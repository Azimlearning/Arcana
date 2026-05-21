"""BM25Retriever — index from ChunkStore, score, top-k, empty corpus."""

from __future__ import annotations

import pytest

from api.retrieval.bm25 import BM25Retriever
from api.stores.chunk_store import StoredChunk
from api.stores.jsonl_chunk_store import JsonlChunkStore


@pytest.fixture
async def chunk_store(tmp_path):
    s = JsonlChunkStore(root=tmp_path)
    await s.upsert_many([
        StoredChunk(id="c1", doc_id="d1", page=1, char_offset=0,
                    text="GraphRAG outperforms vector RAG on multi-hop reasoning questions."),
        StoredChunk(id="c2", doc_id="d1", page=2, char_offset=200,
                    text="Vector retrieval excels at single-hop semantic similarity."),
        StoredChunk(id="c3", doc_id="d2", page=1, char_offset=0,
                    text="The cat sat on the mat. Unrelated to the others."),
    ])
    return s


async def test_query_ranks_keyword_matches_higher(chunk_store):
    retriever = BM25Retriever(chunk_store=chunk_store)
    out = await retriever.retrieve("graphrag multi-hop", top_k=3)
    # c1 contains both keywords; c2 contains "vector"; c3 is unrelated.
    assert out, "expected at least one hit"
    assert out[0].id == "c1"
    assert out[0].source == "bm25"
    assert out[0].score > 0


async def test_empty_corpus_returns_empty(tmp_path):
    store = JsonlChunkStore(root=tmp_path)
    retriever = BM25Retriever(chunk_store=store)
    assert await retriever.retrieve("anything") == []


async def test_empty_query_returns_empty(chunk_store):
    retriever = BM25Retriever(chunk_store=chunk_store)
    assert await retriever.retrieve("") == []
    assert await retriever.retrieve("   ") == []


async def test_top_k_caps_results(chunk_store):
    retriever = BM25Retriever(chunk_store=chunk_store)
    out = await retriever.retrieve("retrieval RAG vector cat", top_k=1)
    assert len(out) <= 1


async def test_zero_score_hits_filtered(chunk_store):
    """Chunks with zero BM25 relevance for the query don't appear."""
    retriever = BM25Retriever(chunk_store=chunk_store)
    # `xyz123` doesn't appear in any chunk.
    out = await retriever.retrieve("xyz123", top_k=10)
    assert out == []
