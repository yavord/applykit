"""SQLAlchemy schema for the local data layer.

All timestamps are naive UTC. Enum-like values are plain str columns;
the StrEnum constants below are the single source of literals.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Alembic needs stable, convention-generated constraint names to diff migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    """Naive UTC now; strip tzinfo so stored values are timezone-less ISO strings."""
    return datetime.now(UTC).replace(tzinfo=None)


class SectionKind(StrEnum):
    CONTACT = "contact"
    SUMMARY = "summary"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"


class DocKind(StrEnum):
    COVER_LETTER = "cover_letter"
    TAILORED_RESUME = "tailored_resume"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class AttemptStatus(StrEnum):
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"
    ERROR = "error"


# Settings keys (settings table). profile_version is the fit-staleness key.
KEY_DISCOVERY_FILTERS = "discovery_filters"
KEY_PROFILE_VERSION = "profile_version"

# Contract 22: persisted filter block, empty/absent value = no restriction.
DEFAULT_FILTERS = {
    "title": "",
    "location": [],
    "work_arrangement": [],
    "seniority": [],
    "employment_type": [],
    "date_posted": "",
    "years_experience": "",
    "industry": [],
}

# Application-profile keys (profiles table): name, email, phone, links, work_auth, answers.


class Profile(Base):
    """Application profile values, one row per key."""

    __tablename__ = "profiles"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(
        Text
    )  # JSON-encoded text when structured (links, work_auth, answers)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Resume(Base):
    """Named resumes; exactly one is active at a time (partial unique index)."""

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    source_path: Mapped[str | None] = mapped_column(
        String
    )  # relative path of preserved original upload
    source_kind: Mapped[str | None] = mapped_column(String)  # "pdf" or "docx"
    revision: Mapped[int] = mapped_column(
        Integer, default=1
    )  # fit-cache key; bumped by replace_sections only
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


Index("uq_resumes_active", Resume.is_active, unique=True, sqlite_where=text("is_active = 1"))


class Section(Base):
    """One row per resume per section kind; content is the per-kind payload."""

    __tablename__ = "resume_sections"
    __table_args__ = (UniqueConstraint("resume_id", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String)  # one of SectionKind
    position: Mapped[int] = mapped_column(Integer)  # 0-based section order
    content: Mapped[dict | list] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# Section content shapes (contract 14; extraction and UI honor these, storage is opaque).
# Any scalar V may be an uncertainty marker {"v": str, "uncertain": bool}.
# contact:        {"name": V, "subtitle": V, "email": V, "phone": V, "location": V,
#                  "tags": [V], "links": [{"name": V, "url": V}]}
# summary:        {"text": V}
# skills:         [{"group": V, "skills": [V]}]
# experience:     [{"title": V, "organization": V, "location": V, "start": V, "end": V,
#                   "summary": V, "bullets": [V]}]
# education:      [{"degree": V, "institution": V, "location": V, "start": V, "end": V,
#                   "gpa": V, "achievements": [V], "coursework": [V]}]
# projects:       [{"title": V, "organization": V, "dates": V, "url": V, "bullets": [V]}]

# SECTION_SCHEMA is the executable form of the shapes above; the repo layer
# enforces it on save (ResumeRepo.replace_sections). "keys" = allowed per-entry
# keys, "lists" = keys whose value is an array, "objects" = list keys whose
# items are objects with their own allowed keys.
SECTION_SCHEMA = {
    SectionKind.CONTACT: {
        "keys": ("name", "subtitle", "email", "phone", "location", "tags", "links"),
        "lists": ("tags", "links"),
        "objects": {"links": ("name", "url")},
    },
    SectionKind.SUMMARY: {"keys": ("text",)},
    SectionKind.SKILLS: {"keys": ("group", "skills"), "lists": ("skills",)},
    SectionKind.EXPERIENCE: {
        "keys": ("title", "organization", "location", "start", "end", "summary", "bullets"),
        "lists": ("bullets",),
    },
    SectionKind.EDUCATION: {
        "keys": (
            "degree",
            "institution",
            "location",
            "start",
            "end",
            "gpa",
            "achievements",
            "coursework",
        ),
        "lists": ("achievements", "coursework"),
    },
    SectionKind.PROJECTS: {
        "keys": ("title", "organization", "dates", "url", "bullets"),
        "lists": ("bullets",),
    },
    SectionKind.CERTIFICATIONS: {"keys": ("name", "issuer", "date", "url")},
}


class Job(Base):
    """Normalized job record. Never deleted; dedupe via the two partial unique indexes."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String)  # configured job source identifier
    title: Mapped[str] = mapped_column(String)
    company: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String)
    work_arrangement: Mapped[str | None] = mapped_column(String)  # remote / hybrid / onsite
    employment_type: Mapped[str | None] = mapped_column(String)
    seniority: Mapped[str | None] = mapped_column(String)
    compensation: Mapped[str | None] = mapped_column(
        String
    )  # free text; null renders as "Not provided"
    posted_date: Mapped[str | None] = mapped_column(String)  # ISO YYYY-MM-DD
    experience_req: Mapped[str | None] = mapped_column(String)
    industry_meta: Mapped[dict | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(String)
    responsibilities: Mapped[list | None] = mapped_column(JSON)
    qualifications: Mapped[list | None] = mapped_column(JSON)
    extracted_skills: Mapped[list | None] = mapped_column(JSON)
    canonical_url: Mapped[str | None] = mapped_column(String)
    norm_company: Mapped[str] = mapped_column(
        String
    )  # casefold + strip + collapse internal whitespace
    norm_title: Mapped[str] = mapped_column(String)
    norm_location: Mapped[str | None] = mapped_column(
        String
    )  # nullable: nulls never collide in the dedup key
    saved_at: Mapped[datetime | None] = mapped_column(DateTime)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime)
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime
    )  # set only via JobRepo.record_applied
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# Dedupe authority: same canonical_url is always one row; without a URL the
# 4-tuple normalized key dedupes. NULLs are distinct in SQLite UNIQUE, so an
# incompletely normalizable job is always inserted.
Index(
    "uq_jobs_canonical_url",
    Job.canonical_url,
    unique=True,
    sqlite_where=text("canonical_url IS NOT NULL"),
)
Index(
    "uq_jobs_dedupe_key",
    Job.norm_company,
    Job.norm_title,
    Job.norm_location,
    Job.posted_date,
    unique=True,
    sqlite_where=text("canonical_url IS NULL"),
)


