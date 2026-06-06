"""UI Agent — block construction, validation, error paths."""

from __future__ import annotations

from api.agents.base import AgentResult, AgentState
from api.agents.tier3.ui_agent import UIAgent
from api.genui._generated import CitedSummary


def _research_payload(*, summary: str = "Answer [c1].") -> dict:
    return {
        "summary": summary,
        "segments": [{"text": "Answer", "citationIds": ["c1"]}],
        "citations": [
            {
                "id": "c1",
                "docId": "doc_alpha",
                "docTitle": "Alpha.pdf",
                "page": 4,
                "quote": "supporting quote",
            }
        ],
    }


async def test_emits_ready_block_for_successful_research():
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload=_research_payload(),
        status="ok",
    )

    agent = UIAgent()
    result = await agent.run("x", state=state)

    assert result.status == "ok"
    assert len(state.ui_blocks) == 1
    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary)
    assert block.type == "CitedSummary"
    assert block.meta.status == "ready"
    assert block.meta.panel == "chat"
    assert block.id.startswith("block_")
    assert block.data.summary == "Answer [c1]."
    assert block.data.citations[0].docTitle == "Alpha.pdf"


async def test_emits_error_block_when_research_failed():
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload={},
        status="failed",
        error="something exploded",
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert block.meta.status == "error"
    assert isinstance(block, CitedSummary)
    assert "something exploded" in block.data.summary


async def test_emits_partial_block_when_research_partial():
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload=_research_payload(),
        status="partial",
        error="no evidence",
    )

    agent = UIAgent()
    await agent.run("x", state=state)
    assert state.ui_blocks[0].meta.status == "partial"


async def test_emits_error_block_when_research_absent():
    """Invariant #6: even with no research result, we MUST emit a block."""
    state = AgentState(query="x")  # no agent_results

    agent = UIAgent()
    await agent.run("x", state=state)
    assert len(state.ui_blocks) == 1
    assert state.ui_blocks[0].meta.status == "error"


async def test_invalid_payload_falls_through_to_error_block():
    """Fail-closed: invariant #2 — never ship a malformed UIBlock.

    If research returns a payload that doesn't match CitedSummaryData,
    UIAgent emits an error block rather than crashing or shipping garbage."""
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload={"summary": "ok", "segments": "this should be a list", "citations": []},
        status="ok",
    )
    agent = UIAgent()
    await agent.run("x", state=state)
    block = state.ui_blocks[0]
    assert block.meta.status == "error"
    assert isinstance(block, CitedSummary)
    assert "schema validation" in block.data.summary.lower()


# ── Chunk 3: intent/mode routing (FR-UI-04) ────────────────────────────────


def _gap_analysis_payload() -> dict:
    return {
        "block_type": "GapAnalysis",
        "data": {
            "summary": "Several gaps were found.",
            "gaps": [
                {"label": "Gap A", "description": "Missing X.", "severity": "high"}
            ],
            "coveredTopics": ["Topic 1"],
        },
    }



async def test_routes_to_gap_analysis_from_discovery():
    """When discovery agent returns block_type=GapAnalysis, UI Agent emits one."""
    from api.genui._generated import GapAnalysis

    state = AgentState(query="x")
    state.agent_results["discovery"] = AgentResult(
        agent_name="discovery",
        payload=_gap_analysis_payload(),
        status="ok",
    )

    agent = UIAgent()
    result = await agent.run("x", state=state)

    assert result.status == "ok"
    assert len(state.ui_blocks) == 1
    block = state.ui_blocks[0]
    assert isinstance(block, GapAnalysis)
    assert block.type == "GapAnalysis"
    assert block.meta.status == "ready"
    assert block.meta.panel == "studio"
    assert block.data.summary == "Several gaps were found."
    assert block.data.gaps[0].severity == "high"



async def test_falls_back_to_cited_summary_when_discovery_absent():
    """Without a discovery result, UI Agent falls through to CitedSummary."""
    state = AgentState(query="x")
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload=_research_payload(),
        status="ok",
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary)
    assert block.type == "CitedSummary"


async def test_discovery_invalid_payload_falls_through_to_cited_summary():
    """When discovery payload is malformed, UI Agent silently falls through."""
    state = AgentState(query="x")
    state.agent_results["discovery"] = AgentResult(
        agent_name="discovery",
        payload={"block_type": "GapAnalysis", "data": {"bad": "field"}},
        status="ok",
    )
    state.agent_results["research"] = AgentResult(
        agent_name="research",
        payload=_research_payload(),
        status="ok",
    )

    agent = UIAgent()
    await agent.run("x", state=state)

    block = state.ui_blocks[0]
    assert isinstance(block, CitedSummary), "should fall through to CitedSummary"
