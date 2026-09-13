"""Fit API tests: shrink settings until a saved resume fits one PDF page."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.resumes.services.settings import ExportSettings, settings_to_params
from app.web.main import app
from tests.test_export import SAMPLE_LINES, write_pdf
from tests.test_pages import DENSE_ENTRY, _extend_experience, _import, _pages

# Ladder fields and their defaults; fit only shrinks them.
LADDER_DEFAULTS = {
    "line_spacing": 12,
    "margin_top": 36,
    "margin_bottom": 36,
    "margin_side": 36,
    "body_size": 11,
    "subheader_size": 12,
    "header_size": 14,
    "name_size": 24,
}

UNCHANGED = ("font_family", "header_align", "education_order", "skills_layout", "align_justify")

MONSTER_ENTRY = {
    "title": "Senior Engineer",
    "organization": "Acme",
    "location": "",
    "start": "2020",
    "end": "2023",
    "bullets": ["word " * 200],
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    path = tmp_path / "resume.pdf"

    write_pdf(path, SAMPLE_LINES)

    return path


def _fit(client: TestClient, resume_id: int, query: str = "") -> dict:
    resp = client.post(f"/api/resumes/{resume_id}/fit{query}")

    assert resp.status_code == 200, resp.text

    return resp.json()


def test_fit_long_resume_one_page(client, pdf):
    imported = _import(client, pdf, "Smith Resume")
    resume_id = imported["id"]

    _extend_experience(client, resume_id, [DENSE_ENTRY] * 12)

    result = _fit(client, resume_id)

    assert result["pages"] == 1

    # Self-consistent: re-counting under the returned settings gives one page.
    query = "?" + "&".join(f"{k}={v}" for k, v in result["settings"].items())
    assert _pages(client, resume_id, query) == 1

    for field, default in LADDER_DEFAULTS.items():
        assert int(result["settings"][field]) <= default

    # Non-ladder fields pass through untouched.
    defaults = settings_to_params(ExportSettings())
    for field in UNCHANGED:
        assert result["settings"][field] == defaults[field]


def test_fit_idempotent_on_single_page(client, pdf):
    imported = _import(client, pdf, "Smith Resume")

    result = _fit(client, imported["id"])

    assert result == {"pages": 1, "settings": settings_to_params(ExportSettings())}


def test_fit_floors_on_monster(client, pdf):
    imported = _import(client, pdf, "Smith Resume")
    resume_id = imported["id"]

    _extend_experience(client, resume_id, [MONSTER_ENTRY] * 60)

    result = _fit(client, resume_id)

    assert result["pages"] > 1

    floors = {
        "line_spacing": "10",
        "margin_top": "10",
        "margin_bottom": "10",
        "margin_side": "30",
        "body_size": "8",
        "subheader_size": "8",
        "header_size": "10",
        "name_size": "16",
    }
    for field, floor in floors.items():
        assert result["settings"][field] == floor


def test_fit_docx_format_422(client, pdf):
    imported = _import(client, pdf, "Smith Resume")

    resp = client.post(f"/api/resumes/{imported['id']}/fit?format=docx")

    assert resp.status_code == 422


def test_fit_unknown_resume_404(client):
    resp = client.post("/api/resumes/999/fit")

    assert resp.status_code == 404


def test_fit_bad_params_422(client, pdf):
    imported = _import(client, pdf, "Smith Resume")
    resume_id = imported["id"]

    for query in ("?body_size=99", "?nope=1"):
        resp = client.post(f"/api/resumes/{resume_id}/fit{query}")

        assert resp.status_code == 422