class Run(Base):
    """A discovery run; resume_id + resume_rev snapshot of the resume that drove the run."""

    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    resume_rev: Mapped[int] = mapped_column(Integer)  # resume.revision snapshot at start
    status: Mapped[str] = mapped_column(String)  # one of RunStatus
    filters: Mapped[dict] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class SourceState(Base):
    """Per-source outcome of a discovery run."""

    __tablename__ = "run_sources"
    __table_args__ = (UniqueConstraint("run_id", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("discovery_runs.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # one of SourceStatus
    message: Mapped[str | None] = mapped_column(String)  # error message or note
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)


class Setting(Base):
    """Preferences/filters and version counters: key-value JSON text."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)  # JSON-encoded text
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class FitScore(Base):
    """One row per (job, resume); keyed for staleness by (resume.revision, profile_version)."""

    __tablename__ = "fit_scores"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True
    )
    resume_rev: Mapped[int] = mapped_column(Integer)
    profile_rev: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)  # 0..100
    components: Mapped[dict] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Application(Base):
    """An application attempt. Insert-only history; jobs are never deleted."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String)  # one of AttemptStatus
    submitted_url: Mapped[str | None] = mapped_column(String)
    revision_ids: Mapped[list | None] = mapped_column(JSON)  # document ids used in the attempt
    notes: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Document(Base):
    """Generated document (tailored resume / cover letter). Insert-only; explicit user edits update in place."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String)  # one of DocKind
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
