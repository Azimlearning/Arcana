"""LiteratureAgent - Tier 2. Produces LiteratureMatrix (papers x dimensions grid).

Pipeline:
  1. hybrid_retrieve(query, top_k=12) — grounds the analysis (invariant #1).
  2. build_literature_prompt — LLM structures retrieved passages as a
     papers x dimensions comparison matrix.
  3. _parse_literature_response — defensive JSON parser; handles fences + prose.
  4. Returns payload with block_type="LiteratureMatrix".
"""

from __future__ import annotations

import json
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.literature import (
    LITERATURE_PROMPT_VERSION,
    LITERATURE_SYSTEM,
    build_literature_prompt,
)
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrievedChunk, RetrieverProtocol

logger = get_logger(__name__)


class LiteratureAgent(BaseAgent):
    """Tier-2 specialist that builds literature comparison matrices."""

    name = "literature"
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
        # 1. Ground before generating (invariant #1).
        chunks = await hybrid_retrieve(
            query,
            top_k=12,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            logger.warning("literature.no_chunks", query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No documents retrieved for literature matrix.",
            )

        messages = [
            Message(role="user", content=build_literature_prompt(query, chunks))
        ]
        try:
            completion = await self._llm.complete(
                messages,
                system=LITERATURE_SYSTEM,
                max_tokens=2048,
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("literature.llm_failed")
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"LLM call failed: {exc}",
            )

        payload = _parse_literature_response(raw, chunks=chunks, query=query)
        return AgentResult(
            agent_name=self.name,
            payload=payload,
            status="ok",
        )


# ---- Response parsing -------------------------------------------------------


def _strip_fences(text: str) -> str:
    fence = chr(96) * 3
    if text.startswith(fence):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.rstrip().endswith(fence):
        text = text.rstrip()[: -len(fence)].rstrip()
    return text.strip()


def _parse_literature_response(
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
            "literature.parse_failed",
            raw_preview=raw[:120],
            version=LITERATURE_PROMPT_VERSION,
        )
        parsed = {}

    dimensions = [str(d) for d in (parsed.get("dimensions") or [])]
    if not dimensions:
        dimensions = ["Methodology", "Key finding", "Limitations"]

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
                    cells.append(
                        {
                            "text": str(cell.get("text") or "Not reported"),
                            "citationId": cell.get("citationId") or None,
                        }
                    )
            # Pad / trim to match dimension count.
            while len(cells) < len(dimensions):
                cells.append({"text": "Not reported", "citationId": None})
            cells = cells[: len(dimensions)]

            rows.append({"docId": doc_id, "docTitle": doc_title, "cells": cells})

    # If the LLM returned nothing, synthesise a row per unique doc from chunks.
    if not rows:
        for chunk in chunks:
            if chunk.doc_id not in seen_doc_ids:
                seen_doc_ids.add(chunk.doc_id)
                rows.append(
                    {
                        "docId": chunk.doc_id,
                        "docTitle": chunk.doc_id,
                        "cells": [
                            {"text": "Not reported", "citationId": None}
                        ] * len(dimensions),
                    }
                )

    # Build citation list from chunks actually referenced.
    citations: list[dict[str, Any]] = [
        {
            "id": f"c{i + 1}",
            "docId": c.doc_id,
            "docTitle": c.doc_id,
            "page": c.page,
            "quote": c.text[:280],
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
