"""Export service: render saved resumes and tailored documents to PDF/DOCX bytes.

All rendering is in-memory; exports are downloads, nothing touches disk.
Layout rules here are the contract between the generator, PDF, and DOCX:
sections normalize to the same block list, both renderers consume it
identically.
"""

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape as xml_escape

import reportlab
from docx import Document
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import ListFlowable, Paragraph, SimpleDocTemplate

from app.data.models import DocKind, Section, SectionKind
from app.data.repositories import DocumentRepo
from app.resumes.errors import DocumentNotFoundError, UnprocessableError
from app.resumes.services.resume_service import get_resume, get_sections

EXPORT_FORMATS = ("pdf", "docx")
MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Bundled Vera covers Latin/Cyrillic/Greek; missing glyphs render as .notdef.
_FONT_DIR = Path(reportlab.__file__).resolve().parent / "fonts"
_FONT_FILES = (
    ("Vera", "Vera.ttf"),
    ("Vera-Bold", "VeraBd.ttf"),
    ("Vera-Italic", "VeraIt.ttf"),
    ("Vera-BoldItalic", "VeraBI.ttf"),
)

for _name, _file in _FONT_FILES:
    pdfmetrics.registerFont(TTFont(_name, str(_FONT_DIR / _file)))

pdfmetrics.registerFontFamily(
    "Vera", normal="Vera", bold="Vera-Bold", italic="Vera-Italic", boldItalic="Vera-BoldItalic"
)

# Section headings; parity with the editor labels.
SECTION_LABELS = {
    SectionKind.SUMMARY: "Summary",
    SectionKind.SKILLS: "Skills",
    SectionKind.EXPERIENCE: "Work Experience",
    SectionKind.EDUCATION: "Education",
    SectionKind.PROJECTS: "Projects",
    SectionKind.CERTIFICATIONS: "Certifications",
}


@dataclass
class Block:
    """One normalized render unit; PDF and DOCX share this list."""

    kind: Literal["h1", "h2", "text", "bullet"]
    text: str
    bold: bool = False


def _scalar(v) -> str:
    """Stored scalar as text; uncertainty markers unwrap to their value."""
    if v is None:
        return ""
    raw = v["v"] if isinstance(v, dict) else v
    return str(raw)


def _items(value) -> list:
    """Stored list value, or empty for anything unexpected."""
    return value if isinstance(value, list) else []


def _range(start, end) -> str:
    """'2020 – 2023' from either bound; empty when both are missing."""
    parts = [p for p in (_scalar(start), _scalar(end)) if p]

    return " – ".join(parts)


def _heading(entry: dict, keys: tuple[str, ...]) -> str:
    """'title — organization' from the non-empty scalars of entry."""
    return " — ".join(p for p in (_scalar(entry.get(k)) for k in keys) if p)


def _line(entry: dict, keys: tuple[str, ...]) -> str:
    """'location · 2020 – 2023 · GPA: 3.8' from the non-empty scalars of entry."""
    return " · ".join(p for p in (_scalar(entry.get(k)) for k in keys) if p)


def _layout_contact(content) -> list[Block]:
    if not isinstance(content, dict):
        return []

    blocks: list[Block] = []

    if name := _scalar(content.get("name")):
        blocks.append(Block("h1", name))
    if subtitle := _scalar(content.get("subtitle")):
        blocks.append(Block("text", subtitle))

    line = _line(content, ("email", "phone", "location"))
    if line:
        blocks.append(Block("text", line))

    tags = [t for t in (_scalar(t) for t in _items(content.get("tags"))) if t]
    if tags:
        blocks.append(Block("text", ", ".join(tags)))

    for link in _items(content.get("links")):
        if not isinstance(link, dict):
            continue

        name, url = _scalar(link.get("name")), _scalar(link.get("url"))
        if name and url:
            blocks.append(Block("text", f"{name} ({url})"))
        elif name or url:
            blocks.append(Block("text", name or url))

    return blocks


def _layout_summary(content) -> list[Block]:
    if not isinstance(content, dict):
        return []

    text = _scalar(content.get("text"))
    if not text:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.SUMMARY]), Block("text", text)]


