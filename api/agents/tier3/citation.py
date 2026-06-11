"""CitationAgent - Tier 3. Citation formatting and bibliography export.

Handles queries about citing sources in specific styles (APA, MLA, etc.)
and full bibliography generation (FR-EXP-08 precursor).

Intent "citation"     -> CitationPreview (single-doc preview)
Intent "bibliography" -> BibliographyExport (all docs as BibTeX)
"""

from __future__ import annotations

import re
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.stores.doc_store import DocMetadata, DocStore

logger = get_logger(__name__)

_DEFAULT_STYLE = "apa"

_BIBLIOGRAPHY_KEYWORDS = frozenset({
    "bibliography", "all citations", "all references",
    "bibtex", "references list", "cite all", "full bibliography",
})


def _infer_year(meta: DocMetadata) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", meta.title + " " + meta.source_uri)
    return int(m.group(0)) if m else None


def _infer_authors(meta: DocMetadata) -> list[str]:
    if "authors" in meta.extra:
        return [a.strip() for a in meta.extra["authors"].split(",") if a.strip()]
    return ["Unknown Author"]


def _infer_style(query: str) -> str:
    q = query.lower()
    for s in ("mla", "chicago", "ieee", "harvard", "apa"):
        if s in q:
            return s
    return _DEFAULT_STYLE


def _format_apa(meta: DocMetadata, authors: list[str], year: int | None) -> str:
    author_str = ", ".join(authors[:3])
    if len(authors) > 3:
        author_str += " et al."
    year_str = f"({year})" if year else "(n.d.)"
    return f"{author_str}. {year_str}. {meta.title}. {meta.source_uri}"


def _format_mla(meta: DocMetadata, authors: list[str]) -> str:
    author_str = authors[0] if authors else "Unknown"
    return f'{author_str}. "{meta.title}." Web. <{meta.source_uri}>.'


def _format_ieee(meta: DocMetadata, authors: list[str], year: int | None) -> str:
    abbrev = ", ".join(a.split()[-1] for a in authors[:3])
    year_str = str(year) if year else "n.d."
    return f'{abbrev}, "{meta.title}," {year_str}. [Online]. Available: {meta.source_uri}'


def _bibtex_key(meta: DocMetadata, authors: list[str], year: int | None) -> str:
    last = re.sub(r"\W+", "", authors[0].split()[-1] if authors else "Unknown")
    return (last + (str(year) if year else "nd"))[:20]


def _make_bibtex(meta: DocMetadata, authors: list[str], year: int | None) -> str:
    key = _bibtex_key(meta, authors, year)
    author_str = " and ".join(authors)
    lines = [
        f"@misc{{{key},",
        f"  title = {{{meta.title}}},",
        f"  author = {{{author_str}}},",
        f"  year = {{{year or ''}}},",
        f"  url = {{{meta.source_uri}}}",
        "}",
    ]
    return "\n".join(lines)


def _format_citation(meta: DocMetadata, style: str) -> tuple[str, str]:
    """Return (formatted_string, bibtex)."""
    authors = _infer_authors(meta)
    year = _infer_year(meta)
    bibtex = _make_bibtex(meta, authors, year)
    if style == "mla":
        formatted = _format_mla(meta, authors)
    elif style == "ieee":
        formatted = _format_ieee(meta, authors, year)
    else:  # apa / chicago / harvard — simplified to APA
        formatted = _format_apa(meta, authors, year)
    return formatted, bibtex


class CitationAgent(BaseAgent):
    """Tier-3 output agent. Formats corpus documents as citation blocks."""

    name = "citation"
    tier = 3

    def __init__(self, *, doc_store: DocStore) -> None:
        self._doc_store = doc_store

    async def run(self, query: str, state: AgentState) -> AgentResult:
        q = query.lower()
        style = _infer_style(q)
        if any(kw in q for kw in _BIBLIOGRAPHY_KEYWORDS):
            return await self._bibliography(state, style)
        return await self._citation_preview(state, style)

    # -- private -----------------------------------------------------------

    async def _citation_preview(self, state: AgentState, style: str) -> AgentResult:
        try:
            docs = await self._doc_store.list_documents()
        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"doc_store.list_documents: {exc}",
            )

        if not docs:
            return AgentResult(
                agent_name=self.name,
                payload={"block_type": "CitationPreview", "data": {
                    "docId": "", "docTitle": "No documents",
                    "authors": [], "year": None, "sourceUri": "",
                    "formatted": "No documents found in this notebook.",
                    "style": style,
                }},
                status="partial",
            )

        meta = docs[0]
        authors = _infer_authors(meta)
        year = _infer_year(meta)
        formatted, _ = _format_citation(meta, style)
        return AgentResult(
            agent_name=self.name,
            payload={"block_type": "CitationPreview", "data": {
                "docId": meta.id,
                "docTitle": meta.title,
                "authors": authors,
                "year": year,
                "sourceUri": meta.source_uri,
                "formatted": formatted,
                "style": style,
            }},
            status="ok",
        )

    async def _bibliography(self, state: AgentState, style: str) -> AgentResult:
        try:
            docs = await self._doc_store.list_documents()
        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"doc_store.list_documents: {exc}",
            )

        entries: list[dict[str, Any]] = []
        bibtex_parts: list[str] = []
        for meta in docs:
            authors = _infer_authors(meta)
            year = _infer_year(meta)
            _, bibtex = _format_citation(meta, style)
            entries.append({
                "key": _bibtex_key(meta, authors, year),
                "docId": meta.id,
                "docTitle": meta.title,
                "authors": authors,
                "year": year,
                "sourceType": "misc",
                "bibtex": bibtex,
            })
            bibtex_parts.append(bibtex)

        return AgentResult(
            agent_name=self.name,
            payload={"block_type": "BibliographyExport", "data": {
                "entries": entries,
                "bibtexAll": "\n\n".join(bibtex_parts),
            }},
            status="ok" if entries else "partial",
        )
