"""Engine, sessions, pragmas, and programmatic migrations.

Singletons are lazily built and cached per data root, so tests (or code) that
swap APPLYKIT_DATA_DIR get a fresh engine per root. Repositories are the only
DB gateway: no other module creates sessions or touches the engine.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.paths import db_path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"

# One (engine, session factory) per data root URL.
_FACTORIES: dict[str, sessionmaker] = {}


def db_url() -> str:
    return f"sqlite:///{db_path()}"


def session_factory() -> sessionmaker:
    url = db_url()

    if url not in _FACTORIES:
        _FACTORIES[url] = _build(url)

    return _FACTORIES[url]


def SessionLocal():
    return session_factory()()


def _build(url: str) -> sessionmaker:
    # Shared by worker threads: WAL allows concurrent readers, one writer serializes.
    engine: Engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_pragmas)

    return sessionmaker(bind=engine, expire_on_commit=False)


def _set_pragmas(dbapi_conn, _record) -> None:
    cursor = dbapi_conn.cursor()

    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.fetchone()  # journal_mode returns a row; consume it
    cursor.execute("PRAGMA busy_timeout=5000")

    cursor.close()


def run_migrations() -> None:
    cfg = Config(str(_ALEMBIC_INI))

    command.upgrade(cfg, "head")
