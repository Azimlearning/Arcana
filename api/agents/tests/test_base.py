"""Base agent layer — registry, @tool, route_to_agent, AgentState shape."""

from __future__ import annotations

import pytest

from api.agents.base import (
    AgentResult,
    AgentState,
    BaseAgent,
    registry,
    route_to_agent,
    tool,
)
from api.core.budget import TokenBudget


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the global registry around every test in this module."""
    registry.reset()
    yield
    registry.reset()


# ─── @tool decorator ──────────────────────────────────────────────


async def test_tool_decorator_registers_schema():
    @tool(agent="research", tier=2)
    async def search_docs(query: str, top_k: int = 10) -> list[str]:
        """Search the corpus for chunks matching the query."""
        return []

    specs = registry.tools_for("research")
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "search_docs"
    assert spec.agent == "research" and spec.tier == 2
    # `query` is required (no default), `top_k` is optional.
    assert spec.input_schema["required"] == ["query"]
    assert spec.input_schema["properties"]["query"] == {"type": "string"}
    assert spec.input_schema["properties"]["top_k"] == {"type": "integer"}


async def test_tool_schema_handles_list_and_optional():
    @tool(agent="research", tier=2)
    async def expand_concepts(
        concepts: list[str],
        doc_id: str | None = None,
    ) -> list[str]:
        """Expand a list of concepts via graph traversal."""
        return []

    spec = registry.tools_for("research")[0]
    assert spec.input_schema["properties"]["concepts"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    # Optional[str] should unwrap to {"type": "string"} (the slice's loose
    # JSON-schema mapping; full union handling lives in subsystem 8+).
    assert spec.input_schema["properties"]["doc_id"] == {"type": "string"}


async def test_tool_returns_function_unchanged():
    """The decorator must return the function as-is so it stays directly callable."""
    @tool(agent="research", tier=2)
    async def echo(query: str) -> str:
        """Echo the query back."""
        return query

    out = await echo("hello")
    assert out == "hello"


# ─── route_to_agent ───────────────────────────────────────────────


class _StubAgent(BaseAgent):
    name = "stub"
    tier = 2

    def __init__(self, *, returns: AgentResult) -> None:
        self._returns = returns
        self.call_count = 0

    async def run(self, query: str, state: AgentState) -> AgentResult:
        self.call_count += 1
        return self._returns


async def test_route_to_agent_dispatches_and_charges_hop():
    stub = _StubAgent(returns=AgentResult(agent_name="stub", payload={"ok": True}))
    registry.register_agent(stub)
    state = AgentState(query="hi", budget=TokenBudget(hops_limit=4))

    result = await route_to_agent("stub", "go", state=state)
    assert result.payload == {"ok": True}
    assert stub.call_count == 1
    assert state.budget.hops_used == 1


async def test_route_to_agent_returns_partial_when_budget_exceeded():
    stub = _StubAgent(returns=AgentResult(agent_name="stub", payload={"never": True}))
    registry.register_agent(stub)
    state = AgentState(query="hi", budget=TokenBudget(hops_limit=1, hops_used=1))

    result = await route_to_agent("stub", "go", state=state)
    assert result.status == "partial"
    assert "budget" in (result.error or "").lower()
    assert stub.call_count == 0  # never dispatched


async def test_route_to_agent_returns_failed_when_target_missing():
    state = AgentState(query="hi")
    result = await route_to_agent("not_registered", "go", state=state)
    assert result.status == "failed"
    assert "not_registered" in (result.error or "")


# ─── AgentState shape ────────────────────────────────────────────


async def test_agent_state_defaults_are_safe():
    s = AgentState(query="hello")
    assert s.messages == []
    assert s.retrieved_ctx == []
    assert s.agent_results == {}
    assert s.ui_blocks == []
    assert s.budget.tokens_used == 0
    assert s.budget.hops_used == 0
    assert s.active_mode == "research"