def _layout_skills(content) -> list[Block]:
    blocks: list[Block] = []

    for entry in _items(content):
        if not isinstance(entry, dict):
            continue

        group = _scalar(entry.get("group"))
        skills = [s for s in (_scalar(s) for s in _items(entry.get("skills"))) if s]

        if not group and not skills:
            continue

        body = f"{group}: {', '.join(skills)}" if group else ", ".join(skills)
        blocks.append(Block("text", body))

    if not blocks:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.SKILLS]), *blocks]


def _layout_experience(content) -> list[Block]:
    blocks: list[Block] = []

    for entry in _items(content):
        if not isinstance(entry, dict):
            continue

        if heading := _heading(entry, ("title", "organization")):
            blocks.append(Block("text", heading, bold=True))

        line = " · ".join(
            p
            for p in (_scalar(entry.get("location")), _range(entry.get("start"), entry.get("end")))
            if p
        )
        if line:
            blocks.append(Block("text", line))

        if summary := _scalar(entry.get("summary")):
            blocks.append(Block("text", summary))

        blocks.extend(
            Block("bullet", b) for b in (_scalar(b) for b in _items(entry.get("bullets"))) if b
        )

    if not blocks:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.EXPERIENCE]), *blocks]


def _layout_education(content) -> list[Block]:
    blocks: list[Block] = []

    for entry in _items(content):
        if not isinstance(entry, dict):
            continue

        if heading := _heading(entry, ("degree", "institution")):
            blocks.append(Block("text", heading, bold=True))

        gpa = _scalar(entry.get("gpa"))
        parts = [_scalar(entry.get("location")), _range(entry.get("start"), entry.get("end"))]
        if gpa:
            parts.append(f"GPA: {gpa}")

        line = " · ".join(p for p in parts if p)
        if line:
            blocks.append(Block("text", line))

        blocks.extend(
            Block("bullet", a) for a in (_scalar(a) for a in _items(entry.get("achievements"))) if a
        )

        coursework = [c for c in (_scalar(c) for c in _items(entry.get("coursework"))) if c]
        if coursework:
            blocks.append(Block("text", ", ".join(coursework)))

    if not blocks:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.EDUCATION]), *blocks]


def _layout_projects(content) -> list[Block]:
    blocks: list[Block] = []

    for entry in _items(content):
        if not isinstance(entry, dict):
            continue

        if heading := _heading(entry, ("title", "organization")):
            blocks.append(Block("text", heading, bold=True))

        line = _line(entry, ("dates", "url"))
        if line:
            blocks.append(Block("text", line))

        blocks.extend(
            Block("bullet", b) for b in (_scalar(b) for b in _items(entry.get("bullets"))) if b
        )

    if not blocks:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.PROJECTS]), *blocks]


def _layout_certifications(content) -> list[Block]:
    blocks: list[Block] = []

    for entry in _items(content):
        if not isinstance(entry, dict):
            continue

        if not (name := _scalar(entry.get("name"))):
            continue

        blocks.append(Block("text", name, bold=True))

        line = _line(entry, ("issuer", "date", "url"))
        if line:
            blocks.append(Block("text", line))

    if not blocks:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.CERTIFICATIONS]), *blocks]


_LAYOUTS = {
    SectionKind.CONTACT: _layout_contact,
    SectionKind.SUMMARY: _layout_summary,
    SectionKind.SKILLS: _layout_skills,
    SectionKind.EXPERIENCE: _layout_experience,
    SectionKind.EDUCATION: _layout_education,
    SectionKind.PROJECTS: _layout_projects,
    SectionKind.CERTIFICATIONS: _layout_certifications,
}


def _section_fields(sec) -> tuple[str, int, object] | None:
    """kind, position, content from an ORM Section or dict; None when malformed."""
    if isinstance(sec, Section):
        return sec.kind, sec.position, sec.content

    if not isinstance(sec, dict):
        return None

    return sec.get("kind"), sec.get("position"), sec.get("content")


