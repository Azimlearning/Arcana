"""NFR-PERF-04 — interactive graph render for up to 500 nodes < 2 s.

The GET /graph render cost is dominated by the two analytics passes the
route runs over the store — `communities()` (Louvain) and `pagerank()`.
This builds a 500-node / ~550-edge graph and asserts both complete well
within the 2 s budget, so the endpoint stays interactive at the spec's
upper node bound. Pure compute — no network or API keys required.
"""

from __future__ import annotations

import time

import pytest

from api.stores.graph_store import GraphEdge, GraphNode
from api.stores.networkx_store import NetworkXGraphStore

_NODES = 500
_PERF_BUDGET_S = 2.0


async def _build_graph() -> NetworkXGraphStore:
    store = NetworkXGraphStore()
    for i in range(_NODES):
        await store.upsert_node(
            GraphNode(id=f"n{i}", type="Concept", label=f"concept {i}", properties={})
        )
    # A ring keeps the graph connected; periodic chords give Louvain real
    # community structure to find rather than a degenerate single cluster.
    for i in range(_NODES):
        await store.upsert_edge(GraphEdge(src=f"n{i}", dst=f"n{(i + 1) % _NODES}", type="REL"))
        if i % 10 == 0:
            await store.upsert_edge(GraphEdge(src=f"n{i}", dst=f"n{(i + 5) % _NODES}", type="REL"))
    return store


@pytest.mark.asyncio
async def test_graph_analytics_render_under_2s_for_500_nodes():
    store = await _build_graph()

    t0 = time.perf_counter()
    communities = await store.communities()
    ranks = await store.pagerank()
    elapsed = time.perf_counter() - t0

    assert store.node_count == _NODES
    assert len(ranks) == _NODES
    assert len(communities) > 0
    assert elapsed < _PERF_BUDGET_S, f"graph analytics took {elapsed:.3f}s (budget {_PERF_BUDGET_S}s)"
