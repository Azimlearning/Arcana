"""NetworkXGraphStore — upsert, expand, paths, analytics, persistence."""

from __future__ import annotations

import pytest

from api.stores.errors import GraphStoreError
from api.stores.graph_store import GraphEdge, GraphNode
from api.stores.networkx_store import NetworkXGraphStore


def _node(node_id: str, type_: str = "Concept", **props) -> GraphNode:
    return GraphNode(id=node_id, type=type_, label=node_id.title(), properties=props)


async def test_upsert_node_then_lookup_via_expand():
    g = NetworkXGraphStore()
    await g.upsert_node(_node("graphrag"))
    await g.upsert_node(_node("hybrid_retrieval"))
    await g.upsert_edge(GraphEdge(src="graphrag", dst="hybrid_retrieval", type="MENTIONS"))
    neighbors = await g.expand("graphrag", hops=1)
    assert {n.id for n in neighbors} == {"hybrid_retrieval"}
    assert neighbors[0].label == "Hybrid_Retrieval"


async def test_upsert_edge_requires_existing_endpoints():
    g = NetworkXGraphStore()
    await g.upsert_node(_node("a"))
    with pytest.raises(GraphStoreError):
        await g.upsert_edge(GraphEdge(src="a", dst="missing", type="X"))


async def test_expand_traverses_multiple_hops():
    g = NetworkXGraphStore()
    for n in ("a", "b", "c", "d"):
        await g.upsert_node(_node(n))
    await g.upsert_edge(GraphEdge(src="a", dst="b", type="L"))
    await g.upsert_edge(GraphEdge(src="b", dst="c", type="L"))
    await g.upsert_edge(GraphEdge(src="c", dst="d", type="L"))

    one_hop = await g.expand("a", hops=1)
    two_hop = await g.expand("a", hops=2)
    three_hop = await g.expand("a", hops=3)
    assert {n.id for n in one_hop} == {"b"}
    assert {n.id for n in two_hop} == {"b", "c"}
    assert {n.id for n in three_hop} == {"b", "c", "d"}


async def test_expand_returns_empty_for_missing_node():
    g = NetworkXGraphStore()
    assert await g.expand("missing", hops=2) == []


async def test_shortest_path_basic_and_missing():
    g = NetworkXGraphStore()
    for n in ("a", "b", "c"):
        await g.upsert_node(_node(n))
    await g.upsert_edge(GraphEdge(src="a", dst="b", type="L"))
    await g.upsert_edge(GraphEdge(src="b", dst="c", type="L"))
    assert await g.shortest_path("a", "c") == ["a", "b", "c"]
    assert await g.shortest_path("a", "missing") is None
    # Disconnected components → no path
    await g.upsert_node(_node("island"))
    assert await g.shortest_path("a", "island") is None


async def test_pagerank_returns_score_per_node():
    g = NetworkXGraphStore()
    for n in ("a", "b", "c"):
        await g.upsert_node(_node(n))
    await g.upsert_edge(GraphEdge(src="a", dst="b", type="L"))
    await g.upsert_edge(GraphEdge(src="b", dst="c", type="L"))
    scores = await g.pagerank()
    assert set(scores.keys()) == {"a", "b", "c"}
    assert all(0.0 <= v <= 1.0 for v in scores.values())
    assert sum(scores.values()) == pytest.approx(1.0, rel=1e-3)


async def test_communities_returns_partition():
    g = NetworkXGraphStore()
    # Two tight clusters connected by a thin bridge
    for n in ("a1", "a2", "a3", "b1", "b2", "b3"):
        await g.upsert_node(_node(n))
    for src, dst in [("a1", "a2"), ("a2", "a3"), ("a3", "a1"),
                     ("b1", "b2"), ("b2", "b3"), ("b3", "b1"),
                     ("a1", "b1")]:
        await g.upsert_edge(GraphEdge(src=src, dst=dst, type="L"))
    communities = await g.communities()
    assert set(communities.keys()) == {"a1", "a2", "a3", "b1", "b2", "b3"}
    # The two triangles should fall into different communities under Louvain.
    assert communities["a2"] == communities["a3"]
    assert communities["b2"] == communities["b3"]
    assert communities["a2"] != communities["b2"]


async def test_empty_graph_analytics_safe():
    g = NetworkXGraphStore()
    assert await g.pagerank() == {}
    assert await g.communities() == {}


async def test_persistence_roundtrip(tmp_path):
    persist = tmp_path / "graph.pkl"
    g1 = NetworkXGraphStore(persist_path=persist)
    await g1.upsert_node(_node("alpha"))
    await g1.upsert_node(_node("beta"))
    await g1.upsert_edge(GraphEdge(src="alpha", dst="beta", type="REFS"))
    g1.save()
    assert persist.exists()

    g2 = NetworkXGraphStore(persist_path=persist)
    assert g2.node_count == 2
    assert g2.edge_count == 1
    neighbors = await g2.expand("alpha", hops=1)
    assert {n.id for n in neighbors} == {"beta"}


async def test_persistence_rejects_non_graph_json(tmp_path):
    persist = tmp_path / "graph.json"
    persist.write_text('{"foo": "bar"}', encoding="utf-8")
    with pytest.raises(GraphStoreError):
        NetworkXGraphStore(persist_path=persist)


async def test_persistence_rejects_corrupt_json(tmp_path):
    persist = tmp_path / "graph.json"
    persist.write_text("{not-json", encoding="utf-8")
    with pytest.raises(GraphStoreError):
        NetworkXGraphStore(persist_path=persist)


async def test_self_loop_does_not_appear_in_own_expansion():
    """`expand("a", 1)` on a node with a self-loop must NOT include "a"."""
    g = NetworkXGraphStore()
    await g.upsert_node(_node("a"))
    await g.upsert_edge(GraphEdge(src="a", dst="a", type="REFS"))
    assert await g.expand("a", hops=1) == []


async def test_save_without_persist_path_is_noop():
    g = NetworkXGraphStore(persist_path=None)
    await g.upsert_node(_node("x"))
    g.save()   # no exception; no file written
    # nothing to assert beyond no-raise


async def test_typed_edges_allowed_between_same_nodes():
    g = NetworkXGraphStore()
    await g.upsert_node(_node("doc1"))
    await g.upsert_node(_node("doc2"))
    await g.upsert_edge(GraphEdge(src="doc1", dst="doc2", type="CITES"))
    await g.upsert_edge(GraphEdge(src="doc1", dst="doc2", type="CONTRADICTS"))
    assert g.edge_count == 2
