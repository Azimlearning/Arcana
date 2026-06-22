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
from typing import Literal

from api.core.logging import get_logger
from api.retrieval.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from api.retrieval.types import RetrievedChunk, RetrieverProtocol

logger = get_logger(__name__)


RetrievalMode = Literal["local", "global", "hybrid", "auto"]

# Query markers that steer the `auto` mode (FR-RET-07). Global = broad/thematic
# questions best answered from corpus-wide + community structure; local =
# specific-entity questions best answered from dense + graph-neighbourhood.
_GLOBAL_MARKERS = (
    "overview", "summary", "summarise", "summarize", "themes", "main ideas",
    "across all", "in general", "broadly", "high-level", "key topics",
    "landscape", "overall", "what are the main",
)
_LOCAL_MARKERS = (
    "what is", "who is", "define", "definition of", "explain the term",
    "specifically", "exactly", "precise",
)


def resolve_retrieval_mode(query: str, mode: RetrievalMode) -> Literal["local", "global", "hybrid"]:
    """Resolve `auto` to a concrete mode from query shape; pass others through.

    Heuristic (FR-RET-07): thematic/broad phrasing -> global; short or
    definitional phrasing -> local; otherwise the balanced hybrid fan-out."""
    if mode != "auto":
        return mode
    q = query.lower()
    if any(m in q for m in _GLOBAL_MARKERS):
        return "global"
    if any(m in q for m in _LOCAL_MARKERS) or len(query.split()) <= 4:
        return "local"
    return "hybrid"


# Which retrievers each resolved mode fans out to. Local is entity-centric
# (dense + graph neighbourhood); global favours corpus-wide keyword coverage
# + graph/community structure; hybrid uses all three (the §10.4 default).
_MODE_RETRIEVERS: dict[str, tuple[str, ...]] = {
    "local": ("vector", "graph"),
    "global": ("bm25", "graph"),
    "hybrid": ("vector", "bm25", "graph"),
}


async def hybrid_retrieve(
    query: str,
    *,
    top_k: int = 10,
    vector_retriever: RetrieverProtocol,
    bm25_retriever: RetrieverProtocol,
    graph_retriever: RetrieverProtocol,
    rrf_k: int = DEFAULT_RRF_K,
    mode: RetrievalMode = "hybrid",
) -> list[RetrievedChunk]:
    """Run all three retrievers concurrently, fuse with RRF, return top-k."""
    # Each retriever pulls `top_k` candidates so RRF has enough to fuse
    # productively. Some literature suggests fetching `top_k * 2` per
    # retriever for better fusion quality — defer to P1 tuning.
    per_retriever_k = top_k

    # FR-RET-07: resolve the (possibly auto) mode, then fan out only to the
    # retrievers that mode calls for. RRF fuses whichever ran — a disabled
    # retriever is simply absent from the rankings, never a degraded-failure.
    resolved = resolve_retrieval_mode(query, mode)
    active = _MODE_RETRIEVERS[resolved]
    retrievers = {
        "vector": vector_retriever,
        "bm25": bm25_retriever,
        "graph": graph_retriever,
    }
    logger.info("retrieval.mode", requested=mode, resolved=resolved, retrievers=active)

    tasks = [
        _safe_call(name, lambda r=retrievers[name]: r.retrieve(query, top_k=per_retriever_k))
        for name in active
    ]
    rankings = list(await asyncio.gather(*tasks))
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
