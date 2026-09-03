"""DiscoveryRepo behavior: run lifecycle and per-source state."""

import pytest

from app.data.models import RunStatus, SourceStatus
from app.data.repositories import DiscoveryRepo, ResumeRepo


@pytest.fixture
def repo():
    return DiscoveryRepo()


@pytest.fixture
def resume_id():
    resumes = ResumeRepo()
    resume = resumes.create("Main")
    resumes.set_active(resume.id)
    return resume.id


def test_run_lifecycle_sets_finished_at(repo, resume_id):
    run_id = repo.create(resume_id, {"title": "engineer"})

    run = repo.get(run_id)
    assert run.status == RunStatus.QUEUED
    assert run.filters == {"title": "engineer"}
    assert run.finished_at is None

    repo.set_status(run_id, RunStatus.RUNNING)
    assert repo.get(run_id).finished_at is None

    repo.set_status(run_id, RunStatus.COMPLETED)
    run = repo.get(run_id)
    assert run.status == RunStatus.COMPLETED
    assert run.finished_at is not None


def test_source_state_upserts_counters(repo, resume_id):
    run_id = repo.create(resume_id, {})

    repo.set_source_state(run_id, "linkedin", SourceStatus.OK, new_count=3)
    repo.set_source_state(run_id, "linkedin", SourceStatus.OK, new_count=4, duplicate_count=2)

    sources = repo.sources(run_id)
    assert len(sources) == 1
    assert sources[0].new_count == 4
    assert sources[0].duplicate_count == 2


def test_source_error_message(repo, resume_id):
    run_id = repo.create(resume_id, {})

    repo.set_source_state(run_id, "indeed", SourceStatus.ERROR, message="rate limited")

    source = repo.sources(run_id)[0]
    assert source.status == SourceStatus.ERROR
    assert source.message == "rate limited"


def test_run_snapshots_the_active_resume(repo):
    """Acceptance scenario 1: subsequent discovery selects the new active resume."""
    resumes = ResumeRepo()
    first = resumes.create("First")
    resumes.set_active(first.id)

    run_id = repo.create(resumes.get_active().id, {})
    run = repo.get(run_id)
    assert run.resume_id == first.id
    assert run.resume_rev == first.revision

    resumes.replace_sections(first.id, [])  # bumps revision to 2
    assert repo.get(repo.create(resumes.get_active().id, {})).resume_rev == 2

    second = resumes.create("Second")
    resumes.set_active(second.id)

    assert repo.get(repo.create(resumes.get_active().id, {})).resume_id == second.id


def test_create_missing_resume_raises(repo):
    with pytest.raises(ValueError):
        repo.create(9999, {})
