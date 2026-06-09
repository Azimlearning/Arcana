"""ContradictionAgent — cross-source disagreement detection tests."""

from __future__ import annotations

from api.agents.base import AgentState
from api.agents.tier2.contradiction import (
    ContradictionAgent,
    _parse_contradiction_response,
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


def _make_agent(llm_text: str, chunks: list[RetrievedChunk]) -> ContradictionAgent:
    r = _StubRetriever(chunks)
    return ContradictionAgent(
        llm_service=_StubLLM(response_text=llm_text),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )


_GOOD_RESPONSE = """\
{
  "concept": "RAG accuracy",
  "summary": "Sources disagree on whether RAG improves factual accuracy.",
  "claims": [
    {"docId": "doc1", "docTitle": "Paper A", "stance": "RAG improves accuracy", "quote": "RAG reduces hallucination by 40%"},
    {"docId": "doc2", "docTitle": "Paper B", "stance": "RAG does not improve accuracy", "quote": "We found no significant improvement"}
  ]
}
"""


# ---- Unit tests: parser -----------------------------------------------------


def test_parse_happy_path():
    chunks = [_chunk("c1", "doc1", "text")]
    result = _parse_contradiction_response(_GOOD_RESPONSE, chunks=chunks, query="RAG accuracy")
    assert result["block_type"] == "ContradictionAlert"
    data = result["data"]
    assert data["concept"] == "RAG accuracy"
    assert len(data["claims"]) == 2
    assert data["claims"][0]["stance"] == "RAG improves accuracy"


def test_parse_caps_at_four_claims():
    raw = """\
{
  "concept": "x",
  "summary": "y",
  "claims": [
    {"docId": "d1", "docTitle": "T1", "stance": "a", "quote": "q1"},
    {"docId": "d2", "docTitle": "T2", "stance": "b", "quote": "q2"},
    {"docId": "d3", "docTitle": "T3", "stance": "c", "quote": "q3"},
    {"docId": "d4", "docTitle": "T4", "stance": "d", "quote": "q4"},
    {"docId": "d5", "docTitle": "T5", "stance": "e", "quote": "q5"}
  ]
}"""
    chunks = [_chunk("c1", "d1", "text")]
    result = _parse_contradiction_response(raw, chunks=chunks, query="x")
    assert len(result["data"]["claims"]) == 4


def test_parse_broken_json_returns_defaults():
    chunks = [_chunk("c1", "d1", "text")]
    result = _parse_contradiction_response("not json", chunks=chunks, query="my query")
    assert result["block_type"] == "ContradictionAlert"
    assert "my query" in result["data"]["concept"]
    assert result["data"]["claims"] == []


def test_parse_truncates_long_quotes():
    long_quote = "x" * 300
    raw = f"""{{"concept": "c", "summary": "s", "claims": [{{"docId": "d", "docTitle": "T", "stance": "st", "quote": "{long_quote}"}}]}}"""
    chunks = [_chunk("c1", "d", "text")]
    result = _parse_contradiction_response(raw, chunks=chunks, query="q")
    assert len(result["data"]["claims"][0]["quote"]) <= 200


# ---- Integration tests: agent.run -------------------------------------------


async def test_run_returns_contradiction_alert():
    chunks = [_chunk("c1", "doc1", "RAG accuracy study.")]
    agent = _make_agent(_GOOD_RESPONSE, chunks)
    state = AgentState(query="does RAG improve accuracy?")
    result = await agent.run("does RAG improve accuracy?", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "ContradictionAlert"
    assert len(state.retrieved_ctx) == 1


async def test_run_fails_when_no_chunks():
    agent = _make_agent(_GOOD_RESPONSE, [])
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"


async def test_run_fails_when_llm_raises():
    r = _StubRetriever([_chunk("c1", "d1", "text")])
    agent = ContradictionAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("err")),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"
