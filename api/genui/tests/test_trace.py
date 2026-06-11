"""Unit tests for api/genui/trace.py — build_trace()."""

from __future__ import annotations

from api.agents.base import AgentResult, AgentState
from api.core.budget import TokenBudget
from api.genui.trace import build_trace


def _state(intent: str = "research", hops_used: int = 0) -> AgentState:
    s = AgentState(query="test query")
    s.intent = intent
    s.budget = TokenBudget()
    s.budget.hops_used = hops_used  # type: ignore[attr-defined]
    return s


def _ok(name: str) -> AgentResult:
    return AgentResult(agent_name=name, payload={}, status="ok")


def _failed(name: str) -> AgentResult:
    return AgentResult(agent_name=name, payload={}, status="failed", error="boom")


# ---------------------------------------------------------------------------
# Basic trace shape
# ---------------------------------------------------------------------------

def test_empty_state_returns_no_agents() -> None:
    state = _state()
    result = build_trace(state)
    assert result["agents"] == []
    assert result["hops_used"] == 0
    assert result["intent"] == "research"


def test_research_path_agents_and_tiers() -> None:
    state = _state(intent="research", hops_used=0)
    state.agent_results["orchestrator"] = _ok("orchestrator")
    state.agent_results["research"] = _ok("research")
    state.agent_results["ui_agent"] = _ok("ui_agent")

    result = build_trace(state)
    names = [a["name"] for a in result["agents"]]
    tiers = [a["tier"] for a in result["agents"]]
    assert names == ["orchestrator", "research", "ui_agent"]
    assert tiers == [1, 2, 3]


def test_all_agents_not_hop_when_hops_zero() -> None:
    state = _state(intent="research", hops_used=0)
    for name in ("orchestrator", "research", "fact_checker", "ui_agent"):
        state.agent_results[name] = _ok(name)

    result = build_trace(state)
    assert all(not a["is_hop"] for a in result["agents"])


# ---------------------------------------------------------------------------
# A2A hop detection
# ---------------------------------------------------------------------------

def test_compare_path_marks_graph_and_contradiction_as_hops() -> None:
    state = _state(intent="compare", hops_used=2)
    state.agent_results["orchestrator"] = _ok("orchestrator")
    state.agent_results["comparator"] = _ok("comparator")
    state.agent_results["graph_agent"] = _ok("graph_agent")
    state.agent_results["contradiction"] = _ok("contradiction")
    state.agent_results["ui_agent"] = _ok("ui_agent")

    result = build_trace(state)
    by_name = {a["name"]: a for a in result["agents"]}

    assert not by_name["orchestrator"]["is_hop"]
    assert not by_name["comparator"]["is_hop"]   # primary agent for "compare"
    assert by_name["graph_agent"]["is_hop"]       # A2A hop 1
    assert by_name["contradiction"]["is_hop"]     # A2A hop 2
    assert not by_name["ui_agent"]["is_hop"]      # tier 3, not tier 2


def test_no_hops_when_budget_zero_even_with_extra_agents() -> None:
    state = _state(intent="compare", hops_used=0)
    state.agent_results["comparator"] = _ok("comparator")
    state.agent_results["graph_agent"] = _ok("graph_agent")

    result = build_trace(state)
    assert all(not a["is_hop"] for a in result["agents"])


# ---------------------------------------------------------------------------
# Status propagation
# ---------------------------------------------------------------------------

def test_failed_agent_status_preserved() -> None:
    state = _state(intent="research", hops_used=0)
    state.agent_results["research"] = _failed("research")

    result = build_trace(state)
    assert result["agents"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# Unknown agent falls back to tier 2
# ---------------------------------------------------------------------------

def test_unknown_agent_defaults_to_tier_2() -> None:
    state = _state()
    state.agent_results["custom_agent"] = _ok("custom_agent")

    result = build_trace(state)
    assert result["agents"][0]["tier"] == 2


# ---------------------------------------------------------------------------
# Intent preserved in output
# ---------------------------------------------------------------------------

def test_intent_appears_in_trace() -> None:
    state = _state(intent="socratic")
    result = build_trace(state)
    assert result["intent"] == "socratic"


def test_empty_intent_falls_back_to_research() -> None:
    state = AgentState(query="test")
    state.intent = ""
    result = build_trace(state)
    assert result["intent"] == "research"
