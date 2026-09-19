"""Export service: render saved resumes and tailored documents to PDF/DOCX bytes.

All rendering is in-memory; exports are downloads, nothing touches disk.
Layout rules here are the contract between the generator, PDF, and DOCX:
sections normalize to the same block list, both renderers consume it
identically.
"""

import re
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape as xml_escape

import reportlab
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, ListFlowable, Paragraph, SimpleDocTemplate, Table

from app.data.models import DocKind, Section, SectionKind
from app.data.repositories import DocumentRepo
from app.resumes.errors import DocumentNotFoundError, SettingsError, UnprocessableError
from app.resumes.services.resume_service import get_resume, get_sections
from app.resumes.settings import (
    EducationOrder,
    ExportFormat,
    ExportSettings,
    FontFamily,
    HeaderAlign,
    SkillsLayout,
    bounds,
)

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

# Work Sans (OFL) is the default export face; the TTF PostScript names are
# WorkSans-Regular / WorkSans-Bold, referenced directly by the styles.
_VENDOR_FONT_DIR = Path(__file__).resolve().parent / "fonts"
_VENDOR_FONT_FILES = (
    ("WorkSans", "WorkSans-Regular.ttf"),
    ("WorkSans-Bold", "WorkSans-Bold.ttf"),
)

for _name, _file in _VENDOR_FONT_FILES:
    pdfmetrics.registerFont(TTFont(_name, str(_VENDOR_FONT_DIR / _file)))

# Register a family per regular face so <b> inline markup in paragraphs resolves.
# Times/Helvetica mappings match the reportlab built-ins; Work Sans has no
# vendored italic TTF, so italic falls back to the regular face.
for _name, _normal, _bold, _italic, _bold_italic in (
    ("Times-Roman", "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"),
    ("Helvetica", "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"),
    ("WorkSans", "WorkSans", "WorkSans-Bold", "WorkSans", "WorkSans-Bold"),
):
    pdfmetrics.registerFontFamily(
        _name, normal=_normal, bold=_bold, italic=_italic, boldItalic=_bold_italic
    )

# US Letter page width in points; reportlab and python-docx default to Letter.
_PAGE_WIDTH = 612

# SimpleDocTemplate Frame default inset on each side; paragraphs flow inside it.
_FRAME_PAD = 6


# (regular, bold, italic) reportlab face per family; TNR/Helvetica are base-14 built-ins.
def _faces(family: FontFamily) -> tuple[str, str, str]:
    return {
        FontFamily.WORK_SANS: ("WorkSans", "WorkSans-Bold", "WorkSans"),
        FontFamily.TIMES_NEW_ROMAN: ("Times-Roman", "Times-Bold", "Times-Italic"),
        FontFamily.HELVETICA: ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique"),
    }[family]


# Family name written into DOCX runs; the viewer substitutes when not installed.
_DOCX_FONTS = {
    FontFamily.WORK_SANS: "Work Sans",
    FontFamily.TIMES_NEW_ROMAN: "Times New Roman",
    FontFamily.HELVETICA: "Helvetica",
}

_PDF_ALIGN = {HeaderAlign.LEFT: TA_LEFT, HeaderAlign.CENTER: TA_CENTER, HeaderAlign.RIGHT: TA_RIGHT}
_DOCX_ALIGN = {
    HeaderAlign.LEFT: WD_ALIGN_PARAGRAPH.LEFT,
    HeaderAlign.CENTER: WD_ALIGN_PARAGRAPH.CENTER,
    HeaderAlign.RIGHT: WD_ALIGN_PARAGRAPH.RIGHT,
}

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
    header: bool = False
    label: str = ""  # bold run prefix; skills group name
    italic: bool = False  # role/degree line
    right: str = ""  # same-line right-aligned tail; dates


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


def _line(entry: dict, keys: tuple[str, ...], sep: str = " · ") -> str:
    """'location · 2020 – 2023 · GPA: 3.8' from the non-empty scalars of entry."""
    return sep.join(p for p in (_scalar(entry.get(k)) for k in keys) if p)


