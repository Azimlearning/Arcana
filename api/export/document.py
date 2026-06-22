"""Document export — PDF + DOCX built from the standard library (FR-EXP-01/02).

No third-party dependency: DOCX is a zip of minimal WordprocessingML; PDF is
a hand-assembled single-page document with a byte-accurate xref table. Both
take a title + a list of text lines and return bytes ready to stream as a
file download. Multi-page PDF and rich styling are intentionally out of scope
for the P1 export (the report is a plain, faithful list of sources).
"""

from __future__ import annotations

import io
import zipfile

_BS = chr(92)  # backslash, kept out of source literals to avoid escaping noise
_PDF_MAX_LINES = 46  # single US-Letter page at 14pt leading from y=720


# ── DOCX ──────────────────────────────────────────────────────────────────────


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_docx(title: str, lines: list[str]) -> bytes:
    """Return a minimal but valid .docx (Office Open XML) as bytes."""
    paras = [
        '<w:p><w:r><w:rPr><w:b/></w:rPr>'
        '<w:t xml:space="preserve">' + _xml_escape(title) + "</w:t></w:r></w:p>"
    ]
    for line in lines:
        paras.append(
            '<w:p><w:r><w:t xml:space="preserve">'
            + _xml_escape(line)
            + "</w:t></w:r></w:p>"
        )

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>" + "".join(paras) + "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
    return buf.getvalue()


# ── PDF ───────────────────────────────────────────────────────────────────────


def _pdf_escape(text: str) -> str:
    return text.replace(_BS, _BS + _BS).replace("(", _BS + "(").replace(")", _BS + ")")


def build_pdf(title: str, lines: list[str]) -> bytes:
    """Return a valid single-page PDF (Helvetica 12pt) as bytes."""
    all_lines = [title, "", *lines]
    content_parts = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for line in all_lines[:_PDF_MAX_LINES]:
        content_parts.append("(" + _pdf_escape(line) + ") Tj")
        content_parts.append("T*")
    content_parts.append("ET")
    content = "\n".join(content_parts).encode("latin-1", "replace")

    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length " + str(len(content)).encode() + b">>\nstream\n" + content + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"

    xref_pos = len(out)
    size = len(objects) + 1
    out += b"xref\n0 " + str(size).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<</Size " + str(size).encode() + b"/Root 1 0 R>>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    return bytes(out)
