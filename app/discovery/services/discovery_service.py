"""Discovery orchestration: run one run across its source adapters (3.4).

Per-source fetching is isolated: a source that raises records an ERROR state
and the other sources still store their records. Filters are matched on read
(contract D2), so sources return what they have and every field they report is
stored verbatim (D9). Records the seam refuses go to the rejected-record log.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict

from app.data.models import Run, RunStatus, SourceStatus
from app.data.repositories import DiscoveryRepo, JobData, JobRepo, normalize
from app.discovery.errors import DiscoveryError
from app.discovery.reports import log_rejected
from app.discovery.source_adapter import (
    SOURCE_FETCH_LIMIT,
    SourceAdapter,
    SourceJob,
    SourceQuery,
)


def run_discovery(run_id: int, sources: Sequence[SourceAdapter]) -> None:
    """Fetch every source into JobRepo and record per-source outcomes.

    Marks the run COMPLETED even when sources fail: per-source failures are
    isolated (D6). The worker (3.5) owns the RUNNING claim and marks FAILED when
    an exception escapes this function.
    """
    runs = DiscoveryRepo()
    run = runs.get(run_id)

    if run is None:
        raise ValueError(f"no run with id {run_id}")

    for adapter in sources:
        _run_source(runs, run, adapter)

    runs.set_status(run_id, RunStatus.COMPLETED)


def _run_source(runs: DiscoveryRepo, run: Run, adapter: SourceAdapter) -> None:
    """Fetch one source, upsert its records, log rejects, record its state row.

    Only DiscoveryError and OSError from `fetch` are isolated here; an adapter
    MUST wrap a fetch failure in SourceError. Anything else is a programming
    error and reaches the worker, which marks the run FAILED.
    """
    try:
        jobs = adapter.fetch(SourceQuery(filters=run.filters, limit=SOURCE_FETCH_LIMIT))
    except (DiscoveryError, OSError) as exc:
        message = str(exc) or type(exc).__name__
        runs.set_source_state(run.id, adapter.name, SourceStatus.ERROR, message=message)
        return

    new_count, duplicate_count, rejected = _store(adapter.name, jobs)

    log_rejected(run.id, adapter.name, rejected)

    runs.set_source_state(
        run.id,
        adapter.name,
        SourceStatus.OK,
        message=_skip_message(rejected),
        new_count=new_count,
        duplicate_count=duplicate_count,
    )


def _store(source: str, jobs: Sequence[SourceJob]) -> tuple[int, int, list[tuple[SourceJob, str]]]:
    """Upsert acceptable records; return (new, duplicate, rejected pairs)."""
    repo = JobRepo()
    new_count = 0
    duplicate_count = 0
    rejected: list[tuple[SourceJob, str]] = []

    for job in jobs:
        reason = job.reject_reason()

        if reason is not None:  # an unusable record never aborts the source
            rejected.append((job, reason))
            continue

        data = _to_job_data(source, job)

        if repo.would_update(data):
            duplicate_count += 1
        else:
            new_count += 1

        repo.upsert(data)

    return new_count, duplicate_count, rejected


def _to_job_data(source: str, job: SourceJob) -> JobData:
    """SourceJob -> JobData with every reported field kept, nulls included (D9).

    SourceJob's fields are a subset of JobData's, enforced by
    `tests/test_sources.py::test_source_job_fields_are_storable_columns`, so
    asdict carries titles, metadata, description, lists and URL through; only
    `source` and the three norm_* keys are derived.
    """
    values = asdict(job)
    values.update(
        source=source,
        norm_company=normalize(job.company),
        norm_title=normalize(job.title),
        norm_location=normalize(job.location) if job.location else None,
    )

    return JobData(**values)


def _skip_message(rejected: Sequence[tuple[SourceJob, str]]) -> str | None:
    """One state message for the rejected records, or None when all were usable."""
    if not rejected:
        return None

    reasons = "; ".join(dict.fromkeys(reason for _, reason in rejected))

    return f"skipped {len(rejected)} invalid record(s): {reasons}"