def _layout_contact(content) -> list[Block]:
    if not isinstance(content, dict):
        return []

    blocks: list[Block] = []

    if name := _scalar(content.get("name")):
        blocks.append(Block("h1", name, header=True))
    if subtitle := _scalar(content.get("subtitle")):
        blocks.append(Block("text", subtitle, header=True))

    # Scalars, then links with their bare URL (or name); one pipe-joined line.
    line = _line(content, ("location", "phone", "email"), sep=" | ")
    links = []
    for link in _items(content.get("links")):
        if not isinstance(link, dict):
            continue

        url, name = _scalar(link.get("url")), _scalar(link.get("name"))
        if part := (url or name):
            links.append(part)

    if links:
        line = " | ".join(p for p in (line, *links) if p)
    if line:
        blocks.append(Block("text", line, header=True))

    tags = [t for t in (_scalar(t) for t in _items(content.get("tags"))) if t]
    if tags:
        blocks.append(Block("text", ", ".join(tags), header=True))

    return blocks


def _layout_summary(content) -> list[Block]:
    if not isinstance(content, dict):
        return []

    text = _scalar(content.get("text"))
    if not text:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.SUMMARY]), Block("text", text)]


def _layout_skills(content, layout: SkillsLayout) -> list[Block]:
    blocks: list[Block] = []

    def skills_of(entry) -> list[str]:
        return [s for s in (_scalar(s) for s in _items(entry.get("skills"))) if s]

    if layout is SkillsLayout.GROUPED:
        for entry in _items(content):
            if not isinstance(entry, dict):
                continue

            group = _scalar(entry.get("group"))
            skills = skills_of(entry)

            if not group and not skills:
                continue

            if group:
                blocks.append(Block("text", ", ".join(skills), label=f"{group}: "))
            else:
                blocks.append(Block("text", ", ".join(skills)))
    else:
        # INLINE and COLUMN drop group labels; both keep every skill in order.
        skills = [
            s for entry in _items(content) if isinstance(entry, dict) for s in skills_of(entry)
        ]

        if layout is SkillsLayout.INLINE:
            if skills:
                blocks.append(Block("text", ", ".join(skills)))
        else:
            blocks.extend(Block("text", s) for s in skills)

    if not blocks:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.SKILLS]), *blocks]


def _layout_experience(content) -> list[Block]:
    blocks: list[Block] = []

    for entry in _items(content):
        if not isinstance(entry, dict):
            continue

        head = _scalar(entry.get("organization")) or _scalar(entry.get("title"))
        if head:
            dates = _range(entry.get("start"), entry.get("end"))
            blocks.append(Block("text", head, bold=True, right=dates))

        title = _scalar(entry.get("title"))
        if title and title != head:
            blocks.append(Block("text", title, italic=True))

        if location := _scalar(entry.get("location")):
            blocks.append(Block("text", location))

        if summary := _scalar(entry.get("summary")):
            blocks.append(Block("text", summary))

        blocks.extend(
            Block("bullet", b) for b in (_scalar(b) for b in _items(entry.get("bullets"))) if b
        )

    if not blocks:
        return []

    return [Block("h2", SECTION_LABELS[SectionKind.EXPERIENCE]), *blocks]


def _layout_education(content, order: EducationOrder) -> list[Block]:
    keys = (
        ("degree", "institution")
        if order is EducationOrder.DEGREE_FIRST
        else ("institution", "degree")
    )
    first, second = keys
    blocks: list[Block] = []

    for entry in _items(content):
        if not isinstance(entry, dict):
            continue

        head = _scalar(entry.get(first)) or _scalar(entry.get(second))
        if head:
            dates = _range(entry.get("start"), entry.get("end"))
            blocks.append(Block("text", head, bold=True, right=dates))

        other = _scalar(entry.get(second))
        if other and other != head:
            blocks.append(Block("text", other, italic=True))

        gpa = _scalar(entry.get("gpa"))
        parts = [_scalar(entry.get("location"))]
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
    SectionKind.EXPERIENCE: _layout_experience,
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


