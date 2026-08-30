"""Import service: extraction, preservation, rejection, cleanup."""

from pathlib import Path

import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.data.models import Resume
from app.data.repositories import ResumeRepo
from app.paths import absolute_path, uploads_dir
from app.resumes import ExtractionError, UnsupportedFormatError, import_resume

MARKER = {"v": "", "uncertain": True}

REPO_DATA = Path(__file__).resolve().parents[1] / "data"
REAL_TXT = REPO_DATA / "sample_cv.txt"

# Canonical fixture resume: contact, summary, skills, two employers, education,
# projects, certifications (mirrors acceptance scenario 1).
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


def write_docx(path: Path, lines: list[str]) -> None:
    doc = DocxDocument()

    for line in lines:
        doc.add_paragraph(line)

    doc.save(str(path))


@pytest.fixture(params=["pdf", "docx"])
def sample_source(tmp_path, request):
    path = tmp_path / f"resume.{request.param}"

    if request.param == "pdf":
        write_pdf(path, SAMPLE_LINES)
    else:
        write_docx(path, SAMPLE_LINES)

    return path


@pytest.fixture
def repo():
    return ResumeRepo()


def _sections(resume_id: int) -> dict[str, dict | list]:
    return {s.kind: s.content for s in ResumeRepo().sections(resume_id)}


def test_import_extracts_all_sections(sample_source):
    resume = import_resume(sample_source)
    stored = _sections(resume.id)

    assert list(stored) == [
        "contact",
        "summary",
        "skills",
        "experience",
        "education",
        "projects",
        "certifications",
    ]

    contact = stored["contact"]
    assert contact["name"] == "Jane Q. Developer"
    assert contact["subtitle"] == "Senior Backend Engineer"
    assert contact["email"] == "jane.q@example.com"
    assert contact["phone"] == "(415) 555-0132"
    assert contact["location"] == "San Francisco, CA"
    assert contact["links"] == [{"name": "LinkedIn", "url": "linkedin.com/in/janeq"}]

    assert stored["summary"] == {
        "text": "Experienced backend engineer with 8 years building distributed systems."
    }

    assert stored["skills"] == [
        {"group": "Languages", "skills": ["Python", "SQL", "TypeScript"]},
        {"group": MARKER, "skills": ["AWS", "Docker", "PostgreSQL"]},
    ]

    experience = stored["experience"]
    assert len(experience) == 2
    assert experience[0]["title"] == "Senior Backend Engineer"
    assert experience[0]["organization"] == "Acme Corp"
    assert experience[0]["start"] == "2020"
    assert experience[0]["end"] == "2023"
    assert experience[0]["bullets"] == [
        "Built migration pipeline serving 2M users",
        "Cut p95 latency by 40%",
    ]
    assert experience[1]["title"] == "Backend Engineer"
    assert experience[1]["organization"] == "Globex Inc"
    assert experience[1]["start"] == "2016"
    assert experience[1]["end"] == "2020"
    assert experience[1]["bullets"] == ["Shipped billing rewrite"]

    education = stored["education"]
    assert education == [
        {
            "degree": "B.S. Computer Science",
            "institution": "State University",
            "location": MARKER,
            "start": "2012",
            "end": "2016",
            "gpa": "3.8",
            "achievements": [],
            "coursework": [],
        }
    ]

    assert stored["projects"] == [
        {
            "title": "Resume Parser",
            "organization": "personal",
            "dates": "2023 - 2024",
            "url": MARKER,
            "bullets": ["Extracts structured resumes from raw text"],
        }
    ]

    assert stored["certifications"] == [
        {
            "name": "AWS Certified Solutions Architect - Associate",
            "issuer": "Amazon Web Services",
            "date": "2024",
            "url": MARKER,
        }
    ]

    assert ResumeRepo().revision(resume.id) == 1


def test_import_preserves_original_bytes(sample_source):
    resume = import_resume(sample_source)

    assert resume.source_kind in ("pdf", "docx")
    assert resume.source_path is not None
    assert resume.source_path.startswith("uploads/")

    preserved = absolute_path(resume.source_path)

    assert preserved.exists()
    assert preserved.read_bytes() == sample_source.read_bytes()


def test_unsupported_extension_rejected_recoverably(tmp_path, session):
    path = tmp_path / "resume.txt"
    path.write_text("Just text, nothing magic.")

    with pytest.raises(UnsupportedFormatError, match="pdf, docx"):
        import_resume(path)

    assert session.scalars(select(Resume)).all() == []
    assert list(uploads_dir().iterdir()) == []


def test_magic_based_rejection(tmp_path, session):
    path = tmp_path / "fake.pdf"
    path.write_text("Not a real pdf despite the extension.")

    with pytest.raises(UnsupportedFormatError):
        import_resume(path)

    assert session.scalars(select(Resume)).all() == []


def test_corrupt_pdf_extraction_error(tmp_path, session):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.7\n<garbage>")

    with pytest.raises(ExtractionError):
        import_resume(path)

    assert session.scalars(select(Resume)).all() == []
    assert list(uploads_dir().iterdir()) == []


def test_password_protected_pdf_rejected(tmp_path, session):
    path = tmp_path / "locked.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("pw")

    with open(path, "wb") as f:
        writer.write(f)

    with pytest.raises(ExtractionError, match="password"):
        import_resume(path)

    assert session.scalars(select(Resume)).all() == []
    assert list(uploads_dir().iterdir()) == []


def test_duplicate_stem_import_rejected(sample_source, session):
    import_resume(sample_source)

    with pytest.raises(ValueError, match="already exists"):
        import_resume(sample_source)

    assert len(session.scalars(select(Resume)).all()) == 1
    assert len(list(uploads_dir().iterdir())) == 1


def test_missing_contact_fields_marked_uncertain(tmp_path):
    path = tmp_path / "minimal.pdf"
    write_pdf(path, ["Jane Q. Developer", "SUMMARY", "Lives somewhere."])

    contact = _sections(import_resume(path).id)["contact"]

    assert contact["name"] == "Jane Q. Developer"
    assert contact["email"] == MARKER
    assert contact["phone"] == MARKER
    assert contact["location"] == MARKER


def test_name_explicit_override(sample_source):
    resume = import_resume(sample_source, name="Custom")

    assert resume.name == "Custom"



@pytest.mark.skipif(not REAL_TXT.exists(), reason="real CV text not present")
def test_import_real_txt_rejected(session):
    with pytest.raises(UnsupportedFormatError):
        import_resume(REAL_TXT)

    assert session.scalars(select(Resume)).all() == []
    assert list(uploads_dir().iterdir()) == []
