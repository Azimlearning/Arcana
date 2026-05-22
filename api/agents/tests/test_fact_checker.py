"""Fact Checker — verdict-producing agent, fail-safe semantics."""

from __future__ import annotations

import pytest

from api.agents.base import AgentResult, AgentState, registry
from api.agents.tier4.fact_checker import FactChecker, _parse_verdicts
from api.llm.types import Completion, Usage


@pytest.fixture(autouse=True)
def clean_registry():
    registry.reset()
    yield
    registry.reset()


# ── Verdict JSON parser ──────────────────────────────────────────


def test_parse_verdicts_plain_array():
    out = _parse_verdicts('[{"id": "c1", "supported": true}, {"id": "c2", "supported": false}]')
    assert out == {"c1": True, "c2": False}


def test_parse_verdicts_strips_fences():
    out = _parse_verdicts('```json\n[{"id":"c1","supported":true}]\n```')
    assert out == {"c1": True}


def test_parse_verdicts_returns_empty_on_garbage():
    assert _parse_verdicts("not json") == {}


def test_parse_verdicts_skips_malformed_items():
    out = _parse_verdicts('[{"id":"c1","supported":true},{"id":"c2"},"junk"]')
    assert out == {"c1": True}


# ── Fact Checker behaviour ───────────────────────────────────────


class _StubLLM:
    def __init__(self, *, text: str = "[]", raise_exc: Exception | None = None) -> None:
        self._text = text
        self._raise = raise_exc

    async def complete(self, messages, *, system=None, tools=None, max_tokens=None, budget=None):
        if self._raise:
            raise self._raise
        return Completion(
            text=self._text,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=20),
            model="stub", provider="stub",
        )


def _state_with_research(citations: list[dict], *, status: str = "ok") -> AgentState:
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload={
            "summary": "claim A [c1] and claim B [c2].",
            "segments": [
                {"text": "claim A", "citationIds": ["c1"]},
                {"text": "claim B", "citationIds": ["c2"]},
            ],
            "citations": citations,
        },
        status=status,  # type: ignore[arg-type]
    )
    return state


async def test_no_research_result_returns_zero_check():
    state = AgentState(query="x")
    checker = FactChecker(llm=_StubLLM())  # type: ignore[arg-type]
    result = await checker.run("x", state=state)
    assert result.status == "ok"
    assert result.payload == {"checked": 0, "verified": 0, "dropped_ids": []}


async def test_failed_research_skips_verification():
    """Don't fact-check what didn't run."""
    state = _state_with_research([{"id": "c1", "quote": "x"}], status="failed")
    checker = FactChecker(llm=_StubLLM())  # type: ignore[arg-type]
    result = await checker.run("x", state=state)
    assert result.payload["checked"] == 0


async def test_no_citations_returns_zero_check():
    state = _state_with_research([])
    checker = FactChecker(llm=_StubLLM())  # type: ignore[arg-type]
    result = await checker.run("x", state=state)
    assert result.payload == {"checked": 0, "verified": 0, "dropped_ids": []}


async def test_all_supported_keeps_all():
    citations = [
        {"id": "c1", "docId": "d1", "docTitle": "D", "page": 1, "quote": "q1"},
        {"id": "c2", "docId": "d1", "docTitle": "D", "page": 2, "quote": "q2"},
    ]
    state = _state_with_research(citations)
    llm = _StubLLM(text='[{"id":"c1","supported":true},{"id":"c2","supported":true}]')
    checker = FactChecker(llm=llm)  # type: ignore[arg-type]
    result = await checker.run("x", state=state)
    assert result.payload["checked"] == 2
    assert result.payload["verified"] == 2
    assert result.payload["dropped_ids"] == []


async def test_one_unsupported_appears_in_dropped_ids():
    citations = [
        {"id": "c1", "docId": "d1", "docTitle": "D", "page": 1, "quote": "q1"},
        {"id": "c2", "docId": "d1", "docTitle": "D", "page": 2, "quote": "q2"},
    ]
    state = _state_with_research(citations)
    llm = _StubLLM(text='[{"id":"c1","supported":true},{"id":"c2","supported":false}]')
    checker = FactChecker(llm=llm)  # type: ignore[arg-type]
    result = await checker.run("x", state=state)
    assert result.payload["verified"] == 1
    assert result.payload["dropped_ids"] == ["c2"]


async def test_llm_failure_treats_all_as_supported():
    """Fail-safe: a transient LLM outage must NOT silently delete legitimate work."""
    citations = [
        {"id": "c1", "docId": "d1", "docTitle": "D", "page": 1, "quote": "q1"},
    ]
    state = _state_with_research(citations)
    llm = _StubLLM(raise_exc=RuntimeError("api down"))
    checker = FactChecker(llm=llm)  # type: ignore[arg-type]
    result = await checker.run("x", state=state)
    assert result.status == "ok"
    assert result.payload["verified"] == 1
    assert result.payload["dropped_ids"] == []


async def test_unknown_id_in_verdicts_defaults_to_supported():
    """LLM might forget to verdict a citation - treat as supported."""
    citations = [
        {"id": "c1", "docId": "d1", "docTitle": "D", "page": 1, "quote": "q1"},
        {"id": "c2", "docId": "d1", "docTitle": "D", "page": 2, "quote": "q2"},
    ]
    state = _state_with_research(citations)
    # Only c1 returned; c2 omitted entirely.
    llm = _StubLLM(text='[{"id":"c1","supported":true}]')
    checker = FactChecker(llm=llm)  # type: ignore[arg-type]
    result = await checker.run("x", state=state)
    assert result.payload["verified"] == 2   # both kept
    assert result.payload["dropped_ids"] == []
