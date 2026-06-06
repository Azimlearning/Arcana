"""DiscoveryAgent - Tier 2. Finds knowledge gaps and cross-doc connections.

Produces GapAnalysis payloads (Slice 2, FR-AGT-06).

Pipeline:
  1. hybrid_retrieve(query) - grounds the analysis (invariant #1).
  2. build_gap_prompt(query, context) - LLM identifies gaps in the corpus.
  3. _parse_gap_response - defensive JSON parser (handles fences, partial garbage).
  4. Returns payload with block_type="GapAnalysis" for the UI Agent to consume.
"""

from __future__ import annotations

import json
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.discovery import DISCOVERY_PROMPT_VERSION, DISCOVERY_SYSTEM, build_gap_prompt
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrieverProtocol

logger = get_logger(__name__)

_VALID_SEVERITIES = frozenset({"high", "medium", "low"})
_DEFAULT_SEVERITY = "medium"


class DiscoveryAgent(BaseAgent):
    """Tier-2 specialist that surfaces knowledge gaps via graph + retrieval."""

    name = "discovery"
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
            top_k=8,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            logger.warning("discovery.no_chunks", query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No documents retrieved for discovery analysis.",
            )

        ctx_text = "\n\n".join(
            f"[{c.id}] (doc:{c.doc_id}, p.{c.page}) {c.text}" for c in chunks
        )

        messages = [
            Message(role="user", content=build_gap_prompt(query, ctx_text))
        ]
        try:
            completion = await self._llm.complete(
                messages,
                system=DISCOVERY_SYSTEM,
                max_tokens=1024,
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("discovery.llm_failed")
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"LLM call failed: {exc}",
            )

        payload = _parse_gap_response(raw, query=query)
        return AgentResult(
            agent_name=self.name,
            payload=payload,
            status="ok",
        )


# ---- Response parsing ---------------------------------------------------


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    fence = chr(96) * 3
    if text.startswith(fence):
        # Strip opening fence (may include language tag like ```json)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.rstrip().endswith(fence):
        text = text.rstrip()[: -len(fence)].rstrip()
    return text.strip()


def _parse_gap_response(raw: str, *, query: str) -> dict[str, Any]:
    """Extract GapAnalysisData-shaped dict from the LLM text.

    Handles markdown fences, leading prose, partial/missing fields.
    Returns a valid payload even when the LLM is partially broken - callers
    rely on the Pydantic model to final-validate.
    """
    text = _strip_fences(raw)

    # Find the outermost JSON object if there is surrounding prose.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]

    try:
        parsed: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "discovery.parse_failed",
            raw_preview=raw[:120],
            version=DISCOVERY_PROMPT_VERSION,
        )
        parsed = {}

    summary = str(parsed.get("summary") or f"Gap analysis for: {query[:80]}")
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
