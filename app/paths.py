"""Paths for the local data layer."""

import os
from pathlib import Path

DATA_DIR_ENV = "APPLYKIT_DATA_DIR"

UPLOADS = "uploads"

REJECTED = "rejected"


def data_root() -> Path:
    """Resolve and ensure the data root: env var override or repo-local `data/`."""
    override = os.environ.get(DATA_DIR_ENV)

    root = Path(override).resolve() if override else Path(__file__).resolve().parents[1] / "data"

    root.mkdir(parents=True, exist_ok=True)

    return root


def db_path() -> Path:
    return data_root() / "applykit.db"


def uploads_dir() -> Path:
    return _ensure_dir(UPLOADS)


def rejected_dir() -> Path:
    """Directory of rejected-record reports; created on first use."""
    return _ensure_dir(REJECTED)


def absolute_path(relative: str) -> Path:
    """Resolve a stored relative path against the data root."""
    return data_root() / relative


def _ensure_dir(name: str) -> Path:
    path = data_root() / name

    path.mkdir(parents=True, exist_ok=True)

    return path