def _layout(sections) -> list[Block]:
    """Normalize section rows/dicts into blocks; unknown kinds and blanks dropped."""
    blocks: list[Block] = []

    for kind, _, content in sorted(
        (f for f in (_section_fields(s) for s in sections) if f is not None),
        key=lambda f: f[1],
    ):
        if layout := _LAYOUTS.get(kind):
            blocks.extend(layout(content))

    return blocks


def _pdf_style(name: str, font: str, size: int, *, space_before: int = 0) -> ParagraphStyle:
    return ParagraphStyle(
        name, fontName=font, fontSize=size, leading=size + 4, spaceBefore=space_before
    )


def render_pdf(blocks: list[Block], title: str) -> bytes:
    """Render blocks to PDF bytes (Vera, A4)."""
    h1 = _pdf_style("h1", "Vera-Bold", 20, space_before=0)
    h2 = _pdf_style("h2", "Vera-Bold", 12, space_before=10)
    body = _pdf_style("body", "Vera", 10)
    bullet = _pdf_style("bullet", "Vera", 10)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, title=title)

    story: list = []
    pending_bullets: list[Paragraph] = []

    def flush_bullets() -> None:
        if pending_bullets:
            # Copy: ListFlowable consumes the list lazily at build time.
            story.append(
                ListFlowable(
                    list(pending_bullets),
                    bulletType="bullet",
                    start="•",
                    bulletFontName="Vera",
                    bulletFontSize=10,
                )
            )
            pending_bullets.clear()

    for block in blocks:
        text = xml_escape(block.text)
        styled = f"<b>{text}</b>" if block.bold else text

        if block.kind == "h1":
            flush_bullets()
            story.append(Paragraph(text, h1))
        elif block.kind == "h2":
            flush_bullets()
            story.append(Paragraph(text, h2))
        elif block.kind == "bullet":
            pending_bullets.append(Paragraph(styled, bullet))
        else:
            flush_bullets()
            story.append(Paragraph(styled, body))

    flush_bullets()
    doc.build(story)

    return buf.getvalue()


def render_docx(blocks: list[Block]) -> bytes:
    """Render blocks to DOCX bytes."""
    document = Document()

    for block in blocks:
        if block.kind == "h1":
            document.add_heading(block.text, level=0)
        elif block.kind == "h2":
            document.add_heading(block.text, level=1)
        elif block.kind == "bullet":
            document.add_paragraph(block.text, style="List Bullet")
        else:
            p = document.add_paragraph()
            run = p.add_run(block.text)
            run.bold = block.bold

    buf = BytesIO()
    document.save(buf)

    return buf.getvalue()


def _render(blocks: list[Block], fmt: str, title: str) -> bytes:
    if fmt == "pdf":
        return render_pdf(blocks, title)
    if fmt == "docx":
        return render_docx(blocks)

    raise ValueError(f"unsupported export format: {fmt}")


def export_resume(resume_id: int, fmt: str) -> bytes:
    """Saved base resume rendered to fmt bytes; 404 unknown id."""
    resume = get_resume(resume_id)

    return _render(_layout(get_sections(resume_id)), fmt, resume.name)


def export_revision(doc_id: int, fmt: str) -> bytes:
    """Tailored-resume document rendered to fmt bytes; 404 no doc, 422 wrong kind/shape."""
    doc = DocumentRepo().get(doc_id)

    if doc is None:
        raise DocumentNotFoundError(f"no document with id {doc_id}")

    if doc.kind != DocKind.TAILORED_RESUME:
        raise UnprocessableError(f"document {doc_id} is not a tailored resume")

    sections = doc.content.get("sections") if isinstance(doc.content, dict) else None
    if not isinstance(sections, list):
        raise UnprocessableError(f"document {doc_id} has no exportable sections")

    resume = get_resume(doc.resume_id)  # docs cascade on resume delete; belt-and-braces 404

    return _render(_layout(sections), fmt, resume.name)


def download_name(
    name: str, fmt: str, *, revision: int | None = None, doc_id: int | None = None
) -> str:
    """Attachment filename: '<slug>-rev<N>.<fmt>' or '<slug>-tailored-<id>.<fmt>'."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-") or "resume"

    if doc_id is not None:
        return f"{slug}-tailored-{doc_id}.{fmt}"

    return f"{slug}-rev{revision}.{fmt}"
