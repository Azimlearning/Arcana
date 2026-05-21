"""Research agent — retrieval + synthesis + citation parsing."""

from __future__ import annotations

from datetime import UTC, datetime

from api.agents.base import AgentState
from api.agents.tier2.research import (
    ResearchAgent,
    _build_citations,
    _build_segments,
    _parse_segments_and_citations,
)
from api.llm.types import Completion, Usage
from api.retrieval.types import RetrievedChunk
from api.stores.doc_store import DocMetadata

# ─── Helpers ──────────────────────────────────────────────────────


def _chunk(cid: str, doc_id: str, text: str, page: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        id=cid, doc_id=doc_id, text=text, page=page, score=0.9, source="vector"
    )


class _StubLLM:
    def __init__(self, *, response_text: str = "default", raise_exc: Exception | None = None) -> None:
        self._response = response_text
        self._raise = raise_exc
        self.calls: list[dict] = []

    async def complete(self, messages, *, system=None, tools=None, max_tokens=None, budget=None):
        self.calls.append({"messages": messages, "system": system, "max_tokens": max_tokens})
        if self._raise:
            raise self._raise
        return Completion(
            text=self._response,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=20),
            model="stub",
            provider="stub",
        )


class _StubRetriever:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self._results = results

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        return self._results[:top_k]


class _StubDocStore:
    def __init__(self, *, titles: dict[str, str]) -> None:
        self._titles = titles
        self.get_metadata_calls = 0

    async def get_metadata(self, doc_id):
        self.get_metadata_calls += 1
        if doc_id not in self._titles:
            from api.stores.errors import DocNotFound
            raise DocNotFound(f"no doc {doc_id}")
        return DocMetadata(
            id=doc_id,
            title=self._titles[doc_id],
            source_uri=f"/{doc_id}.pdf",
            content_type="application/pdf",
            size_bytes=1000,
            created_at=datetime.now(UTC),
        )

    # The other DocStore methods are unused by ResearchAgent but the ABC requires them.
    async def put(self, *a, **kw): ...
    async def get_bytes(self, *a, **kw): ...
    async def update_status(self, *a, **kw): ...
    async def list_documents(self): return []
    async def aclose(self): return None


def _make_agent(
    *,
    llm_response: str = "Default answer [c1].",
    chunks: list[RetrievedChunk] | None = None,
    titles: dict[str, str] | None = None,
    raise_llm: Exception | None = None,
    raise_retrieval: bool = False,
) -> tuple[ResearchAgent, _StubLLM, _StubDocStore]:
    llm = _StubLLM(response_text=llm_response, raise_exc=raise_llm)
    doc = _StubDocStore(titles=titles or {})
    chunks = chunks or []

    class _RaisingVec:
        async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
            raise RuntimeError("simulated outage")

    vec = _RaisingVec() if raise_retrieval else _StubRetriever(chunks)
    bm25 = _StubRetriever([])
    graph = _StubRetriever([])

    agent = ResearchAgent(
        llm_service=llm,  # type: ignore[arg-type]
        embedder=_StubEmbedder(),  # type: ignore[arg-type]
        vector_retriever=vec,
        bm25_retriever=bm25,
        graph_retriever=graph,
        doc_store=doc,  # type: ignore[arg-type]
    )
    return agent, llm, doc


class _StubEmbedder:
    async def embed(self, texts):
        return [[0.0] * 4 for _ in texts]


# ─── Happy path ───────────────────────────────────────────────────


async def test_research_returns_grounded_payload():
    chunks = [
        _chunk("ch1", "doc_alpha", "GraphRAG outperforms vector RAG on multi-hop.", page=4),
        _chunk("ch2", "doc_alpha", "Vector RAG is faster on single-hop.", page=7),
    ]
    agent, _llm, doc = _make_agent(
        llm_response="GraphRAG wins on multi-hop [c1]. Vector wins on single-hop [c2].",
        chunks=chunks,
        titles={"doc_alpha": "GraphRAG: A Survey"},
    )
    state = AgentState(query="how do these retrievers compare?")
    result = await agent.run("how do these retrievers compare?", state=state)

    assert result.status == "ok"
    assert result.agent_name == "research"
    payload = result.payload
    assert "GraphRAG wins" in payload["summary"]
    assert len(payload["citations"]) == 2
    assert payload["citations"][0]["id"] == "c1"
    assert payload["citations"][0]["docTitle"] == "GraphRAG: A Survey"
    assert payload["citations"][0]["page"] == 4
    # Title cache: 1 doc, 2 citations → 1 fetch.
    assert doc.get_metadata_calls == 1
    # State should have retrieved_ctx populated.
    assert len(state.retrieved_ctx) == 2
    # And agent_results should hold the result.
    assert state.agent_results["research"].status == "ok"


