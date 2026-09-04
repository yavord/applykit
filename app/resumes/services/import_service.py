"""Import orchestration: sniff, preserve, extract, parse, persist, clean up."""

from __future__ import annotations

from pathlib import Path

from app.data.models import Resume, SectionKind
from app.data.repositories import ResumeRepo
from app.paths import absolute_path
from app.resumes.extract import extract_text
from app.resumes.formats import preserve, sniff
from app.resumes.parse import parse

SECTION_ORDER = (
    SectionKind.CONTACT,
    SectionKind.SUMMARY,
    SectionKind.SKILLS,
    SectionKind.EXPERIENCE,
    SectionKind.EDUCATION,
    SectionKind.PROJECTS,
    SectionKind.CERTIFICATIONS,
)


def import_resume(source: Path, name: str | None = None) -> Resume:
    """Import a resume file: preserve the upload, extract and persist sections.

    Raises UnsupportedFormatError / ExtractionError / ValueError; on any
    failure after preservation the preserved copy is removed.
    """
    raw = source.read_bytes()
    kind = sniff(raw)

    rel = preserve(raw, kind)

    try:
        text = extract_text(source, kind)
        sections = [
            {"kind": p["kind"], "position": SECTION_ORDER.index(p["kind"]), "content": p["content"]}
            for p in parse(text)
        ]

        return ResumeRepo().create_from_import(
            name.strip() if name else source.stem.strip(), rel, kind, sections
        )
    except Exception:
        absolute_path(rel).unlink(missing_ok=True)
        raise
