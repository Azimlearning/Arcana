"""LearningAgent - Tier 2. Generates grounded study artifacts.

Produces FlashcardDeck, QuizCard, and FeynmanExplainer payloads
(Slice 3: FR-LRN-01/03, Slice 4: FR-LRN-04).

Pipeline:
  1. hybrid_retrieve(query) - grounds all material (invariant #1).
  2. build_*_prompt() - LLM generates the artifact.
  3. _parse_*_response() - defensive parsers.
  4. Returns payload with block_type matching the artifact type.
"""

from __future__ import annotations

import json
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.prompts.learning import (
    FEYNMAN_SYSTEM,
    FLASHCARD_SYSTEM,
    LEARNING_PROMPT_VERSION,
    QUIZ_SYSTEM,
    build_feynman_prompt,
    build_flashcard_prompt,
    build_quiz_prompt,
)
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrieverProtocol

logger = get_logger(__name__)

_VALID_DIFFICULTIES = frozenset({"recall", "comprehension", "application", "analysis"})
_DEFAULT_DIFFICULTY = "comprehension"


class LearningAgent(BaseAgent):
    """Tier-2 specialist that generates grounded study artifacts."""

    name = "learning"
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
            logger.warning("learning.no_chunks", query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No documents retrieved for study material generation.",
            )

        ctx_text = "\n\n".join(
            f"[{c.id}] (doc:{c.doc_id}, p.{c.page}) {c.text}" for c in chunks
        )

        # Infer artifact type from query keywords; default to flashcard deck.
        # Temp heuristic — full intent detection replaces this in §1.3.
        want_quiz = any(kw in query.lower() for kw in ("quiz", "question", "test me", "mcq"))
        want_feynman = any(
            kw in query.lower()
            for kw in ("feynman", "eli5", "explain simply", "simple terms", "like im", "like i'm")
        )

        if want_quiz:
            payload = await self._generate_quiz(query, ctx_text)
        elif want_feynman:
            payload = await self._generate_feynman(query, ctx_text)
        else:
            payload = await self._generate_flashcards(query, ctx_text)

        return AgentResult(agent_name=self.name, payload=payload, status="ok")

    async def _generate_flashcards(self, topic: str, ctx_text: str) -> dict[str, Any]:
        messages = [Message(role="user", content=build_flashcard_prompt(topic, ctx_text))]
        try:
            completion = await self._llm.complete(
                messages, system=FLASHCARD_SYSTEM, max_tokens=1500
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("learning.llm_failed_flashcard")
            return _error_flashcard_payload(topic, str(exc))

        return _parse_flashcard_response(raw, topic=topic)

    async def _generate_quiz(self, topic: str, ctx_text: str) -> dict[str, Any]:
        difficulty = _DEFAULT_DIFFICULTY
        for diff in _VALID_DIFFICULTIES:
            if diff in topic.lower():
                difficulty = diff
                break

        messages = [Message(role="user", content=build_quiz_prompt(topic, ctx_text, difficulty))]
        try:
            completion = await self._llm.complete(
                messages, system=QUIZ_SYSTEM, max_tokens=800
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("learning.llm_failed_quiz")
            return _error_quiz_payload(topic, str(exc))

        return _parse_quiz_response(raw, topic=topic, difficulty=difficulty)

    async def _generate_feynman(self, topic: str, ctx_text: str) -> dict[str, Any]:
        messages = [Message(role="user", content=build_feynman_prompt(topic, ctx_text))]
        try:
            completion = await self._llm.complete(
                messages, system=FEYNMAN_SYSTEM, max_tokens=600
            )
            raw = completion.text
        except Exception as exc:
            logger.exception("learning.llm_failed_feynman")
            return _error_feynman_payload(topic, str(exc))

        return _parse_feynman_response(raw, topic=topic)


# ── Response parsing ──────────────────────────────────────────────────────


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
        logger.warning("learning.parse_failed", raw_preview=text[:120], version=LEARNING_PROMPT_VERSION)
        return {}


def _safe_source(raw: Any, fallback_id: str = "c1") -> dict[str, Any]:
    """Normalise a source dict from the LLM, providing safe defaults."""
    if not isinstance(raw, dict):
        return {"id": fallback_id, "docId": "", "docTitle": "Unknown", "page": None, "quote": ""}
    return {
        "id": str(raw.get("id") or fallback_id),
        "docId": str(raw.get("docId") or ""),
        "docTitle": str(raw.get("docTitle") or "Unknown"),
        "page": raw.get("page"),
        "quote": str(raw.get("quote") or ""),
    }


def _parse_flashcard_response(raw: str, *, topic: str) -> dict[str, Any]:
    parsed = _extract_json(raw)
    topic_out = str(parsed.get("topic") or topic[:80])
    raw_cards = parsed.get("cards") or []

    cards: list[dict[str, Any]] = []
    if isinstance(raw_cards, list):
        for card in raw_cards:
            if not isinstance(card, dict):
                continue
            cards.append({
                "front": str(card.get("front") or ""),
                "back": str(card.get("back") or ""),
                "source": _safe_source(card.get("source")),
                "schedule": None,
            })

    return {
        "block_type": "FlashcardDeck",
        "data": {
            "topic": topic_out,
            "cards": cards,
            "totalCards": len(cards),
            "dueCount": 0,
        },
    }


def _parse_quiz_response(raw: str, *, topic: str, difficulty: str) -> dict[str, Any]:
    parsed = _extract_json(raw)

    q_type = str(parsed.get("questionType") or "mcq")
    if q_type not in ("mcq", "short_answer"):
        q_type = "mcq"

    raw_options = parsed.get("options") or []
    options: list[dict[str, Any]] = []
    if isinstance(raw_options, list):
        for opt in raw_options:
            if isinstance(opt, dict):
                options.append({
                    "index": int(opt.get("index", len(options))),
                    "text": str(opt.get("text") or ""),
                })

    correct_raw = parsed.get("correctIndex")
    correct_index = int(correct_raw) if isinstance(correct_raw, (int, float)) else None

    diff = str(parsed.get("difficulty") or difficulty).lower()
    if diff not in _VALID_DIFFICULTIES:
        diff = _DEFAULT_DIFFICULTY

    return {
        "block_type": "QuizCard",
        "data": {
            "question": str(parsed.get("question") or f"What do you know about {topic[:60]}?"),
            "questionType": q_type,
            "options": options,
            "correctIndex": correct_index,
            "explanation": str(parsed.get("explanation") or ""),
            "difficulty": diff,
            "source": _safe_source(parsed.get("source")),
        },
    }


def _parse_feynman_response(raw: str, *, topic: str) -> dict[str, Any]:
    parsed = _extract_json(raw)
    return {
        "block_type": "FeynmanExplainer",
        "data": {
            "concept": str(parsed.get("concept") or topic[:100]),
            "explanation": str(parsed.get("explanation") or ""),
            "gaps": [str(g) for g in (parsed.get("gaps") or []) if g],
            "source": _safe_source(parsed.get("source")),
        },
    }


def _error_flashcard_payload(topic: str, error: str) -> dict[str, Any]:
    return {
        "block_type": "FlashcardDeck",
        "data": {"topic": topic[:80], "cards": [], "totalCards": 0, "dueCount": 0},
        "_error": error,
    }


def _error_quiz_payload(topic: str, error: str) -> dict[str, Any]:
    return {
        "block_type": "QuizCard",
        "data": {
            "question": f"Error generating quiz for: {topic[:60]}",
            "questionType": "mcq",
            "options": [],
            "correctIndex": None,
            "explanation": error,
            "difficulty": _DEFAULT_DIFFICULTY,
            "source": {"id": "err", "docId": "", "docTitle": "", "page": None, "quote": ""},
        },
    }


def _error_feynman_payload(topic: str, error: str) -> dict[str, Any]:
    return {
        "block_type": "FeynmanExplainer",
        "data": {
            "concept": topic[:100],
            "explanation": f"Error generating explanation: {error}",
            "gaps": [],
            "source": {"id": "err", "docId": "", "docTitle": "", "page": None, "quote": ""},
        },
    }
