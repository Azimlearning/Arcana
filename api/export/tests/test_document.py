"""Document export — stdlib PDF + DOCX writers (FR-EXP-01/02)."""

from __future__ import annotations

import io
import zipfile

from api.export.document import build_docx, build_pdf


def test_docx_is_valid_zip_with_escaped_text():
    data = build_docx("My Report", ["line one", "A & B < C > D"])
    z = zipfile.ZipFile(io.BytesIO(data))
    assert set(z.namelist()) == {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
    doc = z.read("word/document.xml")
    assert b"My Report" in doc
    assert b"line one" in doc
    assert b"A &amp; B &lt; C &gt; D" in doc  # XML-escaped


def test_pdf_has_valid_structure_and_escaped_text():
    data = build_pdf("My Report", ["hello (world)", "second line"])
    assert data.startswith(b"%PDF-1.4")
    assert data.rstrip().endswith(b"%%EOF")
    assert b"xref" in data and b"startxref" in data and b"trailer" in data
    # Parenthesis escaped in the content stream.
    assert b"hello " + bytes([92]) + b"(world" in data
    assert b"My Report" in data


def test_pdf_truncates_to_single_page_without_error():
    data = build_pdf("T", [f"line {i}" for i in range(200)])
    assert data.startswith(b"%PDF")
    assert data.rstrip().endswith(b"%%EOF")