async def test_synthesis_prompt_contains_chunks():
    chunks = [_chunk("ch1", "d1", "Body of chunk one.", page=2)]
    agent, llm, _ = _make_agent(
        llm_response="Answer [c1].",
        chunks=chunks,
        titles={"d1": "Doc 1"},
    )
    state = AgentState(query="ask")
    await agent.run("ask", state=state)

    user_msg = llm.calls[0]["messages"][0]
    assert "USER QUESTION" in user_msg.content
    assert "ask" in user_msg.content
    assert "[c1]" in user_msg.content
    assert "Body of chunk one." in user_msg.content
    assert llm.calls[0]["system"] is not None
    assert "Cite every factual claim" in llm.calls[0]["system"]


# ─── Failure paths ────────────────────────────────────────────────


async def test_zero_chunks_returns_partial_with_no_evidence_msg():
    agent, _, _ = _make_agent(chunks=[])
    state = AgentState(query="x")
    result = await agent.run("x", state=state)
    assert result.status == "partial"
    assert "evidence" in (result.error or "").lower() or "0 chunks" in (result.error or "")
    assert result.payload["citations"] == []


async def test_llm_failure_returns_failed_status():
    chunks = [_chunk("ch1", "d1", "body", page=1)]
    agent, _, _ = _make_agent(
        chunks=chunks,
        raise_llm=RuntimeError("boom"),
        titles={"d1": "D"},
    )
    state = AgentState(query="x")
    result = await agent.run("x", state=state)
    assert result.status == "failed"
    assert "LLM" in (result.error or "")


async def test_retrieval_failure_returns_failed_status():
    # Hybrid wraps each retriever in _safe_call (NFR-REL-01), so a single
    # retriever failure does NOT raise out of hybrid_retrieve.
    # Research only sees an empty result → "partial" not "failed".
    agent, _, _ = _make_agent(chunks=[], raise_retrieval=True)
    state = AgentState(query="x")
    result = await agent.run("x", state=state)
    assert result.status == "partial"


# ─── Citation parser ──────────────────────────────────────────────


def test_citation_parser_builds_unique_citations():
    chunks = [
        _chunk("ch1", "d1", "first body", page=1),
        _chunk("ch2", "d1", "second body", page=2),
        _chunk("ch3", "d2", "third body", page=3),
    ]
    _segments, citations = _parse_segments_and_citations(
        "Alpha [c1] beta [c2][c3] gamma [c1].",
        chunks,
    )
    # 3 unique citations, ordered by first appearance.
    assert [c["id"] for c in citations] == ["c1", "c2", "c3"]


def test_citation_parser_ignores_out_of_range_indices():
    chunks = [_chunk("ch1", "d1", "body", page=1)]
    _, citations = _parse_segments_and_citations(
        "Bogus [c99] reference.",
        chunks,
    )
    assert citations == []


def test_segment_builder_groups_adjacent_markers():
    segments = _build_segments("Alpha [c1][c2] beta [c3].")
    assert len(segments) == 3
    assert segments[0]["text"] == "Alpha"
    assert segments[0]["citationIds"] == ["c1", "c2"]
    assert segments[1]["text"] == "beta"
    assert segments[1]["citationIds"] == ["c3"]
    assert segments[2]["text"] == "."
    assert segments[2]["citationIds"] == []


def test_segment_builder_trailing_uncited_text():
    segments = _build_segments("Cited [c1]. Uncited tail.")
    assert segments[0]["citationIds"] == ["c1"]
    assert segments[-1]["citationIds"] == []
    assert "Uncited" in segments[-1]["text"]


def test_quote_preview_truncated():
    long_chunk = _chunk("ch1", "d1", "x" * 500, page=1)
    citations = _build_citations("[c1]", [long_chunk])
    assert len(citations[0]["quote"]) <= 280


async def test_title_enrichment_falls_back_when_docstore_misses():
    chunks = [_chunk("ch1", "d_missing", "body", page=1)]
    agent, _, _doc = _make_agent(
        llm_response="Answer [c1].",
        chunks=chunks,
        titles={},  # docstore knows no docs → DocNotFound
    )
    state = AgentState(query="x")
    result = await agent.run("x", state=state)
    assert result.payload["citations"][0]["docTitle"] == "d_missing"
