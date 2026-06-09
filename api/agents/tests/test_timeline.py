"""TimelineAgent — chronological CitedSummary tests."""

from __future__ import annotations

from api.agents.base import AgentState
from api.agents.tier2.timeline_agent import TimelineAgent
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


def _make_agent(llm_text: str, chunks: list[RetrievedChunk]) -> TimelineAgent:
    r = _StubRetriever(chunks)
    return TimelineAgent(
        llm_service=_StubLLM(response_text=llm_text),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )


_TIMELINE_RESPONSE = (
    "In 2017, Vaswani et al. introduced the Transformer architecture [c1]. "
    "By 2020, GPT-3 scaled this to 175B parameters [c2]."
)


# ---- Tests ------------------------------------------------------------------


async def test_run_returns_cited_summary_with_citations():
    chunks = [
        _chunk("c1", "doc1", "Attention is All You Need, 2017."),
        _chunk("c2", "doc2", "GPT-3: Language Models are Few-Shot Learners, 2020."),
    ]
    agent = _make_agent(_TIMELINE_RESPONSE, chunks)
    state = AgentState(query="history of transformers")
    result = await agent.run("history of transformers", state=state)

    assert result.status == "ok"
    assert "2017" in result.payload["summary"]
    assert len(result.payload["citations"]) == 2
    assert len(state.retrieved_ctx) == 2


async def test_run_partial_when_no_chunks():
    agent = _make_agent("any", [])
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "partial"


async def test_run_fails_when_llm_raises():
    r = _StubRetriever([_chunk("c1", "d1", "text")])
    agent = TimelineAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("err")),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"
