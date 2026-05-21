"""PDF parser — text extraction round-trip, multi-page, error paths.

Tests build PDFs in-process via PyMuPDF so no binary fixtures ship.
"""

from __future__ import annotations

import pymupdf
import pytest

from api.core.errors import IngestFailed
from api.ingestion.parsers import pdf


def _build_pdf(pages_text: list[str]) -> bytes:
    doc = pymupdf.open()
    try:
        for text in pages_text:
            page = doc.new_page()
            page.insert_text((72, 72), text, fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()


def test_single_page_extraction():
    raw = _build_pdf(["Hello, Arcana."])
    pages = pdf.parse(raw)
    assert len(pages) == 1
    assert pages[0].page == 1
    assert "Hello, Arcana" in pages[0].text


def test_multipage_extraction_preserves_order():
    raw = _build_pdf(["First page body.", "Second page body.", "Third page body."])
    pages = pdf.parse(raw)
    assert [p.page for p in pages] == [1, 2, 3]
    assert "First page" in pages[0].text
    assert "Second page" in pages[1].text
    assert "Third page" in pages[2].text


def test_empty_bytes_raises_ingest_failed():
    with pytest.raises(IngestFailed):
        pdf.parse(b"")


def test_non_pdf_bytes_raises_ingest_failed():
    with pytest.raises(IngestFailed):
        pdf.parse(b"this is plain text, not a PDF")
