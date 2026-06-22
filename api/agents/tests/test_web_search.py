"""WebSearchAgent — academic discovery (Semantic Scholar / arXiv).

Network is mocked at the `_search_semantic_scholar` seam, so no live API
calls are made. Covers: paper→SourceList mapping, graceful degradation,
intent routing, and UIAgent rendering of the emitted block.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from api.agents.base import AgentResult, AgentState
from api.agents.graph import _detect_intent_from_query
from api.agents.tier3.ui_agent import UIAgent
from api.agents.tier4 import web_search as ws
from api.agents.tier4.web_search import WebSearchAgent, _paper_to_source_document

_PAPERS = [
    {
        "paperId": "p1",
        "title": "Attention Is All You Need",
        "url": "https://example.org/p1",
        "year": 2017,
        "externalIds": {"ArXiv": "1706.03762"},
    },
    {
        "paperId": "p2",
        "title": "GraphRAG",
        "externalIds": {"ArXiv": "2404.16130"},
    },
]


async def test_run_maps_papers_to_sourcelist():
    agent = WebSearchAgent()
    state = AgentState(query="find papers about transformers", notebook_id="nb1")
    with patch.object(ws, "_search_semantic_scholar", new=AsyncMock(return_value=_PAPERS)):
        result = await agent.run("find papers about transformers", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "SourceList"
    data = result.payload["data"]
    assert data["totalCount"] == 2
    assert data["notebookId"] == "nb1"
    assert data["documents"][0]["title"] == "Attention Is All You Need"
    assert data["documents"][0]["docId"] == "ss_p1"


async def test_run_degrades_to_partial_on_no_results():
    agent = WebSearchAgent()
    state = AgentState(query="nonsense xyzzy")
    with patch.object(ws, "_search_semantic_scholar", new=AsyncMock(return_value=[])):
        result = await agent.run("nonsense xyzzy", state=state)
    assert result.status == "partial"
    assert result.payload["data"]["totalCount"] == 0


async def test_run_degrades_when_api_raises():
    agent = WebSearchAgent()
    state = AgentState(query="anything")
    with patch.object(ws, "_search_semantic_scholar", new=AsyncMock(side_effect=RuntimeError("503"))):
        result = await agent.run("anything", state=state)
    assert result.status == "partial"  # never crashes the turn


def test_paper_mapping_falls_back_to_arxiv_url():
    doc = _paper_to_source_document(_PAPERS[1])  # no `url`, has ArXiv id
    assert doc["sourceUri"] == "https://arxiv.org/abs/2404.16130"
    assert doc["docId"] == "ss_p2"
    assert doc["status"] == "ready"


def test_intent_detection_routes_to_websearch():
    assert _detect_intent_from_query("find papers about diffusion models") == "websearch"
    assert _detect_intent_from_query("recent work on retrieval augmentation") == "websearch"
    assert _detect_intent_from_query("what does my corpus say?") == ""


async def test_ui_agent_renders_sourcelist_from_web_search():
    ui = UIAgent()
    state = AgentState(query="find papers")
    state.agent_results["web_search"] = AgentResult(
        agent_name="web_search",
        payload={
            "block_type": "SourceList",
            "data": {
                "notebookId": "nb1",
                "documents": [_paper_to_source_document(_PAPERS[0])],
                "totalCount": 1,
            },
        },
        status="ok",
    )
    await ui.run("find papers", state=state)
    assert len(state.ui_blocks) == 1
    assert state.ui_blocks[0].type == "SourceList"
