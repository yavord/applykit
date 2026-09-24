"""API tests: GET /api/jobs filtered listing through the FastAPI app."""

import pytest
from fastapi.testclient import TestClient

from app.data.repositories import JobData, JobRepo
from app.web.main import app


@pytest.fixture
def client():
    return TestClient(app)


def job_data(**overrides) -> JobData:
    defaults = {
        "source": "test",
        "title": "Data Engineer",
        "company": "Acme",
        "norm_company": "acme",
        "norm_title": "data engineer",
    }

    return JobData(**{**defaults, **overrides})


def test_empty_db(client):
    body = client.get("/api/jobs").json()

    assert body == {"jobs": [], "total": 0}


def test_list_newest_first_with_nulls(client):
    repo = JobRepo()
    older = repo.upsert(job_data(posted_date="2026-01-05", description="Sales"))
    newer = repo.upsert(
        job_data(
            title="Data Engineer II",
            norm_title="data engineer ii",
            posted_date="2026-09-23",
            description="We use Google Cloud Platform",
            extracted_skills=["K8s"],
        )
    )

    resp = client.get("/api/jobs")

    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 2
    assert [j["id"] for j in body["jobs"]] == [newer, older]

    first = body["jobs"][0]
    assert first["compensation"] is None
    assert first["experience_req"] is None
    assert first["industry_meta"] is None
    assert "Not provided" not in resp.text


def test_page_capped_at_50(client):
    repo = JobRepo()
    ids = []

    for i in range(51):
        ids.append(
            repo.upsert(
                job_data(
                    title=f"Job {i}",
                    norm_title=f"job {i}",
                    posted_date=f"2026-01-{(i % 28) + 1:02d}",
                )
            )
        )

    body = client.get("/api/jobs").json()

    assert body["total"] == 51
    assert len(body["jobs"]) == 50
    assert body["jobs"][0]["id"] == ids[27]  # newest day 2026-01-28, ids tie-break


def test_filters_restrict(client):
    repo = JobRepo()
    match = repo.upsert(
        job_data(
            work_arrangement="remote",
            location="EU",
            description="We use Google Cloud Platform",
        )
    )
    repo.upsert(
        job_data(
            title="Sales Lead",
            norm_title="sales lead",
            work_arrangement="remote",
            location="US",
            description="Revenue growth",
        )
    )
    repo.upsert(
        job_data(
            title="DevOps",
            norm_title="devops",
            work_arrangement="hybrid",
            location="EU",
            description="We use Google Cloud Platform",
        )
    )

    body = client.get("/api/jobs", params={"work_arrangement": "remote", "terms": "gcp"}).json()

    assert body["total"] == 1
    assert [j["id"] for j in body["jobs"]] == [match]


def test_repeated_query_param_accepted(client):
    repo = JobRepo()
    eu = repo.upsert(job_data(location="EU"))
    us = repo.upsert(job_data(title="Second", norm_title="second", location="US"))
    repo.upsert(job_data(title="Third", norm_title="third", location="APAC"))

    body = client.get("/api/jobs", params=[("location", "EU"), ("location", "US")]).json()

    assert body["total"] == 2
    assert {j["id"] for j in body["jobs"]} == {eu, us}


def test_unknown_filter_422(client):
    resp = client.get("/api/jobs", params={"nope": "1"})

    assert resp.status_code == 422
    assert "nope" in resp.json()["detail"]


def test_bad_date_posted_422(client):
    resp = client.get("/api/jobs", params={"date_posted": "2d"})

    assert resp.status_code == 422
