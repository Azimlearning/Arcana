"""AnnotationAgent - Tier 2. Claim-extraction and coverage gap analysis.

Specialises the GapAnalysis path for queries asking about what claims a set of
sources makes and what is missing. Produces GapAnalysis payloads framed around
claim coverage rather than research gaps.
"""

from __future__ import annotations

import json
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.annotation import (
    ANNOTATION_PROMPT_VERSION,
    ANNOTATION_SYSTEM,
    build_annotation_prompt,
)
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrieverProtocol

logger = get_logger(__name__)

_VALID_SEVERITIES = frozenset({"high", "medium", "low"})
_DEFAULT_SEVERITY = "medium"


class AnnotationAgent(BaseAgent):
    """Tier-2 agent. Returns a GapAnalysis of claim coverage for a topic."""

    name = "annotate"
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
            top_k=8,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            logger.warning("annotation.no_chunks", query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No documents retrieved for annotation.",
            )

        messages = [
            Message(role="user", content=build_annotation_prompt(query, chunks))
        ]
        try:
            completion = await self._llm.complete(
                messages,
                system=ANNOTATION_SYSTEM,
                max_tokens=1024,
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("annotation.llm_failed")
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"LLM call failed: {exc}",
            )

        payload = _parse_annotation_response(raw, query=query)
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


def _parse_annotation_response(raw: str, *, query: str) -> dict[str, Any]:
    text = _strip_fences(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]

    try:
        parsed: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "annotation.parse_failed",
            raw_preview=raw[:120],
            version=ANNOTATION_PROMPT_VERSION,
        )
        parsed = {}

    summary = str(parsed.get("summary") or f"Annotation for: {query[:80]}")
    raw_gaps = parsed.get("gaps") or []
    covered = [str(t) for t in (parsed.get("coveredTopics") or [])]

    gaps: list[dict[str, str]] = []
    if isinstance(raw_gaps, list):
        for g in raw_gaps:
            if not isinstance(g, dict):
                continue
            severity = str(g.get("severity", _DEFAULT_SEVERITY)).lower()
            if severity not in _VALID_SEVERITIES:
                severity = _DEFAULT_SEVERITY
            gaps.append(
                {
                    "label": str(g.get("label") or "Unnamed gap"),
                    "description": str(g.get("description") or ""),
                    "severity": severity,
                }
            )

    return {
        "block_type": "GapAnalysis",
        "data": {
            "summary": summary,
            "gaps": gaps,
            "coveredTopics": covered,
        },
    }
