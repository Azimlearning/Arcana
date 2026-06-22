"""Bibliography export — BibTeX + RIS from document metadata (FR-EXP-08).

Pure string formatting over `DocMetadata`; no third-party dependency.
Arcana's corpus metadata is minimal (title, source URI, ingest date), so
entries use the `@misc`/`GEN` types with an access date — honest about what
is actually known rather than inventing authors/years.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# Single backslash via a raw string keeps source escaping unambiguous.
_URL_OPEN = r"\url{"


@dataclass(frozen=True)
class CitationEntry:
    """The minimal citable facts Arcana holds about a source."""

    key: str          # citation key / id
    title: str
    url: str
    accessed: str     # ISO date (YYYY-MM-DD)


_KEY_SANITIZE = re.compile(r"[^A-Za-z0-9]+")
_BIBTEX_SPECIALS = ["&", "%", "$", "#", "_", "{", "}"]


def make_key(doc_id: str, title: str) -> str:
    """A stable, BibTeX-safe citation key."""
    base = _KEY_SANITIZE.sub("", (doc_id or title or "source").title())[:40]
    return base or "source"


def _bibtex_escape(text: str) -> str:
    out = text
    for ch in _BIBTEX_SPECIALS:
        out = out.replace(ch, "\\" + ch)
    return out


def to_bibtex(entries: Iterable[CitationEntry]) -> str:
    """Render entries as a BibTeX `@misc` bibliography."""
    blocks: list[str] = []
    for e in entries:
        fields = ["  title = {" + _bibtex_escape(e.title) + "}"]
        if e.url:
            fields.append("  howpublished = {" + _URL_OPEN + e.url + "}}")
        if e.accessed:
            fields.append("  urldate = {" + e.accessed + "}")
        body = ",\n".join(fields)
        blocks.append("@misc{" + e.key + ",\n" + body + "\n}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def to_ris(entries: Iterable[CitationEntry]) -> str:
    """Render entries in RIS (Reference Manager) format."""
    blocks: list[str] = []
    for e in entries:
        lines = ["TY  - GEN", "TI  - " + e.title]
        if e.url:
            lines.append("UR  - " + e.url)
        if e.accessed:
            lines.append("Y2  - " + e.accessed)
        lines.append("ER  - ")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")
