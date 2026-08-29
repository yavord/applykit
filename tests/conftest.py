"""Shared fixtures: each test gets a fresh data root and migrated DB."""

import pytest

from app.data.db import SessionLocal, run_migrations


@pytest.fixture(autouse=True)
def tmp_env(tmp_path, monkeypatch):
    # Set before any engine is built: engines are cached per data root URL.
    monkeypatch.setenv("APPLYKIT_DATA_DIR", str(tmp_path))
    run_migrations()


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s
