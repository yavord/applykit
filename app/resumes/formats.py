"""File mechanics driver: sniff format and preserve raw uploads.

No DB and no parsing here (layered boundary); callers work with kinds and
relative paths under the data root.
"""

from __future__ import annotations

import io
import zipfile
from uuid import uuid4

from app.paths import data_root, uploads_dir
from app.resumes.errors import UnsupportedFormatError

SUPPORTED_KINDS = ("pdf", "docx")
SUFFIXES = {"pdf": ".pdf", "docx": ".docx"}

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"
_DOCX_BODY = "word/document.xml"


def sniff(raw: bytes) -> str:
    """Return the detected kind ("pdf" | "docx") or raise UnsupportedFormatError."""
    if not raw:
        raise UnsupportedFormatError(
            "unsupported file format: empty file; supported formats: pdf, docx"
        )

    if raw.startswith(_PDF_MAGIC):
        return "pdf"

    if raw.startswith(_ZIP_MAGIC):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if _DOCX_BODY in archive.namelist():
                return "docx"

        raise UnsupportedFormatError(
            "unsupported file format: not a docx archive; supported formats: pdf, docx"
        )

    raise UnsupportedFormatError(
        "unsupported file format: unrecognized header; supported formats: pdf, docx"
    )


def preserve(raw: bytes, kind: str) -> str:
    """Write raw bytes to uploads/; return the path relative to the data root."""
    upload_path = uploads_dir() / f"{uuid4().hex}{SUFFIXES[kind]}"

    _ = upload_path.write_bytes(raw)

    return upload_path.relative_to(data_root()).as_posix()
