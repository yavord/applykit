"""Pydantic request/response models: the OpenAPI contract surface."""

from datetime import datetime

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
    created_at: datetime
    updated_at: datetime


class PagesOut(BaseModel):
    pages: int


class FitOut(BaseModel):
    pages: int
    settings: dict[str, str]


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
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


class JobOut(BaseModel):
    """One stored job; missing values stay null (D9), the UI renders "Not provided"."""

    id: int
    source: str
    title: str
    company: str
    location: str | None
    work_arrangement: str | None
    employment_type: str | None
    seniority: str | None
    compensation: str | None
    posted_date: str | None
    experience_req: str | None
    industry_meta: dict | None
    description: str | None
    responsibilities: list | None
    qualifications: list | None
    extracted_skills: list | None
    canonical_url: str | None


class JobListOut(BaseModel):
    jobs: list[JobOut]
    total: int


class JobsSettingsOut(BaseModel):
    """Jobs filter prefill; the filter block is a plain dict (as in the jobs list)."""

    filters: dict


def job_out(job) -> JobOut:
    """Job ORM row -> API model; nulls pass through, never a substitute string."""
    return JobOut(
        id=job.id,
        source=job.source,
        title=job.title,
        company=job.company,
        location=job.location,
        work_arrangement=job.work_arrangement,
        employment_type=job.employment_type,
        seniority=job.seniority,
        compensation=job.compensation,
        posted_date=job.posted_date,
        experience_req=job.experience_req,
        industry_meta=job.industry_meta,
        description=job.description,
        responsibilities=job.responsibilities,
        qualifications=job.qualifications,
        extracted_skills=job.extracted_skills,
        canonical_url=job.canonical_url,
    )
