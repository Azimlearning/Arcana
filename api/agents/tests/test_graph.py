"""LangGraph StateGraph wiring — node deltas, reducer math, terminal join.

Slice 1 chunk 1. These tests lock the contracts the graph relies on:
  - `make_node` returns only DELTAS (so the `add` reducer doesn't double-count)
  - Multiple nodes in sequence accumulate deltas correctly
  - A node whose target agent isn't registered returns a failed AgentResult
    instead of crashing the graph
  - The terminal join (research → ui_agent → END) still emits exactly
    one UIBlock per turn after going through the graph.
"""

from __future__ import annotations

import pytest

from api.agents.base import AgentResult, AgentState, BaseAgent, registry
from api.agents.graph import build_graph, make_node
from api.genui._generated import BlockMeta, CitedSummary, CitedSummaryData
from api.retrieval.types import RetrievedChunk


@pytest.fixture(autouse=True)
def clean_registry():
    registry.reset()
    yield
    registry.reset()


# ── Stubs ────────────────────────────────────────────────────────


def _chunk(cid: str) -> RetrievedChunk:
    return RetrievedChunk(
        id=cid, doc_id="d1", text="body", page=1, score=0.5, source="vector"
    )


def _block(bid: str) -> CitedSummary:
    return CitedSummary(
        type="CitedSummary",
        id=bid,
        meta=BlockMeta(panel="chat", order=0, status="ready"),
        data=CitedSummaryData(summary="hi", segments=[], citations=[]),
    )


class _MutatingAgent(BaseAgent):
    """Agent that mutates state during run() and returns AgentResult."""

    def __init__(self, name: str, *, chunks: list | None = None,
                 blocks: list | None = None) -> None:
        self.name = name
        self.tier = 2
        self._chunks = chunks or []
        self._blocks = blocks or []

    async def run(self, query: str, state: AgentState) -> AgentResult:
        # Simulate Research-style state mutation
        state.retrieved_ctx.extend(self._chunks)
        state.ui_blocks.extend(self._blocks)
        return AgentResult(
            agent_name=self.name,
            payload={"ran": True, "chunks": len(self._chunks)},
            status="ok",
        )


# ── make_node ─────────────────────────────────────────────────────


async def test_node_returns_only_deltas_for_appended_lists():
    """The wrapper must emit list-slices not full lists, so the `add`
    reducer appends rather than concatenating duplicates."""
    agent = _MutatingAgent(
        "stub",
        chunks=[_chunk("ch1"), _chunk("ch2")],
        blocks=[_block("blk_1")],
    )
    registry.register_agent(agent)

    # Pre-populate state to verify the wrapper diffs against current length.
    state = AgentState(
        query="hi",
        retrieved_ctx=[_chunk("pre_existing")],
        ui_blocks=[_block("blk_pre")],
    )

    node = make_node("stub")
    update = await node(state)

    # Only the NEW chunks/blocks, not the pre-existing ones.
    assert len(update["retrieved_ctx"]) == 2
    assert update["retrieved_ctx"][0].id == "ch1"
    assert len(update["ui_blocks"]) == 1
    assert update["ui_blocks"][0].id == "blk_1"
    assert update["agent_results"]["stub"].status == "ok"


async def test_node_omits_fields_when_agent_changes_nothing():
    """No retrieved_ctx delta → no `retrieved_ctx` key in the update.
    Empty list would still trigger the `add` reducer (a no-op append),
    but keeping the dict clean makes traces easier to read."""

    class _PureAgent(BaseAgent):
        name = "pure"
        tier = 2

        async def run(self, query, state):
            return AgentResult(agent_name=self.name, payload={}, status="ok")

    registry.register_agent(_PureAgent())
    state = AgentState(query="hi")
    node = make_node("pure")
    update = await node(state)
    assert set(update.keys()) == {"agent_results"}


async def test_node_for_missing_agent_returns_failed_result():
    """Reference to an unregistered agent doesn't crash the graph - it
    surfaces as a `failed` AgentResult that downstream nodes can read."""
    node = make_node("never_registered")
    state = AgentState(query="hi")
    update = await node(state)
    result = update["agent_results"]["never_registered"]
    assert result.status == "failed"
    assert "not registered" in (result.error or "")


async def test_node_catches_agent_exception_and_marks_failed():
    """An agent's RuntimeError must not propagate out of the node - it
    becomes a `failed` AgentResult so the graph terminates cleanly."""

    class _BoomAgent(BaseAgent):
        name = "boom"
        tier = 2

        async def run(self, query, state):
            raise RuntimeError("simulated explosion")

    registry.register_agent(_BoomAgent())
    state = AgentState(query="hi")
    node = make_node("boom")
    update = await node(state)
    result = update["agent_results"]["boom"]
    assert result.status == "failed"
    assert "RuntimeError" in (result.error or "")
    assert "simulated explosion" in (result.error or "")


# ── End-to-end graph wiring ──────────────────────────────────────


async def test_build_graph_compiles_with_required_nodes_registered():
    """Smoke test: with research + ui_agent stubs registered, the graph
    builds and a single ainvoke produces the expected blocks. The
    orchestrator node is a free function (not registered as an agent),
    so it doesn't need to be in the registry."""
    registry.register_agent(
        _MutatingAgent(
            "research",
            chunks=[_chunk("ch1")],
        )
    )
    registry.register_agent(
        _MutatingAgent("ui_agent", blocks=[_block("blk_terminal")])
    )

    graph = build_graph()
    state = AgentState(query="end-to-end")
    final = await graph.ainvoke(state)

    # langgraph with Pydantic state returns either a Pydantic instance or
    # a dict-like AddableValuesDict; tolerate both for forward-compat.
    def _get(field: str):
        return final[field] if isinstance(final, dict) else getattr(final, field)

    assert "research" in _get("agent_results")
    assert "ui_agent" in _get("agent_results")
    assert "orchestrator" in _get("agent_results")
    assert _get("intent") == "research"
    # The terminal block from ui_agent must be present.
    block_ids = [b.id for b in _get("ui_blocks")]
    assert "blk_terminal" in block_ids
    # Retrieved chunks accumulated through reducers.
    chunk_ids = [c.id for c in _get("retrieved_ctx")]
    assert "ch1" in chunk_ids
