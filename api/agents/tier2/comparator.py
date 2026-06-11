"""ComparatorAgent - Tier 2. Cross-document comparison (FR-RET-05).

Pipeline for ≥2 documents (primary path):
  1. hybrid_retrieve(query, top_k=20) — broad corpus sweep (invariant #1).
  2. build_comparator_matrix_prompt — LLM fills a documents x dimensions JSON matrix.
  3. _parse_matrix_response — defensive JSON parser; falls back to a default skeleton.
  4. Returns payload with block_type="LiteratureMatrix".

Single-document fallback (or when JSON parse fails):
  1-2. Same retrieval; prose comparison prompt instead.
  3. _build_prose_payload — extract inline [cN] citations.
  4. Returns payload with block_type="CitedSummary".
"""

from __future__ import annotations

import json
import re
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.comparator import (
    COMPARATOR_MATRIX_SYSTEM,
    COMPARATOR_PROMPT_VERSION,
    COMPARATOR_SYSTEM,
    build_comparator_matrix_prompt,
    build_comparator_prompt,
)
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrievedChunk, RetrieverProtocol

logger = get_logger(__name__)

_CITATION_RE = re.compile(r"\[c(\d+)\]", re.ASCII)
_QUOTE_PREVIEW_CHARS = 280


class ComparatorAgent(BaseAgent):
    """Tier-2 agent. Returns LiteratureMatrix (multi-doc) or CitedSummary (single-doc)."""

    name = "comparator"
    tier = 2

    def __init__(
        self,
        *,
        llm_service: LLMService,
        vector_retriever: RetrieverProtocol,
        bm25_retriever: RetrieverProtocol,
        graph_retriever: RetrieverProtocol,
    ) -> None:
        self._llm = llm_service
        self._vector = vector_retriever
        self._bm25 = bm25_retriever
        self._graph = graph_retriever

    async def run(self, query: str, state: AgentState) -> AgentResult:
        # FR-RET-05: broad corpus sweep (top_k=20 per PRD §12).
        chunks = await hybrid_retrieve(
            query,
            top_k=20,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            return AgentResult(
                agent_name=self.name,
                payload=_prose_payload("No documents retrieved for comparison.", [], []),
                status="partial",
                error="hybrid_retrieve returned 0 chunks",
            )

        doc_ids = _unique_doc_ids(chunks)

        if len(doc_ids) >= 2:
            # Primary path: structured LiteratureMatrix across multiple documents.
            return await self._run_matrix(query, chunks, state)

        # Fallback: single document — prose CitedSummary comparison.
        return await self._run_prose(query, chunks)

    async def _run_matrix(
        self, query: str, chunks: list[RetrievedChunk], state: AgentState
    ) -> AgentResult:
        # A2A hop 1: fetch the concept subgraph for visual context (FR-AGT-03).
        from api.agents.base import registry, route_to_agent  # late import avoids cycle
        if registry.get_agent("graph_agent") is not None:
            await route_to_agent("graph_agent", query, state=state)

        # A2A hop 2: surface contradictions across the same corpus.
        if registry.get_agent("contradiction") is not None:
            await route_to_agent("contradiction", query, state=state)

        messages = [
            Message(role="user", content=build_comparator_matrix_prompt(query, chunks))
        ]
        try:
            completion = await self._llm.complete(
                messages,
                system=COMPARATOR_MATRIX_SYSTEM,
                max_tokens=2048,
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("comparator.matrix_llm_failed")
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"LLM call failed: {exc}",
            )

        payload = _parse_matrix_response(raw, chunks=chunks, query=query)
        return AgentResult(agent_name=self.name, payload=payload, status="ok")

    async def _run_prose(
        self, query: str, chunks: list[RetrievedChunk]
    ) -> AgentResult:
        messages = [
            Message(role="user", content=build_comparator_prompt(query, chunks))
        ]
        try:
            completion = await self._llm.complete(
                messages,
                system=COMPARATOR_SYSTEM,
                max_tokens=1024,
            )
        except Exception as exc:
            logger.exception("comparator.prose_llm_failed")
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"LLM call failed: {exc}",
            )

        text = completion.text
        segments = _build_segments(text)
        citations = _build_citations(text, chunks)
        return AgentResult(
            agent_name=self.name,
            payload=_prose_payload(text, segments, citations),
            status="ok",
        )


