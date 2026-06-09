"""AnnotationAgent — claim-coverage GapAnalysis tests."""

from __future__ import annotations

from api.agents.base import AgentState
from api.agents.tier2.annotation import AnnotationAgent, _parse_annotation_response
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


def _make_agent(llm_text: str, chunks: list[RetrievedChunk]) -> AnnotationAgent:
    r = _StubRetriever(chunks)
    return AnnotationAgent(
        llm_service=_StubLLM(response_text=llm_text),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )


_GOOD_RESPONSE = """\
{
  "summary": "Coverage is partial — methodology is well-covered but evaluation is shallow.",
  "gaps": [
    {"label": "Evaluation benchmarks", "description": "No standard benchmarks used.", "severity": "high"},
    {"label": "Ablation studies", "description": "No component isolation tests.", "severity": "medium"}
  ],
  "coveredTopics": ["Architecture", "Training procedure", "Dataset description"]
}
"""


# ---- Unit tests: parser -----------------------------------------------------


def test_parse_happy_path():
    result = _parse_annotation_response(_GOOD_RESPONSE, query="RAG coverage")
    assert result["block_type"] == "GapAnalysis"
    data = result["data"]
    assert len(data["gaps"]) == 2
    assert data["gaps"][0]["severity"] == "high"
    assert "Architecture" in data["coveredTopics"]


def test_parse_invalid_severity_clamped():
    raw = '{"summary": "ok", "gaps": [{"label": "g", "description": "d", "severity": "critical"}], "coveredTopics": []}'
    result = _parse_annotation_response(raw, query="q")
    assert result["data"]["gaps"][0]["severity"] == "medium"


def test_parse_broken_json_returns_defaults():
    result = _parse_annotation_response("not json", query="my annotation query")
    assert result["block_type"] == "GapAnalysis"
    assert "my annotation query" in result["data"]["summary"]
    assert result["data"]["gaps"] == []


# ---- Integration tests: agent.run -------------------------------------------


async def test_run_returns_gap_analysis():
    chunks = [_chunk("c1", "doc1", "RAG architecture overview.")]
    agent = _make_agent(_GOOD_RESPONSE, chunks)
    state = AgentState(query="annotate RAG coverage")
    result = await agent.run("annotate RAG coverage", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "GapAnalysis"
    assert len(state.retrieved_ctx) == 1


async def test_run_fails_when_no_chunks():
    agent = _make_agent(_GOOD_RESPONSE, [])
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"


async def test_run_fails_when_llm_raises():
    r = _StubRetriever([_chunk("c1", "d1", "text")])
    agent = AnnotationAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("err")),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"
