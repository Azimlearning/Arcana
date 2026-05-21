"""Graph traversal retrieval — FR-RET-03.

Slice scope: the graph is empty (entity extraction defers to the next
slice per the slice ADR). This module exists so `hybrid_retrieve` can
call all three retrievers uniformly; `retrieve()` simply returns [].

REMOVE THE SLICE-SHAPE STUB WHEN entity extraction lands (next slice).
The next slice fills in:
  1. Entity extraction from the query (top-k named entities / concepts).
  2. Match those against `GraphStore` nodes.
  3. `graph_store.expand(node_id, hops)` to gather neighborhoods.
  4. Map neighborhood nodes back to chunks via a `mentioned_in` edge
     (which the ingestion pipeline will create when extraction lands).
"""

from __future__ import annotations

from api.core.logging import get_logger
from api.retrieval.types import RetrievedChunk
from api.stores.graph_store import GraphStore

logger = get_logger(__name__)


class GraphRetriever:
    def __init__(self, *, graph_store: GraphStore) -> None:
        self._graph = graph_store

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        # Slice: graph is empty. Log once at info so a future regression
        # ("we built entity extraction but the retriever still returns []")
        # is visible in traces.
        logger.debug("graph_retriever.skip", reason="slice_no_entities", query_len=len(query))
        return []
