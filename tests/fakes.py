"""Shared public test doubles for the discovery seam.

No production code imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.discovery.captcha import CAPTCHA_SEAM_VERSION
from app.discovery.registry import CAPTCHA_GROUP, SOURCES_GROUP
from app.discovery.source_adapter import (
    SOURCE_SEAM_VERSION,
    SourceJob,
    SourceQuery,
)

# Canned posting for tests that do not care about the payload.
FAKE_JOB = SourceJob(
    title="Data Engineer",
    company="Acme",
    location="Remote",
    work_arrangement="remote",
    employment_type="full_time",
    posted_date="2024-05-01",
    canonical_url="https://example.test/jobs/1",
)


@dataclass
class FakeAdapter:
    """SourceAdapter double: returns `jobs`, records each query, can fail on demand."""

    name: str = "fake"
    seam_version: int = SOURCE_SEAM_VERSION
    jobs: list[SourceJob] = field(default_factory=lambda: [FAKE_JOB])
    error: Exception | None = None
    queries: list[SourceQuery] = field(default_factory=list)

    def fetch(self, query: SourceQuery) -> list[SourceJob]:
        self.queries.append(query)

        if self.error is not None:
            raise self.error

        return list(self.jobs)


class RecordingSolver:
    """CaptchaSolver double: returns a fixed token and records each challenge."""

    seam_version = CAPTCHA_SEAM_VERSION

    def __init__(self, token: str = "test-token") -> None:
        self.token = token
        self.challenges: list[str] = []

    def solve(self, challenge: str) -> str:
        self.challenges.append(challenge)

        return self.token


@dataclass(frozen=True)
class StubEntryPoint:
    """Entry point stand-in for cases installed metadata cannot express."""

    name: str
    group: str
    loaded: object

    def load(self) -> object:
        return self.loaded


def stub_source(name: str, loaded: object) -> StubEntryPoint:
    return StubEntryPoint(name=name, group=SOURCES_GROUP, loaded=loaded)


def stub_captcha(name: str, loaded: object) -> StubEntryPoint:
    return StubEntryPoint(name=name, group=CAPTCHA_GROUP, loaded=loaded)


def install_entries(monkeypatch, *entries) -> None:
    """Point the registry at `entries` instead of installed metadata, per group."""
    monkeypatch.setattr(
        "app.discovery.registry.entry_points",
        lambda group=None, **_: [ep for ep in entries if ep.group == group],
    )
