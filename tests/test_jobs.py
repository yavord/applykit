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


def test_would_update_matches_upsert_authority(repo):
    assert repo.would_update(job_data(canonical_url="https://job/1")) is False

    repo.upsert(job_data(canonical_url="https://job/1"))
    assert repo.would_update(job_data(canonical_url="https://job/1")) is True
    assert repo.would_update(job_data(canonical_url="https://job/2")) is False

    base = {
        "norm_company": "acme",
        "norm_title": "data engineer",
        "norm_location": "berlin",
        "posted_date": "2026-01-01",
    }
    assert repo.would_update(job_data(**base)) is False

    repo.upsert(job_data(**base))
    assert repo.would_update(job_data(**base)) is True

    # A NULL tuple component never collides: upsert always inserts there.
    assert repo.would_update(job_data(norm_location=None, posted_date="2026-01-01")) is False


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


def test_filter_title_keyword_matches_title_or_company(repo):
    id1 = repo.upsert(job_data(title="Data Engineer", norm_title="data engineer"))
    id2 = repo.upsert(
        job_data(
            title="Backend", company="Engine Co", norm_title="backend", norm_company="engine co"
        )
    )

    jobs, total = repo.search(filters={"title": "ENGINE"})

    assert total == 2
    assert {j.id for j in jobs} == {id1, id2}


def test_filter_title_like_wildcards_stay_literal(repo):
    id1 = repo.upsert(job_data(title="Job 50% remote", norm_title="job 50% remote"))
    repo.upsert(job_data(title="Job A remote", norm_title="job a remote"))

    jobs, total = repo.search(filters={"title": "50%"})

    assert total == 1
    assert [j.id for j in jobs] == [id1]


@pytest.mark.parametrize(
    "key,value,other",
    [
        ("location", "europe", "US"),
        ("work_arrangement", "remote", "hybrid"),
        ("seniority", "senior", "entry"),
        ("employment_type", "full_time", "contract"),
    ],
)
def test_filter_exact_fields(repo, key, value, other):
    id1 = repo.upsert(job_data(**{key: value.title() if key == "location" else value}))
    repo.upsert(job_data(**{key: other}))

    jobs, total = repo.search(filters={key: [value]})
    assert total == 1
    assert [j.id for j in jobs] == [id1]

    _, total = repo.search(filters={key: []})
    assert total == 2


def test_filter_industry_matches_json_leaf(repo):
    id1 = repo.upsert(job_data(industry_meta={"category": "Software Development"}))
    repo.upsert(
        job_data(company="Globex", norm_company="globex", industry_meta={"category": "Retail"})
    )

    jobs, total = repo.search(filters={"industry": ["software development"]})

    assert total == 1
    assert [j.id for j in jobs] == [id1]


def test_filter_industry_excludes_null_meta(repo):
    repo.upsert(job_data())

    _, total = repo.search(filters={"industry": ["software development"]})

    assert total == 0


def test_filter_terms_match_description_or_skills(repo):
    id1 = repo.upsert(
        job_data(
            description="We run Google Cloud Platform",
            extracted_skills=["K8s", "Terraform"],
        )
    )
    repo.upsert(job_data(company="Globex", norm_company="globex", description="Sales and revenue"))

    jobs, total = repo.search(filters={"terms": [("gcp", "google cloud", "google cloud platform")]})
    assert total == 1
    assert [j.id for j in jobs] == [id1]

    jobs, total = repo.search(filters={"terms": [("k8s",)]})
    assert total == 1
    assert [j.id for j in jobs] == [id1]


def test_filter_terms_are_anded(repo):
    repo.upsert(
        job_data(description="We run Google Cloud Platform", extracted_skills=["K8s", "Terraform"])
    )

    _, total = repo.search(
        filters={"terms": [("gcp", "google cloud", "google cloud platform"), ("terraform",)]}
    )
    assert total == 1

    _, total = repo.search(
        filters={"terms": [("gcp", "google cloud", "google cloud platform"), ("rust",)]}
    )
    assert total == 0


def test_filter_date_from_inclusive(repo):
    repo.upsert(job_data(posted_date="2026-01-05"))
    id2 = repo.upsert(job_data(title="Second", norm_title="second", posted_date="2026-09-23"))

    jobs, total = repo.search(filters={"date_from": "2026-01-05"})
    assert total == 2

    jobs, total = repo.search(filters={"date_from": "2026-06-01"})
    assert total == 1
    assert [j.id for j in jobs] == [id2]


def test_filter_date_from_excludes_null_posted(repo):
    repo.upsert(job_data(posted_date="2026-09-23"))
    repo.upsert(job_data(title="Second", norm_title="second", posted_date=None))

    _, total = repo.search(filters={"date_from": "2026-01-01"})
    assert total == 1

    _, total = repo.search(filters={})
    assert total == 2


def test_filter_combines_with_term(repo):
    id1 = repo.upsert(job_data(location="US"))
    repo.upsert(job_data(title="Backend", norm_title="backend", location="EU"))

    jobs, total = repo.search("DATA", filters={"location": ["US"]})

    assert total == 1
    assert [j.id for j in jobs] == [id1]


def test_filter_empty_block_matches_all(repo):
    repo.upsert(job_data(posted_date="2026-01-05"))
    repo.upsert(job_data(title="Second", norm_title="second", posted_date="2026-09-23"))

    plain, total_plain = repo.search()
    filtered, total_filtered = repo.search(filters={})

    assert [j.id for j in plain] == [j.id for j in filtered]
    assert total_plain == total_filtered
    assert total_plain == 2


def test_filter_orders_newest_first_nulls_last(repo):
    id1 = repo.upsert(job_data(posted_date="2026-01-05"))
    id2 = repo.upsert(job_data(title="Second", norm_title="second", posted_date="2026-09-23"))
    id3 = repo.upsert(job_data(title="Third", norm_title="third", posted_date=None))

    jobs, _ = repo.search(filters={})

    assert [j.id for j in jobs] == [id2, id1, id3]
