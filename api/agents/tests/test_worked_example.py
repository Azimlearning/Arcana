"""Integration tests for the Listing 12.1 worked example.

Validates: intent detection, A2A hops (route_to_agent), and 3-block UIAgent output.
  'Compare how these three papers treat attention'
  -> orchestrator detects compare intent
  -> comparator runs: A2A hop 1 -> graph_agent, A2A hop 2 -> contradiction
  -> UIAgent emits [LiteratureMatrix, KnowledgeGraphView, ContradictionAlert]
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.agents.base import AgentResult, AgentState, registry, route_to_agent
from api.agents.graph import _detect_intent_from_query
from api.agents.tier3.ui_agent import UIAgent

# ---------------------------------------------------------------------------
# Intent detection unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query,expected", [
    ("Compare how these three papers treat attention", "compare"),
    ("A vs B: differences between transformers", "compare"),
    ("contrast the two methodologies", "compare"),
    ("What is similar between paper A and paper B?", "compare"),
    ("Does this paper contradict the literature?", "contradiction"),
    ("inconsistent findings across sources", "contradiction"),
    ("Show me the knowledge graph of transformers", "graph"),
    ("Give me the timeline of deep learning", "timeline"),
    ("What is the history of attention mechanisms", "timeline"),
    ("Summarise this paper", ""),
    ("What did paper X say about BERT?", ""),
])
def test_detect_intent_from_query(query: str, expected: str) -> None:
    assert _detect_intent_from_query(query) == expected


# ---------------------------------------------------------------------------
# route_to_agent writes back to state.agent_results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_to_agent_writes_to_state() -> None:
    registry.reset()
    mock_agent = MagicMock()
    mock_agent.name = "dummy"
    mock_agent.run = AsyncMock(return_value=AgentResult(
        agent_name="dummy", payload={"ok": True}, status="ok"
    ))
    registry.register_agent(mock_agent)

    state = AgentState(query="test")
    result = await route_to_agent("dummy", "test", state=state)

    assert result.status == "ok"
    assert state.agent_results["dummy"] is result
    registry.reset()


@pytest.mark.asyncio
async def test_route_to_agent_missing_writes_failed_to_state() -> None:
    registry.reset()
    state = AgentState(query="test")
    result = await route_to_agent("nonexistent", "test", state=state)
    assert result.status == "failed"
    assert state.agent_results["nonexistent"] is result


# ---------------------------------------------------------------------------
# UIAgent multi-block compare path
# ---------------------------------------------------------------------------

def _make_literature_matrix_result() -> AgentResult:
    return AgentResult(
        agent_name="comparator",
        payload={
            "block_type": "LiteratureMatrix",
            "data": {
                "query": "compare attention",
                "dimensions": ["Approach", "Findings"],
                "rows": [
                    {"docId": "doc1", "docTitle": "Paper A",
                     "cells": [{"text": "self-attention", "citationId": None},
                                {"text": "state-of-the-art", "citationId": None}]},
                    {"docId": "doc2", "docTitle": "Paper B",
                     "cells": [{"text": "cross-attention", "citationId": None},
                                {"text": "competitive", "citationId": None}]},
                ],
                "citations": [],
            },
        },
        status="ok",
    )


def _make_graph_view_result() -> AgentResult:
    return AgentResult(
        agent_name="graph_agent",
        payload={
            "block_type": "KnowledgeGraphView",
            "data": {
                "nodes": [{"id": "n1", "label": "attention", "nodeType": "concept",
                            "properties": {}}],
                "edges": [],
                "focusNodeId": "n1",
            },
        },
        status="ok",
    )


def _make_contradiction_result() -> AgentResult:
    return AgentResult(
        agent_name="contradiction",
        payload={
            "block_type": "ContradictionAlert",
            "data": {
                "concept": "attention",
                "summary": "Papers disagree on attention mechanism design.",
                "claims": [
                    {"docId": "doc1", "docTitle": "Paper A",
                     "stance": "self-attention is optimal",
                     "quote": "self-attention achieves best results"},
                    {"docId": "doc2", "docTitle": "Paper B",
                     "stance": "cross-attention scales better",
                     "quote": "cross-attention outperforms at scale"},
                ],
            },
        },
        status="ok",
    )


@pytest.mark.asyncio
async def test_ui_agent_compare_emits_three_blocks() -> None:
    """With comparator + graph_agent + contradiction results in state,
    UIAgent should emit all three blocks (PRD Listing 12.1)."""
    ui = UIAgent()
    state = AgentState(query="compare three papers on attention")
    state.agent_results["comparator"] = _make_literature_matrix_result()
    state.agent_results["graph_agent"] = _make_graph_view_result()
    state.agent_results["contradiction"] = _make_contradiction_result()

    result = await ui.run(state.query, state)

    assert result.status == "ok"
    assert len(state.ui_blocks) == 3
    types = [b.type for b in state.ui_blocks]
    assert "LiteratureMatrix" in types
    assert "KnowledgeGraphView" in types
    assert "ContradictionAlert" in types


@pytest.mark.asyncio
async def test_ui_agent_compare_emits_one_block_without_a2a() -> None:
    """Without graph/contradiction results, only LiteratureMatrix is emitted."""
    ui = UIAgent()
    state = AgentState(query="compare papers")
    state.agent_results["comparator"] = _make_literature_matrix_result()

    result = await ui.run(state.query, state)

    assert result.status == "ok"
    assert len(state.ui_blocks) == 1
    assert state.ui_blocks[0].type == "LiteratureMatrix"


@pytest.mark.asyncio
async def test_ui_agent_compare_partial_a2a_two_blocks() -> None:
    """Graph ran but contradiction did not — 2 blocks emitted."""
    ui = UIAgent()
    state = AgentState(query="compare papers")
    state.agent_results["comparator"] = _make_literature_matrix_result()
    state.agent_results["graph_agent"] = _make_graph_view_result()

    result = await ui.run(state.query, state)

    assert result.status == "ok"
    assert len(state.ui_blocks) == 2
    types = [b.type for b in state.ui_blocks]
    assert "LiteratureMatrix" in types
    assert "KnowledgeGraphView" in types


@pytest.mark.asyncio
async def test_ui_agent_single_doc_compare_falls_through_to_cited_summary() -> None:
    """Single-doc comparator path (CitedSummary payload) uses original single-block routing."""
    ui = UIAgent()
    state = AgentState(query="compare this single paper")
    state.agent_results["comparator"] = AgentResult(
        agent_name="comparator",
        payload={"summary": "Only one doc.", "segments": [], "citations": []},
        status="ok",
    )

    result = await ui.run(state.query, state)

    assert result.status == "ok"
    assert len(state.ui_blocks) == 1
    assert state.ui_blocks[0].type == "CitedSummary"
