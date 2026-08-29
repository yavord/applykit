"""DiscoveryRepo behavior: run lifecycle and per-source state."""

import pytest

from app.data.models import RunStatus, SourceStatus
from app.data.repositories import DiscoveryRepo


@pytest.fixture
def repo():
    return DiscoveryRepo()


def test_run_lifecycle_sets_finished_at(repo):
    run_id = repo.create({"title": "engineer"})

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


def test_source_state_upserts_counters(repo):
    run_id = repo.create({})

    repo.set_source_state(run_id, "linkedin", SourceStatus.OK, new_count=3)
    repo.set_source_state(run_id, "linkedin", SourceStatus.OK, new_count=4, duplicate_count=2)

    sources = repo.sources(run_id)
    assert len(sources) == 1
    assert sources[0].new_count == 4
    assert sources[0].duplicate_count == 2


def test_source_error_message(repo):
    run_id = repo.create({})

    repo.set_source_state(run_id, "indeed", SourceStatus.ERROR, message="rate limited")

    source = repo.sources(run_id)[0]
    assert source.status == SourceStatus.ERROR
    assert source.message == "rate limited"
