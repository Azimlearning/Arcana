"""StudyPlannerAgent - Tier 4. Spaced-repetition schedule advisor.

Reads the current session's FlashcardDeck cards (from AgentState), filters
to those due today (via SM-2 is_due), and returns a FlashcardDeck payload
with dueCount set so the frontend can render the review queue.

If no cards are available from state (e.g. the agent is called standalone),
it falls back to a lightweight LLM call to suggest a study topic.

Tier-4 role: post-processing utility; never retrieves or synthesises content.
Uses llm_light (Haiku-4.5) for the fallback suggestion path — low stakes,
high frequency.

FR-LRN-02: spaced-repetition scheduling.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.learning.sm2 import from_wire, is_due
from api.llm.service import LLMService
from api.llm.types import Message

logger = get_logger(__name__)

_PLANNER_SYSTEM = (
    "You are a study coach. Given the user's query, suggest one specific topic "
    "they should review today, in one sentence. Be concise and direct."
)


class StudyPlannerAgent(BaseAgent):
    """Tier-4 utility agent. Produces due-card queue from SM-2 schedules."""

    name = "study_planner"
    tier = 4

    def __init__(self, *, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def run(self, query: str, state: AgentState) -> AgentResult:
        today = date.today()

        # Scan AgentState for any FlashcardDeck payloads produced this turn.
        due_cards: list[dict[str, Any]] = []
        all_cards: list[dict[str, Any]] = []

        for payload in _extract_flashcard_payloads(state):
            for card in payload.get("cards", []):
                all_cards.append(card)
                schedule_raw = card.get("schedule")
                if schedule_raw is None:
                    # New card — always due on first encounter.
                    due_cards.append(card)
                else:
                    try:
                        sched = from_wire(schedule_raw)
                        if is_due(sched, today):
                            due_cards.append(card)
                    except (KeyError, ValueError, TypeError):
                        due_cards.append(card)  # corrupt schedule → due

        if all_cards:
            topic = _infer_topic(state)
            return AgentResult(
                agent_name=self.name,
                payload={
                    "block_type": "FlashcardDeck",
                    "data": {
                        "topic": topic,
                        "cards": due_cards,
                        "totalCards": len(all_cards),
                        "dueCount": len(due_cards),
                    },
                },
                status="ok",
            )

        # No flashcard state — produce a lightweight suggestion.
        suggestion = await _suggest_topic(query, self._llm)
        return AgentResult(
            agent_name=self.name,
            payload={
                "block_type": "FlashcardDeck",
                "data": {
                    "topic": suggestion,
                    "cards": [],
                    "totalCards": 0,
                    "dueCount": 0,
                },
            },
            status="ok",
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_flashcard_payloads(state: AgentState) -> list[dict]:
    """Walk AgentState intermediate_results for FlashcardDeck payloads."""
    results: list[dict] = []
    for result in getattr(state, "intermediate_results", []):
        payload = getattr(result, "payload", {}) or {}
        if payload.get("block_type") == "FlashcardDeck":
            data = payload.get("data") or {}
            results.append(data)
    return results


def _infer_topic(state: AgentState) -> str:
    query: str = getattr(state, "query", "")
    return query[:80] if query else "Study session"


async def _suggest_topic(query: str, llm: LLMService) -> str:
    try:
        completion = await llm.complete(
            [Message(role="user", content=f"Query: {query[:200]}")],
            system=_PLANNER_SYSTEM,
            max_tokens=80,
        )
        return completion.text.strip()[:200] or "Review your notes today."
    except Exception:
        logger.warning("study_planner.llm_failed", query=query[:80])
        return "Review your notes today."
