"""Job listing: read-side use case over JobRepo."""

from __future__ import annotations

from collections.abc import Mapping

from app.data import Job
from app.data.repositories import JobRepo
from app.discovery.filters import to_query


def list_jobs(filters: Mapping[str, object]) -> tuple[list[Job], int]:
    """Jobs matching the filter block, newest first, plus the total match count.

    The page size is JobRepo's default (50); paging controls arrive with the
    Phase 4 list UI. `total` is the unbounded match count.
    """
    return JobRepo().search(filters=to_query(filters))
