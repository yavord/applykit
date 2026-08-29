"""JobRepo behavior: dedupe, statuses, applications, search."""

import pytest
from sqlalchemy import func, select

from app.data.models import Application, AttemptStatus, Job
from app.data.repositories import JobData, JobRepo, _like_escape


@pytest.fixture
def repo():
    return JobRepo()


def job_data(**overrides) -> JobData:
    defaults = {
        "source": "test",
        "title": "Data Engineer",
        "company": "Acme",
        "norm_company": "acme",
        "norm_title": "data engineer",
    }

    return JobData(**{**defaults, **overrides})


def job_count(session) -> int:
    return session.scalar(select(func.count(Job.id)))


def test_canonical_url_dedupes_and_refreshes(repo, session):
    id1 = repo.upsert(job_data(canonical_url="https://job/1"))
    id2 = repo.upsert(
        job_data(
            title="Data Engineer Sr", norm_title="data engineer sr", canonical_url="https://job/1"
        )
    )

    assert id1 == id2
    assert job_count(session) == 1
    assert repo.get(id1).title == "Data Engineer Sr"
    assert repo.get(id1).first_seen_at is not None


def test_no_url_dedupes_on_4_tuple(repo, session):
    base = {
        "norm_company": "acme",
        "norm_title": "data engineer",
        "norm_location": "berlin",
        "posted_date": "2026-01-01",
    }

    id1 = repo.upsert(job_data(**base))
    id2 = repo.upsert(job_data(title="Data Engineer II", **base))

    assert id1 == id2
    assert job_count(session) == 1


def test_null_tuple_component_inserts_new_row(repo, session):
    base = {"norm_company": "acme", "norm_title": "data engineer"}

    id1 = repo.upsert(job_data(norm_location="berlin", posted_date="2026-01-01", **base))
    id2 = repo.upsert(job_data(norm_location=None, posted_date="2026-01-01", **base))
    id3 = repo.upsert(job_data(norm_location="berlin", posted_date=None, **base))

    assert len({id1, id2, id3}) == 3
    assert job_count(session) == 3


def test_statuses_are_mutually_exclusive(repo):
    id1 = repo.upsert(job_data())

    repo.set_saved(id1)
    job = repo.get(id1)
    assert job.saved_at is not None and job.hidden_at is None and job.applied_at is None

    repo.set_hidden(id1)
    job = repo.get(id1)
    assert job.saved_at is None and job.hidden_at is not None and job.applied_at is None

    repo.record_applied(id1, url="https://apply/1")
    job = repo.get(id1)
    assert job.saved_at is None and job.hidden_at is None and job.applied_at is not None


def test_record_applied_writes_application_and_flag_in_one_transaction(repo, session):
    id1 = repo.upsert(job_data())

    repo.record_applied(id1, url="https://apply/1", revision_ids=[10], notes="done")

    app = session.scalar(select(Application).where(Application.job_id == id1))
    assert app.status == AttemptStatus.SUBMITTED
    assert app.submitted_url == "https://apply/1"
    assert repo.get(id1).applied_at is not None


def test_record_applied_twice_raises(repo):
    id1 = repo.upsert(job_data())
    repo.record_applied(id1)

    with pytest.raises(ValueError):
        repo.record_applied(id1)


def test_record_attempt_leaves_job_unchanged(repo):
    id1 = repo.upsert(job_data())

    repo.record_attempt(id1, AttemptStatus.CANCELLED, notes="no budget")

    assert repo.get(id1).applied_at is None


def test_search_normalizes_term(repo):
    id1 = repo.upsert(job_data())
    repo.upsert(
        job_data(title="Plumber", company="Drain Co", norm_title="plumber", norm_company="drain co")
    )

    jobs, total = repo.search("  DATA   engineer ")

    assert total == 1
    assert [j.id for j in jobs] == [id1]


def test_search_escapes_like_wildcards(repo):
    id1 = repo.upsert(job_data(title="Job 50% remote", norm_title="job 50% remote"))
    repo.upsert(job_data(title="Job A remote", norm_title="job a remote"))

    jobs, total = repo.search("50%")

    assert total == 1
    assert [j.id for j in jobs] == [id1]
    assert _like_escape("100%_x\\y") == "100\\%\\_x\\\\y"


def test_search_status_filters(repo):
    id1 = repo.upsert(job_data())
    repo.upsert(job_data(title="Second", norm_title="second"))

    repo.set_saved(id1)

    _, total = repo.search(status="saved")
    assert total == 1
    _, total = repo.search(status="recommended")
    assert total == 1
