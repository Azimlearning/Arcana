"""StudyPlannerAgent - Tier 4. Spaced-repetition schedule advisor.

Reads the current session's FlashcardDeck cards (from AgentState), filters
to those due today (via SM-2 is_due), and returns a StudyPlanner payload
with the due-card queue so the frontend can render the session view.

If no cards are available from state the agent returns an empty StudyPlanner
payload (totalDue=0) which renders the EmptyState in the frontend.

Tier-4 role: post-processing utility; never retrieves or synthesises content.
Uses llm_light (Haiku-4.5) for nothing in this path - fully deterministic.

FR-LRN-09: study queue view.
FR-LRN-10: session goal tracking.
"""

from __future__ import annotations

from datetime import date
from math import ceil
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.learning.sm2 import from_wire, is_due
from api.llm.service import LLMService

logger = get_logger(__name__)

_SESSION_GOAL = 10


class StudyPlannerAgent(BaseAgent):
    name = "study_planner"
    tier = 4

    def __init__(self, *, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def run(self, query: str, state: AgentState) -> AgentResult:
        today = date.today()
        topic = _infer_topic(state)

        due_cards: list[dict[str, Any]] = []
        not_due_dates: list[str] = []

        for payload in _extract_flashcard_payloads(state):
            deck_topic = str(payload.get("topic") or topic)
            for i, card in enumerate(payload.get("cards", [])):
                schedule_raw = card.get("schedule")
                if schedule_raw is None:
                    due_cards.append(_build_due_card(card, deck_topic, i, today.isoformat(), overdue=False))
                else:
                    try:
                        sched = from_wire(schedule_raw)
                        raw_due = schedule_raw.get("dueAt", today.isoformat())
                        if is_due(sched, today):
                            overdue = str(raw_due) < today.isoformat()
                            due_cards.append(_build_due_card(card, deck_topic, i, str(raw_due), overdue=overdue))
                        else:
                            not_due_dates.append(str(raw_due))
                    except (KeyError, ValueError, TypeError):
                        due_cards.append(_build_due_card(card, deck_topic, i, today.isoformat(), overdue=False))

        overdue_count = sum(1 for c in due_cards if c.get("overdue"))
        next_session_at: str | None = min(not_due_dates) if not_due_dates else None

        return AgentResult(
            agent_name=self.name,
            payload={
                "block_type": "StudyPlanner",
                "data": {
                    "notebookId": query[:80],
                    "dueCards": due_cards,
                    "totalDue": len(due_cards),
                    "overdueCount": overdue_count,
                    "nextSessionAt": next_session_at,
                    "sessionGoal": _SESSION_GOAL,
                    "pomodoro": _build_pomodoro(len(due_cards), _SESSION_GOAL),
                },
            },
            status="ok",
        )


# -- Helpers ------------------------------------------------------------------


_CARDS_PER_CYCLE = 5
_FOCUS_MINUTES = 25
_BREAK_MINUTES = 5
_LONG_BREAK_MINUTES = 15


def _build_pomodoro(total_due: int, session_goal: int) -> dict | None:
    """Size a Pomodoro plan to this session's workload (FR-LRN-09).

    Covers min(total_due, session_goal) cards in focus blocks of
    `_CARDS_PER_CYCLE`; returns None for an empty queue so the schema's
    optional `pomodoro` field is simply absent."""
    workload = min(total_due, session_goal)
    if workload <= 0:
        return None
    cycles = max(1, ceil(workload / _CARDS_PER_CYCLE))
    return {
        "focusMinutes": _FOCUS_MINUTES,
        "breakMinutes": _BREAK_MINUTES,
        "longBreakMinutes": _LONG_BREAK_MINUTES,
        "cycles": cycles,
        "cardsPerCycle": _CARDS_PER_CYCLE,
    }


def _extract_flashcard_payloads(state: AgentState) -> list[dict]:
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


def _build_due_card(card: dict, topic: str, index: int, due_at: str, *, overdue: bool) -> dict:
    schedule_raw = card.get("schedule") or {}
    return {
        "cardId": f"card_{index}",
        "front": str(card.get("front") or ""),
        "topic": topic[:80],
        "dueAt": due_at,
        "intervalDays": int(schedule_raw.get("interval", 0)),
        "overdue": overdue,
    }
