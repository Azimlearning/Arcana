"""SocraticAgent - Tier 2. Guides learners via questions, never answers.

Produces SocraticDialog payloads (Slice 3, FR-LRN-08).

Pipeline:
  1. hybrid_retrieve(query) - grounds the concept (invariant #1).
  2. build_socratic_prompt() - LLM generates the next probing question.
  3. _is_answer_shaped() - post-generation guard rejects answer-shaped outputs.
  4. Returns payload with block_type="SocraticDialog".

The never-answer contract: nextQuestion is regenerated once if it reads as
an answer. After two attempts the field is replaced with a safe fallback
question so the block is never empty.
"""

from __future__ import annotations

import json
import re
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.socratic import (
    SOCRATIC_PROMPT_VERSION,
    SOCRATIC_SYSTEM,
    build_socratic_prompt,
)
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrieverProtocol

logger = get_logger(__name__)

_VALID_BLOOM = frozenset({
    "recall", "comprehension", "application", "analysis", "synthesis", "evaluation"
})
_DEFAULT_BLOOM = "comprehension"

# Patterns that suggest the LLM slipped an answer into nextQuestion.
# These are conservative — we only reject obvious answer-shaped outputs.
_ANSWER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bthe answer (is|are)\b", re.IGNORECASE),
    re.compile(r"\bthis (means|refers to|is called)\b", re.IGNORECASE),
    re.compile(r"\bspecifically,\b", re.IGNORECASE),
    re.compile(r"\btherefore\b", re.IGNORECASE),
    re.compile(r"\bthus\b", re.IGNORECASE),
    re.compile(r"\bbecause\b.*\bis\b", re.IGNORECASE),
]


def _is_answer_shaped(text: str) -> bool:
    """Return True if `text` looks like an answer rather than a question."""
    stripped = text.strip()
    # Must end with '?' to be a valid question.
    if not stripped.endswith("?"):
        return True
    # Check for answer-shaped phrases.
    return any(p.search(stripped) for p in _ANSWER_PATTERNS)


def _strip_fences(text: str) -> str:
    fence = chr(96) * 3
    if text.startswith(fence):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.rstrip().endswith(fence):
        text = text.rstrip()[: -len(fence)].rstrip()
    return text.strip()


def _extract_json(text: str) -> dict[str, Any]:
    text = _strip_fences(text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("socratic.parse_failed", raw_preview=text[:120], version=SOCRATIC_PROMPT_VERSION)
        return {}


class SocraticAgent(BaseAgent):
    """Tier-2 Socratic tutor — asks questions, never gives answers."""

    name = "socratic"
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
            top_k=6,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            logger.warning("socratic.no_chunks", query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No documents retrieved for Socratic session.",
            )

        ctx_text = "\n\n".join(
            f"[{c.id}] (doc:{c.doc_id}, p.{c.page}) {c.text}" for c in chunks
        )

        # Extract prior turns from agent state if a previous socratic block exists.
        prior_turns = _extract_prior_turns(state)

        # 2. Attempt to generate a valid probing question (up to 2 tries).
        concept = query[:100]
        bloom = _DEFAULT_BLOOM
        next_question: str | None = None

        for attempt in range(2):
            messages = [
                Message(
                    role="user",
                    content=build_socratic_prompt(concept, ctx_text, prior_turns, bloom),
                )
            ]
            try:
                completion = await self._llm.complete(
                    messages, system=SOCRATIC_SYSTEM, max_tokens=512
                )
                raw = completion.text
            except Exception:
                logger.exception("socratic.llm_failed", attempt=attempt)
                break

            parsed = _extract_json(raw)
            candidate = str(parsed.get("nextQuestion") or "").strip()
            bloom = str(parsed.get("bloomLevel") or bloom).lower()
            if bloom not in _VALID_BLOOM:
                bloom = _DEFAULT_BLOOM

            if candidate and not _is_answer_shaped(candidate):
                next_question = candidate
                break
            logger.warning(
                "socratic.answer_shaped_detected",
                attempt=attempt,
                candidate_preview=candidate[:80],
            )

        # 3. Safe fallback if all attempts failed.
        if not next_question:
            next_question = f"What do you already know about {concept[:60]}?"
            logger.warning("socratic.fallback_question_used", concept=concept[:60])

        payload = {
            "block_type": "SocraticDialog",
            "data": {
                "concept": concept,
                "turns": prior_turns,
                "nextQuestion": next_question,
                "bloomLevel": bloom,
            },
        }
        return AgentResult(agent_name=self.name, payload=payload, status="ok")


def _extract_prior_turns(state: AgentState) -> list[dict[str, str]]:
    """Pull previous Socratic turns from the most recent SocraticDialog block."""
    for block in reversed(state.ui_blocks):
        if getattr(block, "type", None) == "SocraticDialog":
            data = getattr(block, "data", None)
            if data is not None:
                return [
                    {"role": t.role, "text": t.text}
                    for t in getattr(data, "turns", [])
                ]
    return []
