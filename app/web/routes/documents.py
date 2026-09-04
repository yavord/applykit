"""Document HTTP endpoints: export generated documents."""

from typing import Literal

from fastapi import APIRouter, Response

from app.data.repositories import DocumentRepo
from app.resumes.services.export_service import MIME, download_name, export_revision
from app.resumes.services.resume_service import get_resume

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{doc_id}/export.{fmt}", response_class=Response)
def export_document_route(doc_id: int, fmt: Literal["pdf", "docx"]) -> Response:
    """Download a tailored-resume document as PDF or DOCX; 404/422."""
    body = export_revision(doc_id, fmt)  # 404/422 raised here

    doc = DocumentRepo().get(doc_id)  # exists here by construction
    resume = get_resume(doc.resume_id)

    return Response(
        content=body,
        media_type=MIME[fmt],
        headers={
            "Content-Disposition": (
                f'attachment; filename="{download_name(resume.name, fmt, doc_id=doc_id)}"'
            )
        },
    )