def _layout(sections, settings: ExportSettings) -> list[Block]:
    """Normalize section rows/dicts into blocks; unknown kinds and blanks dropped."""
    blocks: list[Block] = []

    for kind, _, content in sorted(
        (f for f in (_section_fields(s) for s in sections) if f is not None),
        key=lambda f: f[1],
    ):
        if kind == SectionKind.EDUCATION:
            blocks.extend(_layout_education(content, settings.education_order))
        elif kind == SectionKind.SKILLS:
            blocks.extend(_layout_skills(content, settings.skills_layout))
        elif layout := _LAYOUTS.get(kind):
            blocks.extend(layout(content))

    return blocks


def _pdf_style(  # noqa: PLR0913  (maps 1:1 to ParagraphStyle fields)
    name, font, size, leading, *, space_before=0, alignment=TA_LEFT
) -> ParagraphStyle:
    return ParagraphStyle(
        name,
        fontName=font,
        fontSize=size,
        leading=leading,
        spaceBefore=space_before,
        alignment=alignment,
    )


def render_pdf(blocks: list[Block], title: str, settings: ExportSettings) -> bytes:
    """Render blocks to PDF bytes (drawer settings drive fonts and sizes)."""
    regular, bold, italic = _faces(settings.font_family)
    line = settings.line_spacing / 10

    h1 = _pdf_style(
        "h1",
        bold,
        settings.name_size,
        settings.name_size * line,
        alignment=_PDF_ALIGN[settings.header_align],
    )
    h2 = _pdf_style(
        "h2",
        bold,
        settings.header_size,
        settings.header_size * line,
        space_before=settings.section_spacing,
    )
    entry = _pdf_style(
        "entry",
        bold,
        settings.subheader_size,
        settings.subheader_size * line,
        space_before=settings.entry_spacing,
    )
    role = _pdf_style("role", italic, settings.body_size, settings.body_size * line)
    justify = TA_JUSTIFY if settings.align_justify else TA_LEFT
    body = _pdf_style(
        "body", regular, settings.body_size, settings.body_size * line, alignment=justify
    )
    contact = _pdf_style(
        "contact",
        regular,
        settings.body_size,
        settings.body_size * line,
        alignment=_PDF_ALIGN[settings.header_align],
    )
    bullet = _pdf_style(
        "bullet", regular, settings.body_size, settings.body_size * line, alignment=justify
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        title=title,
        leftMargin=settings.margin_side,
        rightMargin=settings.margin_side,
        topMargin=settings.margin_top,
        bottomMargin=settings.margin_bottom,
    )

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
                    bulletFontName=regular,
                    bulletFontSize=settings.body_size,
                )
            )
            pending_bullets.clear()

    for block in blocks:
        text = xml_escape(block.text)

        if block.kind == "h1":
            flush_bullets()
            story.append(Paragraph(text, h1))
        elif block.kind == "h2":
            flush_bullets()
            story.append(Paragraph(text, h2))
            story.append(
                HRFlowable(
                    width="100%", thickness=0.5, color=colors.black, spaceBefore=0, spaceAfter=1
                )
            )
        elif block.kind == "bullet":
            pending_bullets.append(Paragraph(text, bullet))
        elif block.label:
            flush_bullets()
            story.append(Paragraph(f"<b>{xml_escape(block.label)}</b>{text}", body))
        elif block.right:
            flush_bullets()
            # One row, org left and dates right, both bold; reportlab has no tab
            # stops (the tab char is whitespace), so a padding-less table pins
            # the dates flush to the right text edge on the same baseline row.
            avail = _PAGE_WIDTH - 2 * settings.margin_side - 2 * _FRAME_PAD
            dates_w = pdfmetrics.stringWidth(block.right, bold, settings.subheader_size)
            dates_cell = ParagraphStyle(
                "entry-right",
                fontName=bold,
                fontSize=settings.subheader_size,
                leading=settings.subheader_size * line,
                alignment=TA_RIGHT,
            )
            story.append(
                Table(
                    [[Paragraph(text, entry), Paragraph(xml_escape(block.right), dates_cell)]],
                    colWidths=[max(avail - dates_w, 0), min(dates_w, avail)],
                    hAlign="LEFT",
                    style=[
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                    ],
                )
            )
        elif block.italic:
            flush_bullets()
            story.append(Paragraph(text, role))
        elif block.header:
            flush_bullets()
            story.append(Paragraph(text, contact))
        elif block.bold:
            flush_bullets()
            story.append(Paragraph(text, entry))
        else:
            flush_bullets()
            story.append(Paragraph(text, body))

    flush_bullets()
    doc.build(story)

    return buf.getvalue()


