"""API tests: discovery run enqueue, poll, latest, and jobs settings timestamp."""

import pytest
from fastapi.testclient import TestClient

from app.data.models import KEY_DISCOVERY_SOURCES, RunStatus, SourceStatus
from app.data.repositories import DiscoveryRepo, ResumeRepo, SettingsRepo
from app.discovery import SourceError, load_filters
from app.discovery.services.worker import DiscoveryWorker
from app.web.main import app
from tests.fakes import FakeAdapter, install_entries, stub_source

FILTERS = {
    "title": "engineer",
    "location": ["EU"],
    "work_arrangement": ["remote"],
    "seniority": [],
    "employment_type": [],
    "date_posted": "7d",
    "years_experience": "",
    "industry": [],
    "terms": ["aviation"],
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def active_resume():
    resumes = ResumeRepo()
    resume = resumes.create("Main")
    resumes.set_active(resume.id)
    return resume


def queue_and_run(client, resume, *entries):
    install_entries(*entries)
    rid = client.post("/api/discovery-runs", json={"filters": FILTERS}).json()["id"]
    DiscoveryWorker(poll_interval=0.01).run_once()
    return rid


def test_submit_queues_with_snapshot(client, active_resume, monkeypatch):
    install_entries(monkeypatch, stub_source("probe", lambda: FakeAdapter(name="probe")))

    resp = client.post("/api/discovery-runs", json={"filters": FILTERS})

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == RunStatus.QUEUED
    assert body["resume_id"] == active_resume.id
    assert body["resume_rev"] == active_resume.revision
    assert body["sources"] == ["probe"]
    assert body["source_states"] == []
    assert load_filters() == FILTERS


def test_submit_without_body_uses_seeds(client, active_resume, monkeypatch):
    install_entries(monkeypatch, stub_source("probe", lambda: FakeAdapter(name="probe")))

    resp = client.post("/api/discovery-runs")

    assert resp.status_code == 201
    assert resp.json()["status"] == RunStatus.QUEUED


def test_submit_bad_filter_422(client):
    resp = client.post("/api/discovery-runs", json={"filters": {"nope": "1"}})

    assert resp.status_code == 422
    assert "nope" in resp.json()["detail"]


def test_submit_without_active_resume_409(client):
    resp = client.post("/api/discovery-runs", json={"filters": FILTERS})

    assert resp.status_code == 409
    assert "no active resume" in resp.json()["detail"]


def test_snapshot_frozen_at_enqueue(client, active_resume, monkeypatch):
    install_entries(monkeypatch, stub_source("probe", lambda: FakeAdapter(name="probe")))
    rid = client.post("/api/discovery-runs", json={"filters": FILTERS}).json()["id"]

    SettingsRepo().set(KEY_DISCOVERY_SOURCES, '["other"]')
    install_entries(monkeypatch, stub_source("other", lambda: FakeAdapter(name="other")))

    assert DiscoveryRepo().get(rid).sources == ["probe"]


def test_status_payload_reports_sources(client, active_resume, monkeypatch):
    install_entries(
        monkeypatch,
        stub_source("a", lambda: FakeAdapter(name="a")),
        stub_source("b", lambda: FakeAdapter(name="b", error=SourceError("down"))),
    )
    rid = client.post("/api/discovery-runs", json={"filters": FILTERS}).json()["id"]
    DiscoveryWorker(poll_interval=0.01).run_once()

    body = client.get(f"/api/discovery-runs/{rid}").json()

    assert body["status"] == RunStatus.COMPLETED
    assert body["new_count"] == 1
    assert body["duplicate_count"] == 0
    assert body["source_states"] == [
        {
            "source": "a",
            "status": SourceStatus.OK,
            "message": None,
            "new_count": 1,
            "duplicate_count": 0,
        },
        {
            "source": "b",
            "status": SourceStatus.ERROR,
            "message": "down",
            "new_count": 0,
            "duplicate_count": 0,
        },
    ]


def test_missing_seam_is_failed_run_not_500(client, active_resume, monkeypatch):
    install_entries(monkeypatch)
    rid = client.post("/api/discovery-runs", json={"filters": FILTERS}).json()["id"]
    DiscoveryWorker(poll_interval=0.01).run_once()

    resp = client.get(f"/api/discovery-runs/{rid}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == RunStatus.FAILED
    assert "no job source installed" in body["message"]


def test_get_unknown_run_404(client):
    resp = client.get("/api/discovery-runs/999")

    assert resp.status_code == 404
    assert "999" in resp.json()["detail"]


def test_latest_null_then_run(client, active_resume, monkeypatch):
    assert client.get("/api/discovery-runs/latest").json() is None

    install_entries(monkeypatch, stub_source("probe", lambda: FakeAdapter(name="probe")))
    rid = client.post("/api/discovery-runs", json={"filters": FILTERS}).json()["id"]
    DiscoveryWorker(poll_interval=0.01).run_once()

    assert client.get("/api/discovery-runs/latest").json()["id"] == rid


def test_settings_exposes_last_run_at(client, active_resume, monkeypatch):
    assert client.get("/api/jobs/settings").json()["last_run_at"] is None

    install_entries(monkeypatch, stub_source("probe", lambda: FakeAdapter(name="probe")))
    client.post("/api/discovery-runs", json={"filters": FILTERS})
    DiscoveryWorker(poll_interval=0.01).run_once()

    last_run_at = client.get("/api/jobs/settings").json()["last_run_at"]

    assert last_run_at is not None
