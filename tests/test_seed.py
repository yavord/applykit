"""Phase 3.3 tests: seed discovery filters from the active resume."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.data import DEFAULT_FILTERS
from app.data.models import SectionKind
from app.data.repositories import ResumeRepo
from app.discovery.services.filters import save_filters
from app.discovery.services.seed import (
    prefill_filters,
    seed_filters,
    seed_from_sections,
    seniority_band,
)
from app.web.main import app

MARKER = {"v": "", "uncertain": True}

FIXED_NOW = datetime(2026, 9, 24)


@pytest.fixture
def client():
    return TestClient(app)


def section(kind, content):
    return SimpleNamespace(kind=kind, content=content)


def full_sections():
    """SAMPLE_LINES-shaped resume; 2012-2023 union -> 12 years -> lead band."""
    return [
        section(
            SectionKind.SKILLS,
            [
                {"group": "Languages", "skills": ["Python", "SQL", "TypeScript"]},
                {"group": "Tools", "skills": ["AWS", "Docker", "PostgreSQL"]},
            ],
        ),
        section(
            SectionKind.EXPERIENCE,
            [
                {
                    "title": "Backend Engineer",
                    "organization": "Globex Inc",
                    "start": "2012",
                    "end": "2016",
                },
                {
                    "title": "Senior Backend Engineer",
                    "organization": "Acme Corp",
                    "start": "2016",
                    "end": "2023",
                },
            ],
        ),
    ]


def store_active_resume() -> None:
    rows = [
        {"kind": str(sec.kind), "position": i, "content": sec.content}
        for i, sec in enumerate(full_sections())
    ]

    resume = ResumeRepo().create_from_import("seed", "seed.txt", "plain", rows)
    ResumeRepo().set_active(resume.id)


def test_full_resume_shape():
    seeds = seed_from_sections(full_sections())

    assert seeds["title"] == "Senior Backend Engineer"
    assert seeds["seniority"] == ["lead"]
    assert seeds["terms"] == ["Python", "SQL", "TypeScript", "AWS", "Docker", "PostgreSQL"]
    assert seeds["years_experience"] == ""


@pytest.mark.parametrize(
    ("years", "band"),
    [
        (0, "entry"),
        (2, "entry"),
        (3, "mid"),
        (5, "mid"),
        (6, "senior"),
        (9, "senior"),
        (10, "lead"),
        (30, "lead"),
    ],
)
def test_seniority_band_boundaries(years, band):
    assert seniority_band(years) == band


def test_union_counts_overlaps_once_and_skips_gaps(monkeypatch):
    monkeypatch.setattr("app.discovery.services.seed.utcnow", lambda: FIXED_NOW)

    overlapping = seed_from_sections(
        [
            section(
                SectionKind.EXPERIENCE,
                [
                    {"title": "A", "start": "2016", "end": "2020"},
                    {"title": "B", "start": "2018", "end": "2019"},
                ],
            )
        ]
    )
    assert overlapping["seniority"] == ["mid"]

    gapped = seed_from_sections(
        [
            section(
                SectionKind.EXPERIENCE,
                [
                    {"title": "A", "start": "2016", "end": "2017"},
                    {"title": "B", "start": "2023", "end": "Present"},
                ],
            )
        ]
    )
    assert gapped["seniority"] == ["mid"]


def test_present_anchors_to_now(monkeypatch):
    monkeypatch.setattr("app.discovery.services.seed.utcnow", lambda: FIXED_NOW)

    seeds = seed_from_sections(
        [
            section(
                SectionKind.EXPERIENCE,
                [{"title": "Engineer", "start": "Jan 2020", "end": "Present"}],
            )
        ]
    )

    assert seeds["seniority"] == ["senior"]


def test_uncertain_values_drop():
    sections = [
        section(SectionKind.SKILLS, [{"group": MARKER, "skills": [MARKER, None, "  "]}]),
        section(SectionKind.EXPERIENCE, [{"title": MARKER, "start": MARKER, "end": MARKER}]),
    ]

    assert seed_from_sections(sections) == DEFAULT_FILTERS


def test_single_dated_entry_yields_title_not_years():
    seeds = seed_from_sections(
        [
            section(
                SectionKind.EXPERIENCE,
                [{"title": "Data Scientist", "start": MARKER, "end": "2023"}],
            )
        ]
    )

    assert seeds["title"] == "Data Scientist"
    assert seeds["seniority"] == []


def test_seed_is_deterministic():
    sections = full_sections()

    assert seed_from_sections(sections) == seed_from_sections(sections)


def test_seed_filters_without_active_resume():
    assert seed_filters() == DEFAULT_FILTERS


def test_prefill_persisted_block_wins():
    store_active_resume()

    assert prefill_filters() == seed_from_sections(full_sections())

    block = save_filters({"title": "custom"})

    assert prefill_filters() == block
    assert prefill_filters()["title"] == "custom"


def test_settings_route(client):
    store_active_resume()
    expected = seed_from_sections(full_sections())

    resp = client.get("/api/jobs/settings")

    assert resp.status_code == 200
    assert resp.json() == {"filters": expected}

    block = save_filters({"title": "custom"})

    resp = client.get("/api/jobs/settings")

    assert resp.status_code == 200
    assert resp.json() == {"filters": block}