# ---- Matrix parsing (mirrors literature.py) ---------------------------------


def _strip_fences(text: str) -> str:
    fence = chr(96) * 3
    if text.startswith(fence):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.rstrip().endswith(fence):
        text = text.rstrip()[: -len(fence)].rstrip()
    return text.strip()


def _parse_matrix_response(
    raw: str, *, chunks: list[RetrievedChunk], query: str
) -> dict[str, Any]:
    text = _strip_fences(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]

    try:
        parsed: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "comparator.matrix_parse_failed",
            raw_preview=raw[:120],
            version=COMPARATOR_PROMPT_VERSION,
        )
        parsed = {}

    dimensions = [str(d) for d in (parsed.get("dimensions") or [])]
    if not dimensions:
        dimensions = ["Approach", "Key findings", "Limitations"]

    raw_rows = parsed.get("rows") or []
    rows: list[dict[str, Any]] = []
    seen_doc_ids: set[str] = set()

    if isinstance(raw_rows, list):
        for r in raw_rows:
            if not isinstance(r, dict):
                continue
            doc_id = str(r.get("docId") or "")
            doc_title = str(r.get("docTitle") or doc_id or "Unknown document")
            if doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)

            raw_cells = r.get("cells") or []
            cells: list[dict[str, Any]] = []
            if isinstance(raw_cells, list):
                for cell in raw_cells:
                    if not isinstance(cell, dict):
                        cells.append({"text": "Not reported", "citationId": None})
                        continue
                    cells.append({
                        "text": str(cell.get("text") or "Not reported"),
                        "citationId": cell.get("citationId") or None,
                    })
            while len(cells) < len(dimensions):
                cells.append({"text": "Not reported", "citationId": None})
            cells = cells[: len(dimensions)]
            rows.append({"docId": doc_id, "docTitle": doc_title, "cells": cells})

    if not rows:
        for chunk in chunks:
            if chunk.doc_id not in seen_doc_ids:
                seen_doc_ids.add(chunk.doc_id)
                rows.append({
                    "docId": chunk.doc_id,
                    "docTitle": chunk.doc_id,
                    "cells": [{"text": "Not reported", "citationId": None}] * len(dimensions),
                })

    citations: list[dict[str, Any]] = [
        {
            "id": f"c{i + 1}",
            "docId": c.doc_id,
            "docTitle": c.doc_id,
            "page": c.page,
            "quote": c.text[:_QUOTE_PREVIEW_CHARS],
        }
        for i, c in enumerate(chunks)
    ]

    return {
        "block_type": "LiteratureMatrix",
        "data": {
            "query": query,
            "dimensions": dimensions,
            "rows": rows,
            "citations": citations,
        },
    }


# ---- Prose helpers (single-doc CitedSummary fallback) -----------------------


def _unique_doc_ids(chunks: list[RetrievedChunk]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for c in chunks:
        if c.doc_id not in seen:
            seen.add(c.doc_id)
            result.append(c.doc_id)
    return result


def _build_citations(text: str, chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    ordered: list[int] = []
    for m in _CITATION_RE.finditer(text):
        idx = int(m.group(1))
        if idx not in seen and 1 <= idx <= len(chunks):
            seen.add(idx)
            ordered.append(idx)
    return [
        {
            "id": f"c{idx}",
            "docId": chunks[idx - 1].doc_id,
            "docTitle": chunks[idx - 1].doc_id,
            "page": chunks[idx - 1].page,
            "quote": chunks[idx - 1].text[:_QUOTE_PREVIEW_CHARS],
        }
        for idx in ordered
    ]


def _build_segments(text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    pos = 0
    for m in _CITATION_RE.finditer(text):
        between = text[pos : m.start()]
        cite_id = f"c{m.group(1)}"
        if between.strip():
            segments.append({"text": between.strip(), "citationIds": [cite_id]})
        elif segments:
            segments[-1] = {
                "text": segments[-1]["text"],
                "citationIds": [*segments[-1]["citationIds"], cite_id],
            }
        pos = m.end()
    trailing = text[pos:].strip()
    if trailing:
        segments.append({"text": trailing, "citationIds": []})
    return segments


def _prose_payload(
    summary: str,
    segments: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {"summary": summary, "segments": segments, "citations": citations}
