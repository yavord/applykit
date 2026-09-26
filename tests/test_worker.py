"""In-process worker: claim, execute, recover, boot enqueue, lifespan"""

import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.data.db import SessionLocal
from app.data.models import Job, Run, RunStatus, SourceStatus, utcnow
from app.data.repositories import DiscoveryRepo, ResumeRepo
from app.discovery import bootstrap_if_stale, enqueue_run, recover_stale
from app.discovery.services.discovery_service import run_discovery
from app.discovery.services.worker import STALE_MESSAGE, DiscoveryWorker
from app.web.main import app
from tests.fakes import FAKE_JOB, FakeAdapter, install_entries, stub_source


@pytest.fixture
def active_resume():
    resumes = ResumeRepo()
    resume = resumes.create("Main")
    resumes.set_active(resume.id)
    return resume


def wait_terminal(run_id: int, timeout: float = 5.0) -> str:
    """Block until a run leaves QUEUED/RUNNING; return its final status."""
    deadline = utcnow() + timedelta(seconds=timeout)

    while True:
        status = DiscoveryRepo().get(run_id).status

        if status in (RunStatus.COMPLETED, RunStatus.FAILED):
            return status

        assert utcnow() < deadline, f"run {run_id} never reached a terminal state"

        time.sleep(0.01)


def job_count(session) -> int:
    return session.scalar(select(func.count(Job.id)))


def test_claim_is_single_flight(active_resume):
    rid = enqueue_run()

    assert DiscoveryRepo().claim(rid) is True
    assert DiscoveryRepo().get(rid).status == RunStatus.RUNNING
    assert DiscoveryRepo().claim(rid) is False


def test_run_once_executes_queued_run(monkeypatch, active_resume, session):
    install_entries(monkeypatch, stub_source("fake", lambda: FakeAdapter(jobs=[FAKE_JOB])))
    worker = DiscoveryWorker(poll_interval=0.01)
    rid = enqueue_run()

    assert worker.run_once() is True

    run = DiscoveryRepo().get(rid)
    assert run.status == RunStatus.COMPLETED

    states = DiscoveryRepo().sources(rid)
    assert [(s.source, s.status) for s in states] == [("fake", SourceStatus.OK)]
    assert job_count(session) == 1


def test_run_once_without_queue_is_false():
    assert DiscoveryWorker().run_once() is False


def test_service_exception_marks_failed_and_worker_survives(active_resume):
    def boom(run_id, sources):
        raise RuntimeError("boom")

    worker = DiscoveryWorker(run_fn=boom, load_fn=lambda: [])
    first, second = enqueue_run(), enqueue_run()

    assert worker.run_once() is True
    assert worker.run_once() is True

    for rid in (first, second):
        run = DiscoveryRepo().get(rid)
        assert run.status == RunStatus.FAILED
        assert run.message == "boom"

    assert worker.run_once() is False


def test_missing_seam_marks_run_failed(active_resume):
    worker = DiscoveryWorker(run_fn=run_discovery)
    rid = enqueue_run()

    worker.run_once()

    run = DiscoveryRepo().get(rid)
    assert run.status == RunStatus.FAILED
    assert "no job source installed" in run.message


def test_recover_stale(active_resume):
    runs = DiscoveryRepo()

    def running_run(started_at) -> int:
        rid = runs.create(active_resume.id, {})
        with SessionLocal() as s:
            s.execute(
                update(Run)
                .where(Run.id == rid)
                .values(status=RunStatus.RUNNING, started_at=started_at)
            )
            s.commit()
        return rid

    old_rid = running_run(utcnow() - timedelta(hours=1))

    assert recover_stale() == 1

    old = runs.get(old_rid)
    assert old.status == RunStatus.FAILED
    assert old.message == STALE_MESSAGE
    assert old.finished_at is not None

    fresh_rid = running_run(utcnow())

    assert recover_stale() == 0
    assert runs.get(fresh_rid).status == RunStatus.RUNNING


def test_bootstrap_enqueues_when_stale(active_resume):
    rid = bootstrap_if_stale()

    assert rid is not None

    run = DiscoveryRepo().get(rid)
    assert run.status == RunStatus.QUEUED


def test_bootstrap_skips_fresh(active_resume):
    runs = DiscoveryRepo()
    rid = runs.create(active_resume.id, {})
    runs.set_status(rid, RunStatus.COMPLETED, finished_at=utcnow() - timedelta(hours=1))
    runs.set_source_state(rid, "fake", SourceStatus.OK)

    assert bootstrap_if_stale() is None
    assert runs.get(rid).status == RunStatus.COMPLETED


def test_bootstrap_skips_unfinished(active_resume):
    enqueue_run()

    assert bootstrap_if_stale() is None


def test_bootstrap_skips_without_resume():
    assert bootstrap_if_stale() is None


def test_lifespan_runs_queued_run_to_completion(monkeypatch, active_resume):
    install_entries(monkeypatch, stub_source("fake", lambda: FakeAdapter(jobs=[FAKE_JOB])))

    with TestClient(app):
        rid = enqueue_run()
        assert wait_terminal(rid) == RunStatus.COMPLETED

    assert app.state.worker.is_alive() is False
    assert DiscoveryRepo().get(rid).status == RunStatus.COMPLETED
