"""Flat-RAG baseline — same corpus, embeddings, and chunking; no graph retriever.

Methodological guard (R-02): the only variable between this baseline and
Arcana's hybrid pipeline is whether the graph retriever contributes to the
RRF fusion. Embeddings, corpus, chunking, and the synthesis prompt are
held constant.

Usage (from run_benchmark.py — not meant as a standalone entry point):

    from eval.baseline_flat_rag import flat_retrieve

    flat_chunks = await flat_retrieve(
        query,
        top_k=10,
        vector_retriever=vector_retriever,
        bm25_retriever=bm25_retriever,
    )
"""

from __future__ import annotations

from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrievedChunk, RetrieverProtocol


class NullRetriever:
    """A retriever that always returns an empty list.

    Injected as `graph_retriever` in the flat-RAG baseline so that
    `hybrid_retrieve` runs only vector + BM25, excluding any graph
    contribution. This is the single and only difference between the
    hybrid and flat pipelines.
    """

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        return []


async def flat_retrieve(
    query: str,
    *,
    top_k: int = 10,
    vector_retriever: RetrieverProtocol,
    bm25_retriever: RetrieverProtocol,
) -> list[RetrievedChunk]:
    """Run flat-RAG retrieval: vector + BM25 via RRF, graph disabled.

    Uses the same `hybrid_retrieve` function as the full pipeline so
    any RRF tuning applies equally to both pipelines (R-02 guard).
    """
    return await hybrid_retrieve(
        query,
        top_k=top_k,
        vector_retriever=vector_retriever,
        bm25_retriever=bm25_retriever,
        graph_retriever=NullRetriever(),
    )
