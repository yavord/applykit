"""Discovery orchestration: fetch -> normalize -> upsert -> per-source state."""

import json

import pytest
from sqlalchemy import func, select

from app.data.models import Job, RunStatus, SourceStatus
from app.data.repositories import DiscoveryRepo, ResumeRepo
from app.discovery.errors import SourceError
from app.discovery.reports import REJECTED_LOG
from app.discovery.services.discovery_service import run_discovery
from app.discovery.source_adapter import SOURCE_FETCH_LIMIT, SourceJob
from app.paths import rejected_dir
from tests.fakes import FAKE_JOB, FakeAdapter


@pytest.fixture
def run_id():
    resumes = ResumeRepo()
    resume = resumes.create("Main")
    resumes.set_active(resume.id)
    return DiscoveryRepo().create(resume.id, {"title": "engineer"})


def states(run_id) -> dict:
    return {s.source: s for s in DiscoveryRepo().sources(run_id)}


def job_count(session) -> int:
    return session.scalar(select(func.count(Job.id)))


def rejected_lines() -> list[dict]:
    return [json.loads(line) for line in (rejected_dir() / REJECTED_LOG).read_text().splitlines()]


def test_two_sources_one_failing(run_id, session):
    good = FakeAdapter(
        name="good",
        jobs=[
            FAKE_JOB,
            SourceJob(
                title="Second",
                company="Globex",
                canonical_url="https://example.test/jobs/2",
            ),
        ],
    )
    bad = FakeAdapter(name="bad", error=SourceError("rate limited"))

    run_discovery(run_id, [good, bad])

    run = DiscoveryRepo().get(run_id)
    assert run.status == RunStatus.COMPLETED
    assert run.finished_at is not None
    assert job_count(session) == 2

    by_source = states(run_id)
    good_state = by_source["good"]
    assert good_state.status == SourceStatus.OK
    assert good_state.new_count == 2
    assert good_state.duplicate_count == 0
    assert good_state.message is None

    bad_state = by_source["bad"]
    assert bad_state.status == SourceStatus.ERROR
    assert bad_state.message == "rate limited"
    assert bad_state.new_count == 0 and bad_state.duplicate_count == 0

    assert not (rejected_dir() / REJECTED_LOG).exists()


def test_repeat_run_is_all_duplicates(run_id, session):
    run_discovery(run_id, [FakeAdapter(name="good", jobs=[FAKE_JOB])])

    resume_id = DiscoveryRepo().get(run_id).resume_id
    second = DiscoveryRepo().create(resume_id, {"title": "engineer"})
    run_discovery(second, [FakeAdapter(name="good", jobs=[FAKE_JOB])])

    assert job_count(session) == 1

    state = states(second)["good"]
    assert state.new_count == 0
    assert state.duplicate_count == 1


def test_duplicate_inside_one_payload(run_id, session):
    run_discovery(run_id, [FakeAdapter(name="good", jobs=[FAKE_JOB, FAKE_JOB])])

    assert job_count(session) == 1

    state = states(run_id)["good"]
    assert state.new_count == 1 and state.duplicate_count == 1


def test_nulls_survive_storage(run_id, session):
    run_discovery(
        run_id, [FakeAdapter(name="good", jobs=[SourceJob(title="Engineer", company="Acme")])]
    )

    job = session.scalar(select(Job))
    assert job.location is None
    assert job.compensation is None
    assert job.description is None
    assert job.posted_date is None
    assert job.norm_location is None


def test_invalid_record_skipped_keeps_the_rest(run_id, session):
    run_discovery(
        run_id,
        [
            FakeAdapter(
                name="fake",
                jobs=[SourceJob(title="", company="Acme"), FAKE_JOB],
            )
        ],
    )

    assert job_count(session) == 1

    state = states(run_id)["fake"]
    assert state.status == SourceStatus.OK
    assert state.new_count == 1
    assert state.message == "skipped 1 invalid record(s): missing title"

    (line,) = rejected_lines()
    assert line["source"] == "fake"
    assert line["reason"] == "missing title"
    assert line["run_id"] == run_id
    assert line["job"]["title"] == ""
    assert line["job"]["company"] == "Acme"


def test_query_carries_run_filters(run_id):
    good = FakeAdapter(name="good", jobs=[FAKE_JOB])

    run_discovery(run_id, [good])

    assert good.queries[0].filters == DiscoveryRepo().get(run_id).filters
    assert good.queries[0].limit == SOURCE_FETCH_LIMIT


def test_oserror_isolated(run_id):
    run_discovery(run_id, [FakeAdapter(name="bad", error=OSError("connection reset"))])

    run = DiscoveryRepo().get(run_id)
    assert run.status == RunStatus.COMPLETED

    state = states(run_id)["bad"]
    assert state.status == SourceStatus.ERROR
    assert state.message == "connection reset"


def test_unknown_run_raises():
    with pytest.raises(ValueError):
        run_discovery(9999, [])
