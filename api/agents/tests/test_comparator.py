"""ComparatorAgent — comparison-framed CitedSummary tests."""

from __future__ import annotations

from api.agents.base import AgentState
from api.agents.tier2.comparator import ComparatorAgent
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


def _make_agent(llm_text: str, chunks: list[RetrievedChunk]) -> ComparatorAgent:
    r = _StubRetriever(chunks)
    return ComparatorAgent(
        llm_service=_StubLLM(response_text=llm_text),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )


_COMPARISON_RESPONSE = (
    "RAG and RLHF differ fundamentally in their feedback mechanism. [c1] "
    "RAG relies on retrieved documents, whereas RLHF [c2] uses human preference signals."
)


# ---- Tests ------------------------------------------------------------------


async def test_run_returns_cited_summary_payload():
    chunks = [
        _chunk("c1", "doc1", "RAG retrieval pipeline."),
        _chunk("c2", "doc2", "RLHF human feedback loop."),
    ]
    agent = _make_agent(_COMPARISON_RESPONSE, chunks)
    state = AgentState(query="compare RAG and RLHF")
    result = await agent.run("compare RAG and RLHF", state=state)

    assert result.status == "ok"
    assert "summary" in result.payload
    assert len(result.payload["citations"]) == 2
    assert len(state.retrieved_ctx) == 2


async def test_run_no_citations_when_no_markers():
    chunks = [_chunk("c1", "d1", "text")]
    agent = _make_agent("A pure comparison with no citation markers.", chunks)
    state = AgentState(query="compare x and y")
    result = await agent.run("compare x and y", state=state)

    assert result.status == "ok"
    assert result.payload["citations"] == []
    assert len(result.payload["segments"]) == 1


async def test_run_partial_status_when_no_chunks():
    agent = _make_agent("any response", [])
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "partial"


async def test_run_fails_when_llm_raises():
    r = _StubRetriever([_chunk("c1", "d1", "text")])
    agent = ComparatorAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("err")),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"