def render_docx(blocks: list[Block], settings: ExportSettings) -> bytes:
    """Render blocks to DOCX bytes (drawer settings drive fonts and sizes)."""
    document = Document()
    section = document.sections[0]
    section.top_margin = Pt(settings.margin_top)
    section.bottom_margin = Pt(settings.margin_bottom)
    section.left_margin = Pt(settings.margin_side)
    section.right_margin = Pt(settings.margin_side)
    family = _DOCX_FONTS[settings.font_family]
    line = settings.line_spacing / 10
    justify = WD_ALIGN_PARAGRAPH.JUSTIFY if settings.align_justify else WD_ALIGN_PARAGRAPH.LEFT

    for block in blocks:
        if block.kind == "h1":
            p = document.add_heading(block.text, level=0)
            run = p.runs[0]
            run.font.name = family
            run.font.size = Pt(settings.name_size)
            run.bold = True
            p.paragraph_format.alignment = _DOCX_ALIGN[settings.header_align]
        elif block.kind == "h2":
            p = document.add_heading(block.text, level=1)
            run = p.runs[0]
            run.font.name = family
            run.font.size = Pt(settings.header_size)
            run.bold = True
            p.paragraph_format.space_before = Pt(settings.section_spacing)
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

            # 0.5 pt black rule under the heading; mirrors the PDF HRFlowable.
            pPr = p._p.get_or_add_pPr()
            pBdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "4")
            bottom.set(qn("w:space"), "1")
            bottom.set(qn("w:color"), "000000")
            pBdr.append(bottom)
            pPr.append(pBdr)
        elif block.kind == "bullet":
            p = document.add_paragraph(block.text, style="List Bullet")
            run = p.runs[0]
            run.font.name = family
            run.font.size = Pt(settings.body_size)
            p.paragraph_format.alignment = justify
        elif block.label:
            p = document.add_paragraph()
            label_run = p.add_run(block.label)
            label_run.bold = True
            label_run.font.name = family
            label_run.font.size = Pt(settings.body_size)
            run = p.add_run(block.text)
            run.font.name = family
            run.font.size = Pt(settings.body_size)
            p.paragraph_format.alignment = justify
        elif block.italic:
            p = document.add_paragraph()
            run = p.add_run(block.text)
            run.font.name = family
            run.font.size = Pt(settings.body_size)
            run.italic = True
        elif block.header:
            p = document.add_paragraph()
            run = p.add_run(block.text)
            run.font.name = family
            run.font.size = Pt(settings.body_size)
            p.paragraph_format.alignment = _DOCX_ALIGN[settings.header_align]
        elif block.bold:
            p = document.add_paragraph()
            run = p.add_run(block.text)
            run.font.name = family
            run.font.size = Pt(settings.subheader_size)
            run.bold = True
            if block.right:
                run.add_text("\t" + block.right)
                p.paragraph_format.tab_stops.add_tab_stop(
                    section.page_width - section.left_margin - section.right_margin,
                    WD_TAB_ALIGNMENT.RIGHT,
                )
            p.paragraph_format.space_before = Pt(settings.entry_spacing)
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        else:
            p = document.add_paragraph()
            run = p.add_run(block.text)
            run.font.name = family
            run.font.size = Pt(settings.body_size)
            p.paragraph_format.alignment = justify

        p.paragraph_format.line_spacing = line

    buf = BytesIO()
    document.save(buf)

    return buf.getvalue()


def _render(blocks: list[Block], fmt: str, title: str, settings: ExportSettings) -> bytes:
    if fmt == "pdf":
        return render_pdf(blocks, title, settings)
    if fmt == "docx":
        return render_docx(blocks, settings)

    raise ValueError(f"unsupported export format: {fmt}")


