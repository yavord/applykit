"""Pydantic request/response models: the OpenAPI contract surface."""

from pydantic import BaseModel


class ResumeSectionIn(BaseModel):
    kind: str
    position: int
    content: dict | list


class SectionsIn(BaseModel):
    sections: list[ResumeSectionIn]


class ResumeSectionOut(BaseModel):
    kind: str
    position: int
    content: dict | list


class ResumeOut(BaseModel):
    id: int
    name: str
    is_active: bool
    revision: int
    source_kind: str | None
    sections: list[ResumeSectionOut]


def resume_out(resume, sections) -> ResumeOut:
    """Compose an ORM Resume row + Section rows; content passes through verbatim."""
    return ResumeOut(
        id=resume.id,
        name=resume.name,
        is_active=resume.is_active,
        revision=resume.revision,
        source_kind=resume.source_kind,
        sections=[
            ResumeSectionOut(kind=s.kind, position=s.position, content=s.content) for s in sections
        ],
    )
