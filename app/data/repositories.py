"""Repository API: the only DB gateway in the app.

Every method opens its own session (open/commit/close). Methods return
SQLAlchemy model instances; callers read attributes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import and_

from app.data.db import SessionLocal
from app.data.models import (
    KEY_PROFILE_VERSION,
    SECTION_SCHEMA,
    Application,
    AttemptStatus,
    Document,
    FitScore,
    Job,
    Profile,
    Resume,
    Run,
    RunStatus,
    Section,
    Setting,
    SourceState,
    utcnow,
)

_SQLITE_HAS_RETURNING = sqlite3.sqlite_version_info >= (3, 35)

# Scraped columns refreshed on every upsert. User statuses (saved/hidden/
# applied) and first_seen_at/created_at are never overwritten by discovery.
_SCRAPED = (
    "source",
    "title",
    "company",
    "location",
    "work_arrangement",
    "employment_type",
    "seniority",
    "compensation",
    "posted_date",
    "experience_req",
    "industry_meta",
    "description",
    "responsibilities",
    "qualifications",
    "extracted_skills",
    "norm_company",
    "norm_title",
    "norm_location",
)


@dataclass
class JobData:
    """All job columns except id, first_seen_at, created_at, updated_at.

    saved_at/hidden_at/applied_at/last_seen_at are accepted for a complete
    record but ignored by upsert: statuses change only via status methods,
    last_seen_at is always refreshed to now.
    """

    source: str
    title: str
    company: str
    norm_company: str
    norm_title: str
    location: str | None = None
    work_arrangement: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    compensation: str | None = None
    posted_date: str | None = None
    experience_req: str | None = None
    industry_meta: dict | None = None
    description: str | None = None
    responsibilities: list | None = None
    qualifications: list | None = None
    extracted_skills: list | None = None
    canonical_url: str | None = None
    norm_location: str | None = None
    saved_at: datetime | None = None
    hidden_at: datetime | None = None
    applied_at: datetime | None = None
    last_seen_at: datetime | None = None


def normalize(value: str) -> str:
    """Casefold, strip, and collapse internal whitespace for search/keys."""
    return " ".join(value.casefold().split())


def _dedupe_conds(data: JobData) -> list:
    """Conditions matching the row `upsert` would refresh; [] when none can exist.

    Mirrors the two partial unique indexes in app/data/models.py. A NULL tuple
    component never collides (SQLite UNIQUE treats NULLs as distinct), so such
    a record always inserts.
    """
    if data.canonical_url is not None:
        return [Job.canonical_url == data.canonical_url]

    if None in (data.norm_company, data.norm_title, data.norm_location, data.posted_date):
        return []

    return [
        Job.canonical_url.is_(None),
        Job.norm_company == data.norm_company,
        Job.norm_title == data.norm_title,
        Job.norm_location == data.norm_location,
        Job.posted_date == data.posted_date,
    ]


def _like_escape(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Exact-match filter key -> column (case-insensitive equality).
_EXACT_COLUMNS = {
    "location": Job.location,
    "work_arrangement": Job.work_arrangement,
    "seniority": Job.seniority,
    "employment_type": Job.employment_type,
}


def _keyword_cond(value: str):
    """Casefolded substring match on title or company (D2 keyword)."""
    pattern = f"%{_like_escape(normalize(value))}%"

    return or_(
        Job.norm_title.like(pattern, escape="\\"), Job.norm_company.like(pattern, escape="\\")
    )


def _exact_cond(column, values: Sequence[str]):
    """Case-insensitive equality, one value per entry; internal whitespace is kept."""
    return func.lower(func.trim(column)).in_([value.lower() for value in values])


def _json_values_cond(column, values: Sequence[str]):
    """True when any scalar inside a JSON column equals one of `values`.

    `industry_meta` has no fixed shape (no source contract pins its keys), so
    membership is tested against every leaf instead of a designated key.

    The table-valued alias MUST be created once and bound to a name: calling
    json_each(...).table_valued(...) twice inside one exists() puts the same
    FROM alias in one subquery and SQLite fails with "ambiguous column name".
    Sibling exists() subqueries may reuse the alias name.
    """
    rows = func.json_each(column).table_valued("value").alias("json_values")

    return exists(
        select(1)
        .select_from(rows)
        .where(func.lower(func.trim(rows.c.value)).in_([value.lower() for value in values]))
    )


def _term_cond(variants: Sequence[str]):
    """One skill term: any synonym spelling in description or extracted skills."""
    conds = []

    for variant in variants:
        pattern = f"%{_like_escape(normalize(variant))}%"
        rows = func.json_each(Job.extracted_skills).table_valued("value").alias("skill_values")

        conds.append(
            or_(
                Job.description.like(pattern, escape="\\"),
                exists(select(1).select_from(rows).where(rows.c.value.like(pattern, escape="\\"))),
            )
        )

    return or_(*conds)


_MARKER_KEYS = frozenset({"v", "uncertain"})


def _is_scalar(value: object) -> bool:
    """Scalar, or an uncertainty marker {"v": str, "uncertain": bool}."""
    if isinstance(value, dict):
        return set(value) == _MARKER_KEYS and isinstance(value["uncertain"], bool)
    return not isinstance(value, (dict, list))


def _validate_items(kind: str, key: str, value: object, object_keys: tuple | None) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{kind}.{key} must be a list")

    for item in value:
        if object_keys is None:
            if not _is_scalar(item):
                raise ValueError(f"{kind}.{key} items must be scalars")
            continue

        if not isinstance(item, dict):
            raise ValueError(f"{kind}.{key} items must be objects")

        unknown = set(item) - set(object_keys)
        if unknown:
            raise ValueError(f"unknown {kind}.{key} field(s): {sorted(unknown)}")

        for field, field_value in item.items():
            if not _is_scalar(field_value):
                raise ValueError(f"{kind}.{key}.{field} must be a scalar")


def _validate_entry(kind: str, entry: dict, schema: dict) -> None:
    unknown = set(entry) - set(schema["keys"])
    if unknown:
        raise ValueError(f"unknown {kind} field(s): {sorted(unknown)}")

    for key, value in entry.items():
        if key in schema.get("lists", ()):
            _validate_items(kind, key, value, schema.get("objects", {}).get(key))
        elif not _is_scalar(value):
            raise ValueError(f"{kind}.{key} must be a scalar")


def _validate_section(sec: dict) -> None:
    """Reject unknown kinds, unknown keys, and mistyped values before storing."""
    if not isinstance(sec, dict):
        raise ValueError("section must be an object")

    kind = sec.get("kind")
    if kind not in SECTION_SCHEMA:
        raise ValueError(f"unknown section kind: {kind!r}")

    content = sec.get("content")
    if not isinstance(content, (dict, list)):
        raise ValueError(f"{kind} content must be an object or list")

    schema = SECTION_SCHEMA[kind]
    entries = content if isinstance(content, list) else [content]
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{kind} entries must be objects")
        _validate_entry(kind, entry, schema)


class ResumeRepo:
    def list(self) -> list[Resume]:
        with SessionLocal() as s:
            return list(s.scalars(select(Resume).order_by(Resume.name)))

    def create(self, name: str) -> Resume:
        if not name.strip():
            raise ValueError("resume name must not be empty")

        with SessionLocal() as s:
            resume = Resume(name=name)

            s.add(resume)

            try:
                s.commit()
            except IntegrityError as e:
                s.rollback()

                raise ValueError(f"resume name already exists: {name}") from e

            return resume

    def create_from_import(
        self, name: str, source_path: str, source_kind: str, sections: list[dict]
    ) -> Resume:
        """Create a resume with its extracted sections and preserved source, one transaction."""
        if not name.strip():
            raise ValueError("resume name must not be empty")

        for sec in sections:
            _validate_section(sec)

        try:
            with SessionLocal() as s:
                resume = Resume(name=name, source_path=source_path, source_kind=source_kind)

                s.add(resume)
                s.flush()

                for sec in sections:
                    s.add(
                        Section(
                            resume_id=resume.id,
                            kind=sec["kind"],
                            position=sec["position"],
                            content=sec["content"],
                        )
                    )

                s.commit()
                return resume
        except IntegrityError as e:
            raise ValueError(f"resume name already exists: {name}") from e

    def get_active(self) -> Resume | None:
        with SessionLocal() as s:
            return s.scalar(select(Resume).where(Resume.is_active.is_(True)))

    def set_active(self, resume_id: int) -> None:
        with SessionLocal() as s:
            resume = s.get(Resume, resume_id)

            if resume is None:
                raise ValueError(f"no resume with id {resume_id}")

            # Clear current active first; the partial unique index allows one.
            s.execute(update(Resume).values(is_active=False))
            resume.is_active = True
            s.commit()

    def delete(self, resume_id: int) -> None:
        with SessionLocal() as s:
            resume = s.get(Resume, resume_id)

            if resume is None:
                raise ValueError(f"no resume with id {resume_id}")

            if resume.is_active:
                raise ValueError("switch the active resume before deleting it")

            s.delete(resume)  # sections cascade via FK
            s.commit()

    def replace_sections(self, resume_id: int, sections: list[dict]) -> None:
        """Delete-then-insert all sections and bump revision, one transaction."""
        for sec in sections:
            _validate_section(sec)

        with SessionLocal() as s:
            resume = s.get(Resume, resume_id)

            if resume is None:
                raise ValueError(f"no resume with id {resume_id}")

            s.execute(delete(Section).where(Section.resume_id == resume_id))

            for sec in sections:
                s.add(
                    Section(
                        resume_id=resume_id,
                        kind=sec["kind"],
                        position=sec["position"],
                        content=sec["content"],
                    )
                )

            resume.revision += 1
            s.commit()

    def sections(self, resume_id: int) -> list[Section]:
        with SessionLocal() as s:
            return list(
                s.scalars(
                    select(Section).where(Section.resume_id == resume_id).order_by(Section.position)
                )
            )

    def revision(self, resume_id: int) -> int:
        with SessionLocal() as s:
            resume = s.get(Resume, resume_id)

            if resume is None:
                raise ValueError(f"no resume with id {resume_id}")

            return resume.revision

    def get(self, resume_id: int) -> Resume | None:
        """One resume row, or None when unknown."""
        with SessionLocal() as s:
            return s.get(Resume, resume_id)


class JobRepo:
    def upsert(self, data: JobData) -> int:
        """Insert or refresh a job by its dedupe authority, return job id."""
        values = asdict(data)
        now = utcnow()

        values["first_seen_at"] = now
        values["last_seen_at"] = now
        values["created_at"] = now
        values["updated_at"] = now

        stmt = insert(Job).values(**values)

        if data.canonical_url is not None:
            # Same canonical URL is always the same row, never duplicated.
            conflict = stmt.on_conflict_do_update(
                index_elements=[Job.canonical_url],
                index_where=Job.canonical_url.is_not(None),
                set_=_upsert_update(stmt, now),
            )
        else:
            # Dedupe on the normalized 4-tuple; NULL component = no conflict = insert.
            conflict = stmt.on_conflict_do_update(
                index_elements=[
                    Job.norm_company,
                    Job.norm_title,
                    Job.norm_location,
                    Job.posted_date,
                ],
                index_where=Job.canonical_url.is_(None),
                set_=_upsert_update(stmt, now),
            )

        with SessionLocal() as s:
            job_id = _execute_upsert(s, conflict)
            s.commit()

            return job_id

    def would_update(self, data: JobData) -> bool:
        """True when `upsert(data)` would refresh an existing row, not insert one.

        The dedupe counterpart of upsert, used for new/duplicate run counts.
        Checked before the upsert, so two processes claiming two different runs
        at once may both count one row as new; counts are advisory UI numbers.
        """
        conds = _dedupe_conds(data)

        if not conds:
            return False

        with SessionLocal() as s:
            return s.scalar(select(Job.id).where(*conds).limit(1)) is not None

    def get(self, job_id: int) -> Job | None:
        with SessionLocal() as s:
            return s.get(Job, job_id)

    def search(  # noqa: PLR0913
        self,
        term: str | None = None,
        status: str | None = None,
        filters: Mapping[str, object] | None = None,
        limit: int = 50,
        offset: int = 0,
        sort: str = "newest",
    ) -> tuple[list[Job], int]:
        """Search jobs; `filters` is the query spec built by
        app.discovery.filters.to_query: title (keyword),
        location/work_arrangement/seniority/employment_type (exact,
        case-insensitive), industry (any value inside industry_meta), date_from
        (ISO lower bound on posted_date, inclusive), terms (synonym groups;
        groups are AND-ed, the spellings inside one group are OR-ed over
        description and extracted_skills).
        """
        conds = [*self._search_conds(term, status), *self._filter_conds(filters or {})]

        with SessionLocal() as s:
            total = s.scalar(select(func.count()).select_from(Job).where(*conds))

            jobs = list(
                s.scalars(
                    select(Job).where(*conds).order_by(*_SORTS[sort]).limit(limit).offset(offset)
                )
            )

            return jobs, total

    @staticmethod
    def _search_conds(term: str | None, status: str | None) -> list:
        conds = []

        if term:
            conds.append(_keyword_cond(term))

        if status == "recommended":
            conds.append(
                and_(Job.saved_at.is_(None), Job.hidden_at.is_(None), Job.applied_at.is_(None))
            )
        elif status == "saved":
            conds.append(Job.saved_at.is_not(None))
        elif status == "hidden":
            conds.append(Job.hidden_at.is_not(None))
        elif status == "applied":
            conds.append(Job.applied_at.is_not(None))

        return conds

    @staticmethod
    def _filter_conds(filters: Mapping[str, object]) -> list:
        """Read-side filter clauses; an empty value imposes no condition (D2)."""
        conds = []

        if title := str(filters.get("title") or "").strip():
            conds.append(_keyword_cond(title))

        for key, column in _EXACT_COLUMNS.items():
            if values := filters.get(key):
                conds.append(_exact_cond(column, values))

        if values := filters.get("industry"):
            conds.append(_json_values_cond(Job.industry_meta, values))

        if date_from := filters.get("date_from"):
            conds.append(Job.posted_date >= date_from)

        for variants in filters.get("terms") or []:
            conds.append(_term_cond(variants))

        return conds

    def set_saved(self, job_id: int) -> None:
        self._set_status(job_id, saved_at=utcnow(), hidden_at=None, applied_at=None)

    def set_hidden(self, job_id: int) -> None:
        self._set_status(job_id, saved_at=None, hidden_at=utcnow(), applied_at=None)

    def _set_status(self, job_id: int, **fields) -> None:
        with SessionLocal() as s:
            job = s.get(Job, job_id)

            if job is None:
                raise ValueError(f"no job with id {job_id}")

            for name, value in fields.items():
                setattr(job, name, value)

            s.commit()

    def record_applied(  # noqa: PLR0913
        self,
        job_id: int,
        url: str | None = None,
        revision_ids: list | None = None,
        notes: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        """Application attempt + applied_at, one transaction."""
        with SessionLocal() as s:
            job = s.get(Job, job_id)

            if job is None:
                raise ValueError(f"no job with id {job_id}")

            if job.applied_at is not None:
                raise ValueError(f"job {job_id} already applied")

            s.add(
                Application(
                    job_id=job_id,
                    status=AttemptStatus.SUBMITTED,
                    submitted_url=url,
                    revision_ids=revision_ids,
                    notes=notes,
                    started_at=started_at or utcnow(),
                    finished_at=finished_at,
                )
            )
            # Applied is mutually exclusive with saved/hidden (contract 37).
            job.saved_at = None
            job.hidden_at = None
            job.applied_at = utcnow()
            s.commit()

    def record_attempt(self, job_id: int, status: str, notes: str | None = None) -> None:
        """Application row only (cancelled/error); the job record is unchanged."""
        if status not in (AttemptStatus.CANCELLED, AttemptStatus.ERROR):
            raise ValueError(f"invalid attempt status: {status}")

        with SessionLocal() as s:
            job = s.get(Job, job_id)

            if job is None:
                raise ValueError(f"no job with id {job_id}")

            s.add(Application(job_id=job_id, status=status, notes=notes, started_at=utcnow()))
            s.commit()


def _upsert_update(stmt, now: datetime) -> dict:
    excluded = stmt.excluded

    update = {col: getattr(excluded, col) for col in _SCRAPED}
    update["last_seen_at"] = now
    update["updated_at"] = now

    return update


def _execute_upsert(s: Session, stmt) -> int:
    if _SQLITE_HAS_RETURNING:
        return s.execute(stmt.returning(Job.id)).scalar_one()

    result = s.execute(stmt)

    s.flush()

    return result.lastrowid


class DiscoveryRepo:
    def create(self, resume_id: int, filters: dict) -> int:
        with SessionLocal() as s:
            resume = s.get(Resume, resume_id)

            if resume is None:
                raise ValueError(f"no resume with id {resume_id}")

            run = Run(
                status=RunStatus.QUEUED,
                filters=filters,
                resume_id=resume_id,
                resume_rev=resume.revision,
            )

            s.add(run)
            s.commit()

            return run.id

    def set_status(self, run_id: int, status: str, finished_at: datetime | None = None) -> None:
        with SessionLocal() as s:
            run = s.get(Run, run_id)

            if run is None:
                raise ValueError(f"no run with id {run_id}")

            run.status = status

            if status in (RunStatus.COMPLETED, RunStatus.FAILED):
                run.finished_at = finished_at or utcnow()

            s.commit()

    def set_source_state(  # noqa: PLR0913
        self,
        run_id: int,
        source: str,
        status: str,
        message: str | None = None,
        new_count: int = 0,
        duplicate_count: int = 0,
    ) -> None:
        values = {
            "status": status,
            "message": message,
            "new_count": new_count,
            "duplicate_count": duplicate_count,
        }

        with SessionLocal() as s:
            row = s.scalar(
                select(SourceState).where(
                    SourceState.run_id == run_id, SourceState.source == source
                )
            )

            if row is None:
                s.add(SourceState(run_id=run_id, source=source, **values))
            else:
                for name, value in values.items():
                    setattr(row, name, value)

            s.commit()

    def get(self, run_id: int) -> Run | None:
        with SessionLocal() as s:
            return s.get(Run, run_id)

    def sources(self, run_id: int) -> list[SourceState]:
        with SessionLocal() as s:
            return list(
                s.scalars(
                    select(SourceState).where(SourceState.run_id == run_id).order_by(SourceState.id)
                )
            )


class DocumentRepo:
    def create(self, resume_id: int, job_id: int, kind: str, content: dict) -> Document:
        with SessionLocal() as s:
            doc = Document(resume_id=resume_id, job_id=job_id, kind=kind, content=content)

            s.add(doc)
            s.commit()

            return doc

    def update(self, doc_id: int, content: dict) -> None:
        """Persist explicit manual edits; generation never reuses a row."""
        with SessionLocal() as s:
            doc = s.get(Document, doc_id)

            if doc is None:
                raise ValueError(f"no document with id {doc_id}")

            doc.content = content
            s.commit()

    def get(self, doc_id: int) -> Document | None:
        with SessionLocal() as s:
            return s.get(Document, doc_id)

    def list_for_job(self, job_id: int) -> list[Document]:
        with SessionLocal() as s:
            return list(
                s.scalars(
                    select(Document)
                    .where(Document.job_id == job_id)
                    .order_by(Document.created_at, Document.id)
                )
            )


class ProfileRepo:
    """Application-profile values; every set bumps the fit-staleness version."""

    def get(self, key: str) -> str | None:
        with SessionLocal() as s:
            row = s.get(Profile, key)

            return row.value if row else None

    def set(self, key: str, value: str) -> None:
        with SessionLocal() as s:
            row = s.get(Profile, key)

            if row is None:
                s.add(Profile(key=key, value=value))
            else:
                row.value = value

            self._bump_version(s)
            s.commit()

    def all(self) -> dict[str, str]:
        with SessionLocal() as s:
            return {row.key: row.value for row in s.scalars(select(Profile))}

    def version(self) -> int:
        with SessionLocal() as s:
            row = s.get(Setting, KEY_PROFILE_VERSION)

            return int(row.value) if row else 0

    @staticmethod
    def _bump_version(s: Session) -> None:
        row = s.get(Setting, KEY_PROFILE_VERSION)

        version = int(row.value) if row else 0

        if row is None:
            s.add(Setting(key=KEY_PROFILE_VERSION, value=str(version + 1)))
        else:
            row.value = str(version + 1)


class SettingsRepo:
    def get(self, key: str) -> str | None:
        with SessionLocal() as s:
            row = s.get(Setting, key)

            return row.value if row else None

    def set(self, key: str, value: str) -> None:
        with SessionLocal() as s:
            row = s.get(Setting, key)

            if row is None:
                s.add(Setting(key=key, value=value))
            else:
                row.value = value

            s.commit()


class FitRepo:
    """One row per (job, resume); staleness is the caller's job (version key comparison)."""

    def get(self, job_id: int, resume_id: int) -> FitScore | None:
        with SessionLocal() as s:
            return s.get(FitScore, (job_id, resume_id))

    def set(  # noqa: PLR0913
        self,
        job_id: int,
        resume_id: int,
        total: int,
        components: dict,
        resume_rev: int,
        profile_rev: int,
    ) -> None:
        stmt = insert(FitScore).values(
            job_id=job_id,
            resume_id=resume_id,
            total=total,
            components=components,
            resume_rev=resume_rev,
            profile_rev=profile_rev,
            computed_at=utcnow(),
        )
        excluded = stmt.excluded

        stmt = stmt.on_conflict_do_update(
            index_elements=[FitScore.job_id, FitScore.resume_id],
            set_={
                "total": excluded.total,
                "components": excluded.components,
                "resume_rev": excluded.resume_rev,
                "profile_rev": excluded.profile_rev,
                "computed_at": utcnow(),
            },
        )

        with SessionLocal() as s:
            s.execute(stmt)
            s.commit()


class ApplicationRepo:
    def record(  # noqa: PLR0913
        self,
        job_id: int,
        status: str,
        submitted_url: str | None = None,
        revision_ids: list | None = None,
        notes: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> Application:
        with SessionLocal() as s:
            app = Application(
                job_id=job_id,
                status=status,
                submitted_url=submitted_url,
                revision_ids=revision_ids,
                notes=notes,
                started_at=started_at or utcnow(),
                finished_at=finished_at,
            )

            s.add(app)
            s.commit()

            return app

    def list_for_job(self, job_id: int) -> list[Application]:
        with SessionLocal() as s:
            return list(
                s.scalars(
                    select(Application)
                    .where(Application.job_id == job_id)
                    .order_by(Application.started_at, Application.id)
                )
            )


_SORTS = {
    "newest": (Job.posted_date.desc().nulls_last(), Job.id.desc()),
    "company": (Job.norm_company.asc(), Job.id.asc()),
    "title": (Job.norm_title.asc(), Job.id.asc()),
}
