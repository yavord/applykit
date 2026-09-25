"""Rejected-record log: append-only JSONL of records the seam refused.

A file, not a table: rejects are adapter-development diagnostics, not product
data, so the schema stays migration-free. Browse with:
    jq -c 'select(.run_id == 42)' data/rejected/jobs.jsonl

Line shape:
    {"run_id": 42, "source": "remotive", "at": "2026-09-25T12:00:00.123456",
     "reason": "missing title", "job": {<every SourceJob field>}}
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict

from app.data.models import utcnow
from app.discovery.source_adapter import SourceJob
from app.paths import rejected_dir

REJECTED_LOG = "jobs.jsonl"


def log_rejected(run_id: int, source: str, rejected: Sequence[tuple[SourceJob, str]]) -> None:
    """Append one JSON line per (job, reason) pair; no-op when none were rejected."""
    if not rejected:
        return

    at = utcnow().isoformat()
    lines = [
        json.dumps(
            {"run_id": run_id, "source": source, "at": at, "reason": reason, "job": asdict(job)},
            ensure_ascii=False,
        )
        for job, reason in rejected
    ]

    # One append per record could interleave with another process; a single
    # write keeps lines whole.
    with (rejected_dir() / REJECTED_LOG).open("a", encoding="utf-8") as handle:
        handle.write("".join(f"{line}\n" for line in lines))
