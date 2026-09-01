"""Resume HTTP endpoints: import, list, get, patch sections, activate, delete."""

from fastapi import APIRouter, Form, UploadFile

from app.resumes.resume_service import (
    activate_resume,
    delete_resume,
    get_resume,
    get_sections,
    import_resume_upload,
    list_resumes,
    save_sections,
)
from app.web.schemas import ResumeOut, SectionsIn, resume_out

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/import", status_code=201, response_model=ResumeOut)
def import_resume_route(file: UploadFile, name: str | None = Form(None)) -> ResumeOut:
    """Import an uploaded resume; 409 duplicate name, 415 bad format, 422 unreadable."""
    resume = import_resume_upload(file.file.read(), name)

    return resume_out(resume, get_sections(resume.id))


@router.get("", response_model=list[ResumeOut])
def list_resumes_route() -> list[ResumeOut]:
    """All resumes with full sections."""
    return [resume_out(r, get_sections(r.id)) for r in list_resumes()]


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume_route(resume_id: int) -> ResumeOut:
    """One resume with full sections; 404 unknown id."""
    return resume_out(get_resume(resume_id), get_sections(resume_id))


@router.patch("/{resume_id}/sections", response_model=ResumeOut)
def save_sections_route(resume_id: int, body: SectionsIn) -> ResumeOut:
    """Replace sections and bump revision; 400 bad shape, 404 unknown id."""
    save_sections(resume_id, [s.model_dump() for s in body.sections])

    return resume_out(get_resume(resume_id), get_sections(resume_id))


@router.post("/{resume_id}/activate", response_model=ResumeOut)
def activate_resume_route(resume_id: int) -> ResumeOut:
    """Make a resume active; 404 unknown id."""
    activate_resume(resume_id)

    return resume_out(get_resume(resume_id), get_sections(resume_id))


@router.delete("/{resume_id}", status_code=204)
def delete_resume_route(resume_id: int) -> None:
    """Delete a resume; 409 when active, 404 unknown id."""
    delete_resume(resume_id)
