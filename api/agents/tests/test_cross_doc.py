"""CrossDocAgent — InsightCard producer tests."""

from __future__ import annotations

from api.agents.base import AgentState
from api.agents.tier2.cross_doc import (
    CrossDocAgent,
    _parse_cross_doc_response,
    _unique_doc_ids,
)
from api.llm.types import Completion, Usage
from api.retrieval.types import RetrievedChunk

# ---- Helpers ----------------------------------------------------------------


def _chunk(cid: str, doc_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(id=cid, doc_id=doc_id, text=text, page=1, score=0.9, source="vector")


class _StubLLM:
    def __init__(self, response_text: str = "", raise_exc: Exception | None = None):
        self._response = response_text
        self._raise = raise_exc

    async def complete(self, messages, *, system=None, max_tokens=None, budget=None, tools=None):
        if self._raise:
            raise self._raise
        return Completion(
            text=self._response,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=50),
            model="stub",
            provider="stub",
        )


class _StubRetriever:
    def __init__(self, results: list[RetrievedChunk]):
        self._results = results

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        return self._results[:top_k]


def _make_agent(llm_text: str, chunks: list[RetrievedChunk]) -> CrossDocAgent:
    r = _StubRetriever(chunks)
    return CrossDocAgent(
        llm_service=_StubLLM(response_text=llm_text),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )


_GOOD_RESPONSE = """\
{
  "insight": "Both papers implicitly assume zero-shot generalisation despite different architectures.",
  "connection": "Shared assumption about model transferability across domains.",
  "docAId": "doc1",
  "docATitle": "RAG Paper",
  "docBId": "doc2",
  "docBTitle": "RLHF Paper",
  "citations": [
    {"id": "c1", "docId": "doc1", "docTitle": "RAG Paper", "page": null, "quote": "evaluated zero-shot"},
    {"id": "c2", "docId": "doc2", "docTitle": "RLHF Paper", "page": null, "quote": "generalises without fine-tuning"}
  ]
}
"""


# ---- Unit tests -------------------------------------------------------------


def test_unique_doc_ids_preserves_order():
    chunks = [
        _chunk("a", "doc1", "x"),
        _chunk("b", "doc2", "y"),
        _chunk("c", "doc1", "z"),
    ]
    assert _unique_doc_ids(chunks) == ["doc1", "doc2"]


def test_parse_happy_path():
    chunks = [_chunk("c1", "doc1", "t"), _chunk("c2", "doc2", "t")]
    result = _parse_cross_doc_response(_GOOD_RESPONSE, chunks=chunks, query="q")
    assert result["block_type"] == "InsightCard"
    data = result["data"]
    assert data["docAId"] == "doc1"
    assert data["docBId"] == "doc2"
    assert len(data["citations"]) == 2
    assert "zero-shot" in data["insight"]


def test_parse_broken_json_uses_chunk_fallbacks():
    chunks = [_chunk("c1", "doc1", "text A"), _chunk("c2", "doc2", "text B")]
    result = _parse_cross_doc_response("not json", chunks=chunks, query="my query")
    assert result["block_type"] == "InsightCard"
    data = result["data"]
    assert data["docAId"] == "doc1"
    assert data["docBId"] == "doc2"
    assert "my query" in data["insight"]
    # Should synthesise at least one citation from chunks
    assert len(data["citations"]) >= 1


def test_parse_truncates_long_quotes():
    long_quote = "q" * 300
    raw = f"""{{"insight":"i","connection":"c","docAId":"d1","docATitle":"T1","docBId":"d2","docBTitle":"T2",
"citations":[{{"id":"c1","docId":"d1","docTitle":"T1","page":null,"quote":"{long_quote}"}}]}}"""
    chunks = [_chunk("c1", "d1", "t"), _chunk("c2", "d2", "t")]
    result = _parse_cross_doc_response(raw, chunks=chunks, query="q")
    assert len(result["data"]["citations"][0]["quote"]) <= 200


# ---- Integration tests: agent.run -------------------------------------------


async def test_run_returns_insight_card():
    chunks = [_chunk("c1", "doc1", "text A"), _chunk("c2", "doc2", "text B")]
    agent = _make_agent(_GOOD_RESPONSE, chunks)
    state = AgentState(query="what connects these papers?")
    result = await agent.run("what connects these papers?", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "InsightCard"
    assert len(state.retrieved_ctx) == 2


async def test_run_fails_with_single_doc():
    chunks = [_chunk("c1", "doc1", "only one doc")]
    agent = _make_agent(_GOOD_RESPONSE, chunks)
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"
    assert "two documents" in (result.error or "")


async def test_run_fails_when_no_chunks():
    agent = _make_agent(_GOOD_RESPONSE, [])
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"