def _require_pdf(settings: ExportSettings) -> None:
    """Page counting/fitting only make sense for PDF; DOCX layout is viewer-dependent."""
    if settings.format is ExportFormat.DOCX:
        raise SettingsError("page count and fit require format=pdf")


def _pdf_pages(body: bytes) -> int:
    """Page count of rendered PDF bytes."""
    return len(PdfReader(BytesIO(body)).pages)


def count_resume_pages(resume_id: int, settings: ExportSettings) -> int:
    """PDF pages a saved resume occupies under settings; 404 unknown id, 422 docx."""
    _require_pdf(settings)
    resume = get_resume(resume_id)

    return _pdf_pages(render_pdf(_layout(get_sections(resume_id), settings), resume.name, settings))


@dataclass(frozen=True, slots=True)
class FitResult:
    """Settings keeping the resume on one PDF page; pages is the count under .settings."""

    settings: ExportSettings
    pages: int


# Cheapest visual damage first; each field descends one unit to its contract
# floor, re-rendering until the resume fits on one page.
_FIT_LADDER: tuple[str, ...] = (
    "line_spacing",
    "margin_top",
    "margin_bottom",
    "margin_side",
    "body_size",
    "subheader_size",
    "header_size",
    "name_size",
)

# Under-full nudges in application order: the body inches first and takes the
# first claim on room (it fills the page), spacing strides after. Other sizes
# are untouched; bounds are checked per knob at apply time.
_FILL_BUMPS: tuple[tuple[str, int], ...] = (
    ("body_size", 1),
    ("entry_spacing", 2),
    ("section_spacing", 2),
    ("line_spacing", 2),
)

# The frame opens one-way; smaller margins only shorten lines, never overflow.
_FILL_MARGINS: tuple[str, ...] = ("margin_top", "margin_bottom", "margin_side")


def fit_resume(resume_id: int, settings: ExportSettings) -> FitResult:
    """One-page settings: shrink on overflow, nudge spacing, body, and frame when it fits."""
    _require_pdf(settings)
    resume = get_resume(resume_id)
    blocks = _layout(get_sections(resume_id), settings)  # ladder touches no layout field

    def pages(s: ExportSettings) -> int:
        return _pdf_pages(render_pdf(blocks, resume.name, s))

    current, count = settings, pages(settings)

    for field in _FIT_LADDER:
        floor = bounds(field)[0]

        while count > 1 and getattr(current, field) > floor:
            current = replace(current, **{field: getattr(current, field) - 1})
            count = pages(current)

    if count > 1:
        return FitResult(current, count)

    # Fits with room: open the frame first (narrower margins only shorten lines,
    # so candidates are judged in the roomy frame), then nudge each knob up,
    # reverting any bump that spills to a second page.
    for field in _FILL_MARGINS:
        lo, _ = bounds(field)
        if getattr(current, field) > lo:
            current = replace(current, **{field: lo})

    for field, amplitude in _FILL_BUMPS:
        value = getattr(current, field)
        _, hi = bounds(field)
        step = min(amplitude, hi - value)
        while step >= 1:
            candidate = replace(current, **{field: value + step})
            if pages(candidate) == 1:
                current = candidate
                break
            step -= 1

    return FitResult(current, 1)


def export_resume(resume_id: int, fmt: str, settings: ExportSettings | None = None) -> bytes:
    """Saved base resume rendered to fmt bytes; 404 unknown id."""
    resume = get_resume(resume_id)
    settings = settings or ExportSettings()

    return _render(_layout(get_sections(resume_id), settings), fmt, resume.name, settings)


def export_revision(doc_id: int, fmt: str, settings: ExportSettings | None = None) -> bytes:
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

    return _render(
        _layout(sections, settings or ExportSettings()),
        fmt,
        resume.name,
        settings or ExportSettings(),
    )


def download_name(
    name: str, fmt: str, *, revision: int | None = None, doc_id: int | None = None
) -> str:
    """Attachment filename: '<slug>-rev<N>.<fmt>' or '<slug>-tailored-<id>.<fmt>'."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-") or "resume"

    if doc_id is not None:
        return f"{slug}-tailored-{doc_id}.{fmt}"

    return f"{slug}-rev{revision}.{fmt}"
