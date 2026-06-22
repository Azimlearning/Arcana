"""ContradictionAgent - Tier 2. Detects cross-source disagreements.

Pipeline:
  1. hybrid_retrieve(query, top_k=10) — grounds the analysis (invariant #1).
  2. build_contradiction_prompt — LLM finds places where sources disagree.
  3. _parse_contradiction_response — defensive JSON parser.
  4. Returns payload with block_type="ContradictionAlert".
"""

from __future__ import annotations

import json
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.contradiction import (
    CONTRADICTION_PROMPT_VERSION,
    CONTRADICTION_SYSTEM,
    build_contradiction_prompt,
)
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrievedChunk, RetrieverProtocol

logger = get_logger(__name__)

_MAX_QUOTE_CHARS = 200


class ContradictionAgent(BaseAgent):
    """Tier-2 specialist that surfaces contradictions across sources."""

    name = "contradiction"
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
            mode=state.retrieval_mode,  # type: ignore[arg-type]  # FR-RET-07
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            logger.warning("contradiction.no_chunks", query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No documents retrieved for contradiction analysis.",
            )

        messages = [
            Message(role="user", content=build_contradiction_prompt(query, chunks))
        ]
        try:
            completion = await self._llm.complete(
                messages,
                system=CONTRADICTION_SYSTEM,
                max_tokens=1024,
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("contradiction.llm_failed")
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error=f"LLM call failed: {exc}",
            )

        payload = _parse_contradiction_response(raw, chunks=chunks, query=query)
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


def _parse_contradiction_response(
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
            "contradiction.parse_failed",
            raw_preview=raw[:120],
            version=CONTRADICTION_PROMPT_VERSION,
        )
        parsed = {}

    concept = str(parsed.get("concept") or query[:80])
    summary = str(
        parsed.get("summary") or f"Contradiction analysis for: {query[:80]}"
    )

    raw_claims = parsed.get("claims") or []
    claims: list[dict[str, str]] = []
    if isinstance(raw_claims, list):
        for c in raw_claims[:4]:  # cap at 4 per prompt rules
            if not isinstance(c, dict):
                continue
            claims.append(
                {
                    "docId": str(c.get("docId") or ""),
                    "docTitle": str(c.get("docTitle") or c.get("docId") or "Unknown"),
                    "stance": str(c.get("stance") or "")[:80],
                    "quote": str(c.get("quote") or "")[:_MAX_QUOTE_CHARS],
                }
            )

    return {
        "block_type": "ContradictionAlert",
        "data": {
            "concept": concept,
            "summary": summary,
            "claims": claims,
        },
    }
