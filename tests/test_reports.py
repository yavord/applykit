"""Rejected-record log driver: append-only JSONL to the temp data root."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.discovery.reports import REJECTED_LOG, log_rejected
from app.discovery.source_adapter import SourceJob
from app.paths import rejected_dir
from tests.fakes import FAKE_JOB


def log_path() -> Path:
    return rejected_dir() / REJECTED_LOG


def read_lines() -> list[dict]:
    return [json.loads(line) for line in log_path().read_text().splitlines()]


def test_no_rejects_writes_nothing():
    log_rejected(1, "fake", [])

    assert not log_path().exists()


def test_appends_one_line_per_record_across_calls():
    log_rejected(1, "fake", [(SourceJob(title="", company="Acme"), "missing title")])
    log_rejected(2, "remotive", [(FAKE_JOB, "posted_date is not ISO YYYY-MM-DD: 'yesterday'")])

    lines = read_lines()
    assert len(lines) == 2

    for line in lines:
        assert set(line) == {"run_id", "source", "at", "reason", "job"}
        datetime.fromisoformat(line["at"])
        assert isinstance(line["job"], dict)

    assert lines[0]["run_id"] == 1 and lines[0]["source"] == "fake"
    assert lines[0]["reason"] == "missing title" and lines[0]["job"]["title"] == ""

    assert lines[1]["run_id"] == 2 and lines[1]["source"] == "remotive"
    assert lines[1]["job"]["canonical_url"] == FAKE_JOB.canonical_url


def test_payload_round_trips_nested_fields():
    job = SourceJob(
        title="Ingeniero de datos",
        company="Acme",
        industry_meta={"category": "Software Development"},
        responsibilities=["Ship"],
        canonical_url="https://example.test/jobs/3",
    )

    log_rejected(7, "fake", [(job, "missing company")])

    assert read_lines()[0]["job"] == asdict(job)
