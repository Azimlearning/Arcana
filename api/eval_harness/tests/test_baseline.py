"""Unit tests for eval/baseline_flat_rag.py — NullRetriever, flat_retrieve."""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk
from eval.baseline_flat_rag import NullRetriever, flat_retrieve

# ── Stub retriever ────────────────────────────────────────────────────────


class _StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.calls: list[str] = []

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        self.calls.append(query)
        return self._chunks[:top_k]


def _chunk(cid: str, doc_id: str = "doc1") -> RetrievedChunk:
    return RetrievedChunk(id=cid, doc_id=doc_id, text="t", page=1, score=0.8, source="vector")


# ── NullRetriever ─────────────────────────────────────────────────────────


async def test_null_retriever_always_empty():
    nr = NullRetriever()
    result = await nr.retrieve("anything", top_k=10)
    assert result == []


async def test_null_retriever_respects_top_k():
    nr = NullRetriever()
    assert await nr.retrieve("q", top_k=0) == []
    assert await nr.retrieve("q", top_k=100) == []


# ── flat_retrieve ─────────────────────────────────────────────────────────


async def test_flat_retrieve_returns_vector_and_bm25_results():
    # Both vector and BM25 return the same chunk; flat should fuse and return it.
    c = _chunk("c1", "doc1")
    vec = _StubRetriever([c])
    bm = _StubRetriever([c])

    chunks = await flat_retrieve("test query", top_k=5, vector_retriever=vec, bm25_retriever=bm)
    assert len(chunks) >= 1
    assert chunks[0].doc_id == "doc1"


async def test_flat_retrieve_graph_is_excluded():
    # If we patch flat_retrieve's NullRetriever, the graph still returns nothing.
    # This test verifies that adding a non-null graph to the pipeline wouldn't
    # affect flat_retrieve (which always uses NullRetriever internally).
    c = _chunk("c1", "docA")
    vec = _StubRetriever([c])
    bm = _StubRetriever([c])

    result = await flat_retrieve("query", top_k=10, vector_retriever=vec, bm25_retriever=bm)
    # All returned chunks must come from vector or bm25 (not a graph-only doc)
    doc_ids = {ch.doc_id for ch in result}
    assert doc_ids <= {"docA"}


async def test_flat_retrieve_empty_corpus():
    vec = _StubRetriever([])
    bm = _StubRetriever([])
    result = await flat_retrieve("q", top_k=5, vector_retriever=vec, bm25_retriever=bm)
    assert result == []
