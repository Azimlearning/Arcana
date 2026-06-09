"""CrossDocAgent - Tier 2. Surfaces serendipitous InsightCard cross-document links.

Pipeline:
  1. hybrid_retrieve(query, top_k=10) — grounds the analysis (invariant #1).
  2. build_cross_doc_prompt — LLM finds a non-obvious connection between two docs.
  3. _parse_cross_doc_response — defensive JSON parser; falls back to a best-effort
     InsightCard from the top two chunk doc_ids.
  4. Returns payload with block_type="InsightCard".
"""

from __future__ import annotations

import json
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.cross_doc import (
    CROSS_DOC_PROMPT_VERSION,
    CROSS_DOC_SYSTEM,
    build_cross_doc_prompt,
)
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrievedChunk, RetrieverProtocol

logger = get_logger(__name__)

_MAX_QUOTE_CHARS = 200


class CrossDocAgent(BaseAgent):
    """Tier-2 specialist that extracts cross-document insights (InsightCard)."""

    name = "cross_doc"
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
        chunks = await hybrid_retrieve(
            query,
            top_k=10,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            logger.warning("cross_doc.no_chunks", query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No documents retrieved for cross-document analysis.",
            )

        # Need at least two documents for a cross-doc insight.
        doc_ids = _unique_doc_ids(chunks)
        if len(doc_ids) < 2:
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="At least two documents needed for cross-document insight.",
            )

        messages = [
            Message(role="user", content=build_cross_doc_prompt(query, chunks))
        ]
        try:
            completion = await self._llm.complete(
                messages,
                system=CROSS_DOC_SYSTEM,
                max_tokens=1024,
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("cross_doc.llm_failed")
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"LLM call failed: {exc}",
            )

        payload = _parse_cross_doc_response(raw, chunks=chunks, query=query)
        return AgentResult(
            agent_name=self.name,
            payload=payload,
            status="ok",
        )


# ---- Helpers ----------------------------------------------------------------


def _unique_doc_ids(chunks: list[RetrievedChunk]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for c in chunks:
        if c.doc_id not in seen:
            seen.add(c.doc_id)
            result.append(c.doc_id)
    return result


def _strip_fences(text: str) -> str:
    fence = chr(96) * 3
    if text.startswith(fence):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.rstrip().endswith(fence):
        text = text.rstrip()[: -len(fence)].rstrip()
    return text.strip()


def _parse_cross_doc_response(
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
            "cross_doc.parse_failed",
            raw_preview=raw[:120],
            version=CROSS_DOC_PROMPT_VERSION,
        )
        parsed = {}

    doc_ids = _unique_doc_ids(chunks)
    doc_a_id = str(parsed.get("docAId") or doc_ids[0])
    doc_b_id = str(parsed.get("docBId") or (doc_ids[1] if len(doc_ids) > 1 else doc_ids[0]))
    doc_a_title = str(parsed.get("docATitle") or doc_a_id)
    doc_b_title = str(parsed.get("docBTitle") or doc_b_id)

    insight = str(
        parsed.get("insight") or f"Cross-document insight for: {query[:80]}"
    )
    connection = str(
        parsed.get("connection") or "These documents share a common theme."
    )

    raw_citations = parsed.get("citations") or []
    citations: list[dict[str, Any]] = []
    if isinstance(raw_citations, list):
        for cit in raw_citations[:3]:
            if not isinstance(cit, dict):
                continue
            citations.append(
                {
                    "id": str(cit.get("id") or f"c{len(citations) + 1}"),
                    "docId": str(cit.get("docId") or ""),
                    "docTitle": str(cit.get("docTitle") or cit.get("docId") or ""),
                    "page": cit.get("page"),
                    "quote": str(cit.get("quote") or "")[:_MAX_QUOTE_CHARS],
                }
            )

    # Ensure at least one citation.
    if not citations and chunks:
        c = chunks[0]
        citations.append(
            {
                "id": "c1",
                "docId": c.doc_id,
                "docTitle": c.doc_id,
                "page": c.page,
                "quote": c.text[:_MAX_QUOTE_CHARS],
            }
        )

    return {
        "block_type": "InsightCard",
        "data": {
            "insight": insight,
            "connection": connection,
            "docAId": doc_a_id,
            "docATitle": doc_a_title,
            "docBId": doc_b_id,
            "docBTitle": doc_b_title,
            "citations": citations,
        },
    }
