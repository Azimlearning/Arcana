"""ComparatorAgent - Tier 2. Comparison-framed CitedSummary synthesis.

Specialises the CitedSummary path for queries asking to compare entities, approaches,
or methodologies. Uses a comparison-structured prompt rather than a neutral synthesis
prompt so the LLM structures its response around similarities and differences.
"""

from __future__ import annotations

import re
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.comparator import (
    COMPARATOR_SYSTEM,
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
    """Tier-2 agent. Returns a CitedSummary shaped as a structured comparison."""

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
        chunks = await hybrid_retrieve(
            query,
            top_k=10,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            return AgentResult(
                agent_name=self.name,
                payload=_empty_payload("No documents retrieved for comparison."),
                status="partial",
                error="hybrid_retrieve returned 0 chunks",
            )

        messages = [
            Message(role="user", content=build_comparator_prompt(query, chunks))
        ]
        try:
            completion = await self._llm.complete(
                messages,
                system=COMPARATOR_SYSTEM,
                budget=state.budget,
            )
        except Exception as exc:
            logger.exception("comparator.llm_failed")
            return AgentResult(
                agent_name=self.name,
                payload=_empty_payload(f"LLM call failed: {exc}"),
                status="failed",
                error=str(exc),
            )

        text = completion.text
        segments = _build_segments(text)
        citations = _build_citations(text, chunks)

        return AgentResult(
            agent_name=self.name,
            payload={
                "summary": text,
                "segments": segments,
                "citations": citations,
            },
            status="ok",
        )


# ---- Shared citation parsing (mirrors research.py helpers) ------------------


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


def _empty_payload(message: str) -> dict[str, Any]:
    return {
        "summary": message,
        "segments": [{"text": message, "citationIds": []}],
        "citations": [],
    }
