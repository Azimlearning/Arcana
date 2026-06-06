"""WritingAgent — draft generation, response parsing, error paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from api.agents.base import AgentState
from api.agents.tier2.writing import (
    WritingAgent,
    _extract_json,
    _parse_draft_response,
    _strip_fences,
)

# ── Helpers ───────────────────────────────────────────────────────────────

def _mock_agent(llm_text: str) -> WritingAgent:
    llm = MagicMock()
    completion = MagicMock()
    completion.text = llm_text
    llm.complete = AsyncMock(return_value=completion)

    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=[])

    from api.retrieval.types import RetrievedChunk
    chunk = RetrievedChunk(id="c1", doc_id="d1", text="Transformers use attention.", page=1, score=0.9, source="vector")

    async def fake_hybrid(query, *, top_k, vector_retriever, bm25_retriever, graph_retriever):
        return [chunk]

    import api.agents.tier2.writing as mod
    mod.hybrid_retrieve = fake_hybrid  # type: ignore[attr-defined]

    return WritingAgent(
        llm_service=llm,
        vector_retriever=retriever,
        bm25_retriever=retriever,
        graph_retriever=retriever,
    )


def _draft_json() -> str:
    return """{
  "title": "Attention in Transformers",
  "sections": [
    {
      "heading": "Introduction",
      "body": "Transformers use self-attention [c1] to relate tokens.",
      "citationIds": ["c1"]
    },
    {
      "heading": "Key Mechanism",
      "body": "Queries, keys, and values are computed via linear projections [c1].",
      "citationIds": ["c1"]
    }
  ],
  "citations": [
    {"id": "c1", "docId": "d1", "docTitle": "Transformers paper", "page": 3, "quote": "attention is all you need"}
  ],
  "wordCount": 25
}"""


# ── Unit tests: parsing ───────────────────────────────────────────────────

def test_strip_fences_removes_json_fence():
    fenced = "```json\n{\"a\": 1}\n```"
    assert _strip_fences(fenced) == '{"a": 1}'


def test_extract_json_handles_plain_object():
    raw = '  {"title": "T", "sections": []} '
    result = _extract_json(raw)
    assert result["title"] == "T"


def test_parse_draft_response_happy_path():
    result = _parse_draft_response(_draft_json(), topic="Attention")
    assert result["block_type"] == "DraftEditor"
    data = result["data"]
    assert data["title"] == "Attention in Transformers"
    assert len(data["sections"]) == 2
    assert data["sections"][0]["heading"] == "Introduction"
    assert data["sections"][0]["citationIds"] == ["c1"]
    assert len(data["citations"]) == 1
    assert data["wordCount"] == 25


def test_parse_draft_response_broken_json_returns_empty_draft():
    result = _parse_draft_response("not json at all", topic="Fallback topic")
    assert result["block_type"] == "DraftEditor"
    data = result["data"]
    assert data["title"] == "Fallback topic"
    assert data["sections"] == []
    assert data["wordCount"] == 0


def test_parse_draft_response_computes_word_count_when_missing():
    raw = """{
  "title": "T",
  "sections": [{"heading": "H", "body": "one two three", "citationIds": []}],
  "citations": []
}"""
    result = _parse_draft_response(raw, topic="T")
    assert result["data"]["wordCount"] == 3


# ── Integration-style: agent.run ─────────────────────────────────────────

async def test_writing_agent_returns_ok_with_draft():
    agent = _mock_agent(_draft_json())
    state = AgentState(query="explain attention mechanism")
    result = await agent.run("explain attention mechanism", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "DraftEditor"
    assert result.payload["data"]["title"] == "Attention in Transformers"
    assert len(result.payload["data"]["sections"]) == 2


async def test_writing_agent_returns_failed_when_no_chunks():
    import api.agents.tier2.writing as mod

    async def no_chunks(query, *, top_k, vector_retriever, bm25_retriever, graph_retriever):
        return []

    mod.hybrid_retrieve = no_chunks  # type: ignore[attr-defined]

    llm = MagicMock()
    retriever = MagicMock()
    agent = WritingAgent(
        llm_service=llm,
        vector_retriever=retriever,
        bm25_retriever=retriever,
        graph_retriever=retriever,
    )
    state = AgentState(query="q")
    result = await agent.run("q", state=state)

    assert result.status == "failed"
    assert "No documents" in (result.error or "")


async def test_writing_agent_llm_raise_returns_ok_with_error_payload():
    """LLM crash → ok status + error DraftEditor (empty sections)."""
    from api.retrieval.types import RetrievedChunk
    chunk = RetrievedChunk(id="c1", doc_id="d1", text="context", page=1, score=0.9, source="vector")

    import api.agents.tier2.writing as mod

    async def one_chunk(query, *, top_k, vector_retriever, bm25_retriever, graph_retriever):
        return [chunk]

    mod.hybrid_retrieve = one_chunk  # type: ignore[attr-defined]

    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=RuntimeError("provider down"))
    retriever = MagicMock()

    agent = WritingAgent(
        llm_service=llm,
        vector_retriever=retriever,
        bm25_retriever=retriever,
        graph_retriever=retriever,
    )
    state = AgentState(query="draft something")
    result = await agent.run("draft something", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "DraftEditor"
    assert result.payload["data"]["sections"] == []
