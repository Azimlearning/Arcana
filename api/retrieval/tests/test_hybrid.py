"""hybrid_retrieve — gather, fuse, top-k, NFR-REL-01 degradation."""

from __future__ import annotations

from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrievedChunk


class _StubRetriever:
    """Looks like VectorRetriever / BM25Retriever / GraphRetriever
    structurally (only the `retrieve()` coroutine is called by hybrid)."""

    def __init__(self, results: list[RetrievedChunk], *, raise_exc: Exception | None = None) -> None:
        self._results = results
        self._raise = raise_exc
        self.calls = 0

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        self.calls += 1
        if self._raise:
            raise self._raise
        return self._results[:top_k]


def _c(cid: str, source: str = "vector") -> RetrievedChunk:
    return RetrievedChunk(
        id=cid, doc_id="d1", text=f"chunk {cid}", page=1, score=0.5,
        source=source,  # type: ignore[arg-type]
    )


async def test_fuses_three_retrievers():
    vec = _StubRetriever([_c("a"), _c("b"), _c("c")])
    bm25 = _StubRetriever([_c("b", "bm25"), _c("d", "bm25"), _c("e", "bm25")])
    graph = _StubRetriever([])  # slice-shape: graph is empty
    out = await hybrid_retrieve(
        "query",
        top_k=5,
        vector_retriever=vec,
        bm25_retriever=bm25,
        graph_retriever=graph,
    )
    # All three got called.
    assert vec.calls == bm25.calls == graph.calls == 1
    # `b` appears in both rankings → boosted; should outrank singletons.
    ids = [c.id for c in out]
    assert ids[0] == "b"
    assert set(ids) >= {"a", "b", "c", "d", "e"} - {"x"}   # all uniques present
    assert all(c.source == "hybrid" for c in out)


async def test_one_retriever_raising_does_not_kill_query():
    """NFR-REL-01: a single retriever failure degrades to the others'
    results rather than 500-ing the whole turn."""
    vec = _StubRetriever([_c("a"), _c("b")])
    bm25 = _StubRetriever([], raise_exc=RuntimeError("simulated outage"))
    graph = _StubRetriever([])
    out = await hybrid_retrieve(
        "query",
        top_k=5,
        vector_retriever=vec,
        bm25_retriever=bm25,
        graph_retriever=graph,
    )
    assert [c.id for c in out] == ["a", "b"]


async def test_all_retrievers_failing_returns_empty():
    vec = _StubRetriever([], raise_exc=RuntimeError("v"))
    bm25 = _StubRetriever([], raise_exc=RuntimeError("b"))
    graph = _StubRetriever([], raise_exc=RuntimeError("g"))
    out = await hybrid_retrieve(
        "query",
        top_k=5,
        vector_retriever=vec,
        bm25_retriever=bm25,
        graph_retriever=graph,
    )
    assert out == []


async def test_top_k_respected():
    vec = _StubRetriever([_c(f"v{i}") for i in range(20)])
    bm25 = _StubRetriever([_c(f"b{i}", "bm25") for i in range(20)])
    graph = _StubRetriever([])
    out = await hybrid_retrieve(
        "query",
        top_k=3,
        vector_retriever=vec,
        bm25_retriever=bm25,
        graph_retriever=graph,
    )
    assert len(out) == 3
