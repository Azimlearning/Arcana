"""GraphRetriever — slice scope: returns empty until entity extraction lands.

REMOVE BOTH TESTS WHEN entity extraction lands (next slice). The
`test_slice_returns_empty_until_extraction_lands` test below locks the
slice's intentional no-op behaviour; once extraction is wired the
GraphRetriever will return real results and these tests would need to
be replaced with traversal-shape assertions, not adjusted in place.
"""

from __future__ import annotations

from api.retrieval.graph import GraphRetriever
from api.stores.graph_store import GraphEdge, GraphNode
from api.stores.networkx_store import NetworkXGraphStore


async def test_empty_graph_returns_empty():
    store = NetworkXGraphStore()
    retriever = GraphRetriever(graph_store=store)
    assert await retriever.retrieve("anything", top_k=5) == []


async def test_slice_returns_empty_until_extraction_lands():
    """SLICE-ONLY: even with nodes in the graph, the slice's retriever
    doesn't traverse — entity extraction is the missing prerequisite.
    REMOVE WHEN entity extraction lands (next slice)."""
    store = NetworkXGraphStore()
    await store.upsert_node(GraphNode(id="alpha", type="Concept", label="Alpha"))
    await store.upsert_node(GraphNode(id="beta", type="Concept", label="Beta"))
    await store.upsert_edge(GraphEdge(src="alpha", dst="beta", type="MENTIONS"))
    retriever = GraphRetriever(graph_store=store)
    assert await retriever.retrieve("alpha beta", top_k=5) == []
