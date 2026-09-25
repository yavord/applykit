"""The public source seam: an adapter fetches postings as SourceJobs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

# Politeness cap on records fetched per source per run. Advisory: the Remotive
# public API ignores `limit` and returns a fixed page, so an adapter caps
# client-side.
SOURCE_FETCH_LIMIT = 100

# Bumped whenever this protocol or the SourceJob shape changes incompatibly;
# the registry refuses an installed adapter that targets another version.
SOURCE_SEAM_VERSION = 1


@dataclass(frozen=True)
class SourceQuery:
    """Fetch inputs: the run's persisted filter block plus a hard fetch cap.

    `filters` is the canonical discovery filter block (DEFAULT_FILTERS); an
    adapter reads the keys its API supports and MUST tolerate unknown or
    missing keys. Matching stays on read, so sources return what they have.
    """

    filters: Mapping[str, object]
    limit: int = SOURCE_FETCH_LIMIT


@dataclass(frozen=True)
class SourceJob:
    """One posting as a source reported it. Nulls are preserved, never guessed."""

    title: str
    company: str
    location: str | None = None
    work_arrangement: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    compensation: str | None = None
    posted_date: str | None = None
    experience_req: str | None = None
    industry_meta: dict | None = None
    description: str | None = None
    responsibilities: list[str] | None = None
    qualifications: list[str] | None = None
    extracted_skills: list[str] | None = None
    canonical_url: str | None = None

    def reject_reason(self) -> str | None:
        """Why this record cannot be stored, or None when it is acceptable.

        Construction never raises: orchestration logs the reason, skips this
        record and keeps the source's remaining records.
        """
        if not isinstance(self.title, str) or not self.title.strip():
            return "missing title"

        if not isinstance(self.company, str) or not self.company.strip():
            return "missing company"

        if self.posted_date is not None:
            try:
                date.fromisoformat(self.posted_date)
            except (TypeError, ValueError):
                return f"posted_date is not ISO YYYY-MM-DD: {self.posted_date!r}"

        return None


@runtime_checkable
class SourceAdapter(Protocol):
    """A configured job source; implementations are installed packages."""

    name: str  # stable source id, stored on every job row and source state
    seam_version: int  # MUST equal SOURCE_SEAM_VERSION

    def fetch(self, query: SourceQuery) -> list[SourceJob]:
        """Return the source's current postings; raise SourceError on failure."""
        ...
