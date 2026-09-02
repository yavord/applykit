"""API tests: resume import + CRUD through the FastAPI app (TestClient)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.web.main import app

REPO_DATA = Path(__file__).resolve().parents[1] / "data"

# Canonical fixture resume; mirrors tests/test_import.py.
SAMPLE_LINES = [
    "Jane Q. Developer",
    "Senior Backend Engineer | San Francisco, CA",
    "jane.q@example.com | (415) 555-0132 | linkedin.com/in/janeq",
    "SUMMARY",
    "Experienced backend engineer with 8 years building distributed systems.",
    "SKILLS",
    "Languages: Python, SQL, TypeScript",
    "AWS, Docker, PostgreSQL",
    "EXPERIENCE",
    "Senior Backend Engineer | Acme Corp",
    "2020 - 2023",
    "- Built migration pipeline serving 2M users",
    "- Cut p95 latency by 40%",
    "",
    "Backend Engineer | Globex Inc",
    "2016 - 2020",
    "- Shipped billing rewrite",
    "EDUCATION",
    "State University, 2012 - 2016",
    "B.S. Computer Science",
    "GPA: 3.8",
    "PROJECTS",
    "Resume Parser | personal",
    "2023 - 2024",
    "- Extracts structured resumes from raw text",
    "CERTIFICATIONS",
    "AWS Certified Solutions Architect - Associate, Amazon Web Services, 2024",
]


def write_pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path))
    y = 780

    for line in lines:
        c.drawString(60, y, line if line else " ")
        y -= 16

    c.save()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def pdf(tmp_path) -> Path:
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


def test_import_happy_path(client, pdf):
    body = _import(client, pdf, "Smith Resume")

    assert body["id"] == 1
    assert body["name"] == "Smith Resume"
    assert body["is_active"] is False
    assert body["revision"] == 1
    assert body["source_kind"] == "pdf"
    assert "source_path" not in body

    kinds = [s["kind"] for s in body["sections"]]
    assert kinds == [
        "contact",
        "summary",
        "skills",
        "experience",
        "education",
        "projects",
        "certifications",
    ]
    assert [s["position"] for s in body["sections"]] == list(range(len(kinds)))
    assert all(isinstance(s["content"], (dict, list)) for s in body["sections"])


def test_duplicate_name_409(client, pdf):
    _import(client, pdf, "Smith Resume")

    resp = client.post(
        "/api/resumes/import",
        files={"file": ("resume.pdf", pdf.read_bytes(), "application/pdf")},
        data={"name": "Smith Resume"},
    )

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_unsupported_txt_415(client, tmp_path):
    txt = tmp_path / "resume.txt"
    txt.write_text("just text")

    resp = client.post(
        "/api/resumes/import",
        files={"file": ("resume.txt", txt.read_bytes(), "text/plain")},
    )

    assert resp.status_code == 415


def test_corrupt_pdf_422(client, tmp_path):
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"%PDF-1.4\n" + b"\x00" * 512)

    resp = client.post(
        "/api/resumes/import",
        files={"file": ("corrupt.pdf", bad.read_bytes(), "application/pdf")},
    )

    assert resp.status_code == 422


def test_list_resumes(client, pdf):
    _import(client, pdf, "Beta Resume")
    _import(client, pdf, "Alpha Resume")

    resp = client.get("/api/resumes")

    assert resp.status_code == 200

    body = resp.json()
    assert [r["name"] for r in body] == ["Alpha Resume", "Beta Resume"]
    assert all(r["sections"] for r in body)
    assert all(r["sections"][0]["kind"] == "contact" for r in body)
    assert all("created_at" in r and "updated_at" in r for r in body)


def test_get_resume(client, pdf):
    imported = _import(client, pdf, "Smith Resume")

    resp = client.get(f"/api/resumes/{imported['id']}")

    assert resp.status_code == 200
    assert resp.json()["name"] == "Smith Resume"
    assert len(resp.json()["sections"]) == 7


def test_get_resume_unknown_404(client):
    resp = client.get("/api/resumes/999")

    assert resp.status_code == 404
    assert "no resume with id 999" in resp.json()["detail"]


def test_patch_sections_roundtrip_marker(client, pdf):
    imported = _import(client, pdf, "Smith Resume")

    patch = {
        "sections": [
            {
                "kind": "contact",
                "position": 0,
                "content": {"name": {"v": "Ada", "uncertain": True}},
            }
        ]
    }
    resp = client.patch(f"/api/resumes/{imported['id']}/sections", json=patch)

    assert resp.status_code == 200
    assert resp.json()["revision"] == 2
    assert resp.json()["sections"][0]["content"]["name"] == {"v": "Ada", "uncertain": True}

    got = client.get(f"/api/resumes/{imported['id']}").json()
    assert got["sections"][0]["content"]["name"] == {"v": "Ada", "uncertain": True}


def test_patch_sections_unknown_id_404(client):
    resp = client.patch(
        "/api/resumes/999/sections",
        json={"sections": [{"kind": "summary", "position": 0, "content": {"text": "hi"}}]},
    )

    assert resp.status_code == 404


def test_patch_sections_unknown_kind_400(client, pdf):
    imported = _import(client, pdf, "Smith Resume")

    resp = client.patch(
        f"/api/resumes/{imported['id']}/sections",
        json={"sections": [{"kind": "bogus", "position": 0, "content": {"x": 1}}]},
    )

    assert resp.status_code == 400
    assert "unknown section kind" in resp.json()["detail"]


def test_activate_switches_active(client, pdf):
    first = _import(client, pdf, "First Resume")
    second = _import(client, pdf, "Second Resume")

    resp = client.post(f"/api/resumes/{first['id']}/activate")

    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    resp = client.post(f"/api/resumes/{second['id']}/activate")

    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    listed = client.get("/api/resumes").json()
    assert {r["name"]: r["is_active"] for r in listed} == {
        "First Resume": False,
        "Second Resume": True,
    }


def test_delete(client, pdf):
    first = _import(client, pdf, "First Resume")
    second = _import(client, pdf, "Second Resume")

    client.post(f"/api/resumes/{first['id']}/activate")

    resp = client.delete(f"/api/resumes/{first['id']}")

    assert resp.status_code == 409

    resp = client.delete(f"/api/resumes/{second['id']}")

    assert resp.status_code == 204

    resp = client.get(f"/api/resumes/{second['id']}")

    assert resp.status_code == 404
