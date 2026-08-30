"""Text extraction drivers: turn a preserved file into newline-joined lines."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from docx.api import Document as open_document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.resumes.errors import ExtractionError, UnsupportedFormatError


def extract_text(source: Path, kind: str) -> str:
    """Extract newline-joined text lines from a pdf or docx file."""
    if kind == "pdf":
        return _extract_pdf(source)

    if kind == "docx":
        return _extract_docx(source)

    raise UnsupportedFormatError(f"unsupported file format: {kind}; supported formats: pdf, docx")


def _extract_pdf(source: Path) -> str:
    try:
        reader = PdfReader(str(source))

        if reader.is_encrypted:
            raise ExtractionError("password-protected pdf")

        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfReadError as e:
        raise ExtractionError(str(e)) from e


def _extract_docx(source: Path) -> str:
    doc = open_document(str(source))

    return "\n".join(_iter_docx_lines(doc))


def _iter_docx_lines(doc: DocxDocument) -> Iterator[str]:
    """Yield body text in document order: paragraphs and tables interleaved."""
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc).text
        elif isinstance(child, CT_Tbl):
            for row in Table(child, doc).rows:
                for cell in row.cells:
                    yield from (p.text for p in cell.paragraphs)
