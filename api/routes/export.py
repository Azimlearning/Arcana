"""Export routes — bibliography (BibTeX/RIS) + report (PDF/DOCX). FR-EXP-01/02/08.

Builds a faithful export from the calling user's ingested sources. Responses
are file downloads (Content-Disposition: attachment). NFR-SEC-01: guarded by
get_current_user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from api.core.auth import CurrentUser, get_current_user
from api.core.logging import get_logger
from api.export.bibliography import CitationEntry, make_key, to_bibtex, to_ris
from api.export.document import build_docx, build_pdf

logger = get_logger(__name__)

router = APIRouter(prefix="/export", tags=["export"])

_DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _user_citations(http_request: Request) -> list[CitationEntry]:
    shared = getattr(http_request.app.state, "shared", {})
    doc_store = shared.get("doc_store")
    if doc_store is None:
        return []
    try:
        docs = await doc_store.list_documents()
    except Exception:
        logger.warning("export.list_documents_failed")
        return []

    entries: list[CitationEntry] = []
    for d in docs:
        created = getattr(d, "created_at", None)
        accessed = created.date().isoformat() if hasattr(created, "date") else str(created or "")[:10]
        entries.append(
            CitationEntry(
                key=make_key(d.id, d.title),
                title=d.title,
                url=d.source_uri,
                accessed=accessed,
            )
        )
    return entries


@router.get("/bibliography")
async def export_bibliography(
    http_request: Request,
    fmt: str = Query("bibtex", alias="format"),
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Export the corpus bibliography as BibTeX or RIS (FR-EXP-08)."""
    entries = await _user_citations(http_request)
    if fmt == "bibtex":
        body, media, ext = to_bibtex(entries), "application/x-bibtex", "bib"
    elif fmt == "ris":
        body, media, ext = to_ris(entries), "application/x-research-info-systems", "ris"
    else:
        raise HTTPException(status_code=422, detail="format must be 'bibtex' or 'ris'.")
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="arcana-bibliography.{ext}"'},
    )


@router.get("/report")
async def export_report(
    http_request: Request,
    fmt: str = Query("pdf", alias="format"),
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Export a source report as PDF or DOCX (FR-EXP-01/02)."""
    entries = await _user_citations(http_request)
    title = "Arcana — Source Report"
    lines: list[str] = [f"Sources ({len(entries)}):", ""]
    if entries:
        for e in entries:
            lines.append(f"- {e.title}")
            if e.url:
                lines.append(f"  {e.url}")
    else:
        lines.append("(no sources ingested yet)")

    if fmt == "pdf":
        data, media, ext = build_pdf(title, lines), "application/pdf", "pdf"
    elif fmt == "docx":
        data, media, ext = build_docx(title, lines), _DOCX_MEDIA, "docx"
    else:
        raise HTTPException(status_code=422, detail="format must be 'pdf' or 'docx'.")
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="arcana-report.{ext}"'},
    )
