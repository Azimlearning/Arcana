"""PDF parser — text extraction per page via PyMuPDF (FR-ING-01).

Returns one `PageText` per page (1-indexed) so chunking can attribute
each chunk back to its starting page for citation provenance.

Slice scope: text-only extraction. OCR for scanned PDFs (FR-ING-04) and
DOCX/web/YouTube parsers (FR-ING-02/03) land in P1 §1.1. A scanned PDF
will produce empty PageText for every page today — the pipeline records
that and marks the document `failed` via `IngestFailed`.
"""

from __future__ import annotations

from typing import cast

import pymupdf  # type: ignore[import-untyped]

from api.core.errors import IngestFailed
from api.ingestion.types import PageText


def parse(raw: bytes) -> list[PageText]:
    """Open a PDF byte string and return text per page (1-indexed).

    Raises `IngestFailed` if the bytes cannot be opened as a PDF.
    """
    if not raw:
        raise IngestFailed("empty PDF bytes")
    try:
        doc = pymupdf.open(stream=raw, filetype="pdf")
    except Exception as e:  # PyMuPDF raises various subtypes
        raise IngestFailed(f"could not open PDF: {e}") from e
    try:
        pages: list[PageText] = []
        # Iterate by index — PyMuPDF's Document type stubs don't declare
        # __iter__, which trips pyright on enumerate(doc).
        for i in range(doc.page_count):
            page = doc[i]
            # get_text() is union-typed (dict|list|str) but "text" always returns str.
            text = cast(str, page.get_text("text")) or ""
            pages.append(PageText(page=i + 1, text=text))
        return pages
    finally:
        doc.close()
