"""Graph traversal retrieval — FR-RET-03.

Slice 1: the retriever actually traverses. Algorithm per query:

  1. Extract entities from the query text using the same prompt the
     ingestion extractor uses (lowercase, slug-canonicalised).
  2. For each query entity that EXISTS in the graph:
       - Score chunks listed in its `mentioned_in_chunks` property at
         weight 1.0 (direct entity match).
       - 1-hop expand the node; for each neighbor, score chunks in its
         `mentioned_in_chunks` at weight 0.5 (related entity).
  3. Top-k by accumulated score; fetch text via ChunkStore; return as
     `RetrievedChunk(source="graph")`.

Graceful degradation (NFR-REL-01):
  - `llm=None` → return [] (preserves slice-0 behaviour when an op runs
    without API keys).
  - Query-extraction failure → return [].
  - No matching entities → return [].
  - Missing chunks (graph references chunk_ids the chunk store no longer
    has, e.g. after a delete) → silently skipped.
"""

from __future__ import annotations

from typing import cast

from api.core.errors import IngestFailed
from api.core.logging import get_logger
from api.ingestion.extractor import extract_entities
from api.llm.service import LLMService
from api.retrieval.types import RetrievedChunk
from api.stores.chunk_store import ChunkStore
from api.stores.graph_store import GraphStore

logger = get_logger(__name__)

# Score weights: direct match dominates; 1-hop neighbors contribute half.
# v1 weights — bump GRAPH_SCORING_VERSION when tuning so R-02 benchmark
# results can be partitioned by scoring version.
GRAPH_SCORING_VERSION = "v1"
_DIRECT_MATCH_WEIGHT = 1.0
_NEIGHBOR_WEIGHT = 0.5


class GraphRetriever:
    def __init__(
        self,
        *,
        graph_store: GraphStore,
        chunk_store: ChunkStore | None = None,
        llm: LLMService | None = None,
    ) -> None:
        self._graph = graph_store
        self._chunks = chunk_store
        self._llm = llm

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        if self._llm is None or self._chunks is None:
            # No LLM or no chunk store wired - operator is running without
            # API keys, or the ingest pipeline never ran. Either way the
            # graph contribution to hybrid retrieval degrades cleanly.
            logger.debug(
                "graph_retriever.skip",
                reason="missing_llm_or_chunk_store",
                query_len=len(query),
            )
            return []

        # 1. Pull candidate entities from the query.
        try:
            extraction = await extract_entities(
                text=query,
                chunk_id="query",
                doc_id="query",
                llm=self._llm,
            )
        except IngestFailed as e:
            logger.warning("graph_retriever.extract_failed", error=str(e))
            return []

        if not extraction.nodes:
            return []

        # 2. Score chunks by direct + neighbor match.
        chunk_scores: dict[str, float] = {}
        for query_node in extraction.nodes:
            graph_node = await self._graph.get_node(query_node.id)
            if graph_node is None:
                continue   # query mentioned an entity not in the corpus
            direct_chunks = cast(
                list[str],
                graph_node.properties.get("mentioned_in_chunks", []) or [],
            )
            for cid in direct_chunks:
                chunk_scores[cid] = chunk_scores.get(cid, 0.0) + _DIRECT_MATCH_WEIGHT

            neighbors = await self._graph.expand(query_node.id, hops=1)
            for nbr in neighbors:
                nbr_chunks = cast(
                    list[str],
                    nbr.properties.get("mentioned_in_chunks", []) or [],
                )
                for cid in nbr_chunks:
                    chunk_scores[cid] = chunk_scores.get(cid, 0.0) + _NEIGHBOR_WEIGHT

        if not chunk_scores:
            return []

        # 3. Fetch chunk text in score-descending order, capped at top_k.
        ranked = sorted(chunk_scores.items(), key=lambda kv: kv[1], reverse=True)
        out: list[RetrievedChunk] = []
        for chunk_id, score in ranked:
            if len(out) >= top_k:
                break
            stored = await self._chunks.get(chunk_id)
            if stored is None:
                # Graph references a chunk that's been deleted - skip.
                continue
            out.append(
                RetrievedChunk(
                    id=stored.id,
                    doc_id=stored.doc_id,
                    text=stored.text,
                    page=stored.page,
                    score=score,
                    source="graph",
                )
            )
        return out
