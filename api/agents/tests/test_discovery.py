"""DiscoveryAgent - gap analysis, JSON parsing, fallback behavior."""

from __future__ import annotations

from api.agents.base import AgentState
from api.agents.tier2.discovery import DiscoveryAgent, _parse_gap_response, _strip_fences
from api.llm.types import Completion, Usage
from api.retrieval.types import RetrievedChunk

# ---- Helpers ----------------------------------------------------------------


def _chunk(cid: str, doc_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(id=cid, doc_id=doc_id, text=text, page=1, score=0.9, source="vector")


class _StubLLM:
    def __init__(self, *, response_text: str = "", raise_exc: Exception | None = None) -> None:
        self._response = response_text
        self._raise = raise_exc
        self.calls: list = []

    async def complete(self, messages, *, system=None, max_tokens=None, budget=None, tools=None):
        self.calls.append({"messages": messages, "system": system})
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
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self._results = results

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        return self._results[:top_k]


def _make_agent(llm_text: str, chunks: list[RetrievedChunk]) -> DiscoveryAgent:
    r = _StubRetriever(chunks)
    return DiscoveryAgent(
        llm_service=_StubLLM(response_text=llm_text),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )


_GOOD_RESPONSE = """
{
  "summary": "Several gaps found in methodology coverage.",
  "gaps": [
    {"label": "Longitudinal studies", "description": "No long-term follow-up data.", "severity": "high"},
    {"label": "Sample diversity", "description": "Studies lack demographic diversity.", "severity": "medium"}
  ],
  "coveredTopics": ["RAG architecture", "embedding models"]
}
"""


# ---- Unit tests: response parser --------------------------------------------


def test_strip_fences_removes_json_fence():
    raw = """```json
{"a": 1}
```"""
    assert _strip_fences(raw) == '{"a": 1}'


def test_strip_fences_no_fence_unchanged():
    raw = '{"a": 1}'
    assert _strip_fences(raw) == '{"a": 1}'


def test_parse_gap_response_happy_path():
    result = _parse_gap_response(_GOOD_RESPONSE, query="test query")
    assert result["block_type"] == "GapAnalysis"
    data = result["data"]
    assert "gaps" in data and len(data["gaps"]) == 2
    assert data["gaps"][0]["severity"] == "high"
    assert "RAG architecture" in data["coveredTopics"]


def test_parse_gap_response_invalid_severity_clamped():
    raw = '{"summary": "x", "gaps": [{"label": "g", "description": "d", "severity": "critical"}], "coveredTopics": []}'
    result = _parse_gap_response(raw, query="q")
    assert result["data"]["gaps"][0]["severity"] == "medium"


def test_parse_gap_response_broken_json_returns_defaults():
    result = _parse_gap_response("not json at all", query="my query")
    assert result["block_type"] == "GapAnalysis"
    assert "my query" in result["data"]["summary"]
    assert result["data"]["gaps"] == []


def test_parse_gap_response_empty_fields_safe():
    result = _parse_gap_response("{}", query="q")
    assert isinstance(result["data"]["gaps"], list)
    assert isinstance(result["data"]["coveredTopics"], list)


# ---- Integration tests: agent run -------------------------------------------


async def test_run_returns_gap_analysis_payload():
    chunks = [_chunk("c1", "doc1", "RAG architecture overview.")]
    agent = _make_agent(_GOOD_RESPONSE, chunks)
    state = AgentState(query="what are the gaps?")

    result = await agent.run("what are the gaps?", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "GapAnalysis"
    data = result.payload["data"]
    assert len(data["gaps"]) == 2
    # Chunks appended to state (invariant #1 verified)
    assert len(state.retrieved_ctx) == 1


async def test_run_fails_gracefully_when_no_chunks():
    agent = _make_agent(_GOOD_RESPONSE, [])
    state = AgentState(query="x")
    result = await agent.run("x", state=state)
    assert result.status == "failed"
    assert "No documents" in (result.error or "")


async def test_run_fails_gracefully_when_llm_raises():
    chunks = [_chunk("c1", "doc1", "some text")]
    r = _StubRetriever(chunks)
    agent = DiscoveryAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("timeout")),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )
    state = AgentState(query="x")
    result = await agent.run("x", state=state)
    assert result.status == "failed"
    assert "LLM call failed" in (result.error or "")
