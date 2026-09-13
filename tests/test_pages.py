"""Pages API tests: PDF page count for a saved resume under drawer settings."""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.web.main import app
from tests.test_export import SAMPLE_LINES, write_pdf

COMPACT = "?body_size=8&line_spacing=10&margin_top=10&margin_bottom=10&margin_side=30"

DENSE_ENTRY = {
    "title": "Senior Engineer",
    "organization": "Acme",
    "location": "",
    "start": "2020",
    "end": "2023",
    "bullets": ["word " * 40],
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    path = tmp_path / "resume.pdf"

    write_pdf(path, SAMPLE_LINES)

    return path


def _import(client: TestClient, pdf: Path, name: str) -> dict:
    with pdf.open("rb") as f:
        resp = client.post(
            "/api/resumes/import",
            files={"file": ("resume.pdf", f, "application/pdf")},
            data={"name": name},
        )

    assert resp.status_code == 201, resp.text

    return resp.json()


def _extend_experience(client: TestClient, resume_id: int, entries: list[dict]) -> None:
    resp = client.get(f"/api/resumes/{resume_id}")

    body = resp.json()
    for sec in body["sections"]:
        if sec["kind"] == "experience":
            sec["content"].extend(entries)
            break
    else:
        raise AssertionError("fixture resume has no experience section")

    resp = client.patch(f"/api/resumes/{resume_id}/sections", json={"sections": body["sections"]})

    assert resp.status_code == 200, resp.text


def _pages(client: TestClient, resume_id: int, query: str = "") -> int:
    resp = client.get(f"/api/resumes/{resume_id}/pages{query}")

    assert resp.status_code == 200, resp.text

    return resp.json()["pages"]


def test_pages_parity_with_export(client, pdf):
    """Pages endpoint and export.pdf count the same rendered document."""
    imported = _import(client, pdf, "Smith Resume")
    resume_id = imported["id"]

    exported = client.get(f"/api/resumes/{resume_id}/export.pdf")

    assert exported.status_code == 200
    assert _pages(client, resume_id) == len(PdfReader(BytesIO(exported.content)).pages)


def test_pages_multi_page_fixture(client, pdf):
    """A long experience section spans pages; compact settings shrink it."""
    imported = _import(client, pdf, "Smith Resume")
    resume_id = imported["id"]

    _extend_experience(client, resume_id, [DENSE_ENTRY] * 12)

    default = _pages(client, resume_id)
    compact = _pages(client, resume_id, COMPACT)

    assert default > 1
    assert compact < default


def test_pages_docx_format_422(client, pdf):
    imported = _import(client, pdf, "Smith Resume")

    resp = client.get(f"/api/resumes/{imported['id']}/pages?format=docx")

    assert resp.status_code == 422


def test_pages_bad_params_422(client, pdf):
    imported = _import(client, pdf, "Smith Resume")
    resume_id = imported["id"]

    for query in ("?body_size=99", "?nope=1"):
        resp = client.get(f"/api/resumes/{resume_id}/pages{query}")

        assert resp.status_code == 422


def test_pages_unknown_resume_404(client):
    resp = client.get("/api/resumes/999/pages")

    assert resp.status_code == 404
