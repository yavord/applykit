"""Resume CRUD orchestration: list, get, sections, activate, delete, upload import."""

import tempfile
from pathlib import Path

from app.data.models import Resume, Section
from app.data.repositories import ResumeRepo
from app.resumes.errors import (
    ActiveResumeError,
    DuplicateResumeError,
    InvalidSectionsError,
    ResumeNotFoundError,
)
from app.resumes.import_service import import_resume as _import_resume


def list_resumes() -> list[Resume]:
    """All resumes in name order."""
    return ResumeRepo().list()


def get_resume(resume_id: int) -> Resume:
    """One resume; unknown id raises ResumeNotFoundError."""
    resume = ResumeRepo().get(resume_id)

    if resume is None:
        raise ResumeNotFoundError(f"no resume with id {resume_id}")

    return resume


def get_sections(resume_id: int) -> list[Section]:
    """Sections for a resume, in position order."""
    return ResumeRepo().sections(resume_id)


def save_sections(resume_id: int, sections: list[dict]) -> None:
    """Replace sections and bump revision; 404 unknown id, 400 bad shape."""
    get_resume(resume_id)

    try:
        ResumeRepo().replace_sections(resume_id, sections)
    except ValueError as e:
        raise InvalidSectionsError(str(e)) from e


def activate_resume(resume_id: int) -> None:
    """Make a resume the active one; 404 unknown id."""
    get_resume(resume_id)
    ResumeRepo().set_active(resume_id)


def delete_resume(resume_id: int) -> None:
    """Delete a resume (not the active one); 404 unknown id, 409 active."""
    get_resume(resume_id)

    try:
        ResumeRepo().delete(resume_id)
    except ValueError as e:
        raise ActiveResumeError(str(e)) from e


def import_resume_upload(raw: bytes, name: str | None = None) -> Resume:
    """Import an uploaded file's bytes: sniff, extract, persist; 409 duplicate name."""
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "upload"

        source.write_bytes(raw)

        try:
            return _import_resume(source, name)
        except ValueError as e:
            raise DuplicateResumeError(str(e)) from e
