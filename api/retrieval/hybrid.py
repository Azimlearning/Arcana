"""hybrid_retrieve — the FYP's primary evidence path (PRD §10.4 Listing 10.4).

Fans out to vector + BM25 + graph retrievers concurrently via
`asyncio.gather`, wrapping each in a safe-call so one retriever's failure
degrades the result rather than crashing the turn (NFR-REL-01). Fuses
with RRF and returns the top-k.

The slice's graph retriever returns [] (no entities yet), so today the
result is effectively `RRF(vector, bm25)`. As soon as entity extraction
lands, the graph contribution turns on with no caller change — that's
the design.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from api.core.logging import get_logger
from api.retrieval.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from api.retrieval.types import RetrievedChunk, RetrieverProtocol

logger = get_logger(__name__)


async def hybrid_retrieve(
    query: str,
    *,
    top_k: int = 10,
    vector_retriever: RetrieverProtocol,
    bm25_retriever: RetrieverProtocol,
    graph_retriever: RetrieverProtocol,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[RetrievedChunk]:
    """Run all three retrievers concurrently, fuse with RRF, return top-k."""
    # Each retriever pulls `top_k` candidates so RRF has enough to fuse
    # productively. Some literature suggests fetching `top_k * 2` per
    # retriever for better fusion quality — defer to P1 tuning.
    per_retriever_k = top_k

    vector_task = _safe_call(
        "vector", lambda: vector_retriever.retrieve(query, top_k=per_retriever_k)
    )
    bm25_task = _safe_call(
        "bm25", lambda: bm25_retriever.retrieve(query, top_k=per_retriever_k)
    )
    graph_task = _safe_call(
        "graph", lambda: graph_retriever.retrieve(query, top_k=per_retriever_k)
    )

    # gather returns a tuple; RRF expects a list of rankings.
    rankings = list(await asyncio.gather(vector_task, bm25_task, graph_task))
    fused = reciprocal_rank_fusion(rankings, k=rrf_k)
    return fused[:top_k]


async def _safe_call(
    name: str,
    fn: Callable[[], Awaitable[list[RetrievedChunk]]],
) -> list[RetrievedChunk]:
    """Call a retriever; on any exception, log and return []. NFR-REL-01.

    NOTE: `except Exception` deliberately does NOT catch `asyncio.CancelledError`
    (which subclasses `BaseException` in Python 3.8+). If a caller wraps
    `hybrid_retrieve` in a `wait_for` timeout, cancellation still propagates
    correctly and is not silently turned into a degraded result.
    """
    try:
        return await fn()
    except Exception as e:  # degrade rather than fail (cancellation excluded — see docstring)
        logger.warning("retrieval.failed", retriever=name, error=str(e))
        return []
