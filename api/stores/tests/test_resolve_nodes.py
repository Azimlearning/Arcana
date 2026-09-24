"""Approximate query-entity resolution — GraphStore.resolve_nodes.

Query slugs rarely equal corpus slugs, so exact lookup alone drops most
query entities and the graph signal silently degrades to nothing. These
tests pin the matching rule that fixes it, including the guards that stop
it from over-matching.
"""

from __future__ import annotations

import pytest

from api.stores.graph_store import GraphNode
from api.stores.networkx_store import NetworkXGraphStore


@pytest.fixture
async def store() -> NetworkXGraphStore:
    s = NetworkXGraphStore()
    for nid, label in [
        ("dense_retrieval", "dense retrieval"),
        ("dense_text_retrieval", "dense text retrieval"),
        ("multi_hop_retrieval", "multi-hop retrieval"),
        ("rag_technique", "RAG technique"),
        ("bm25", "BM25"),
        ("retrieval", "retrieval"),
    ]:
        await s.upsert_node(GraphNode(id=nid, type="Concept", label=label))
    return s


async def test_exact_match_returns_only_that_node(store: NetworkXGraphStore) -> None:
    got = await store.resolve_nodes("bm25")
    assert [n.id for n in got] == ["bm25"]


async def test_approximate_match_finds_the_corpus_slug(store: NetworkXGraphStore) -> None:
    # The question says "dense vector retrieval"; the corpus says "dense retrieval".
    got = await store.resolve_nodes("dense_vector_retrieval")
    assert got, "expected an approximate match"
    assert got[0].id == "dense_retrieval"


async def test_single_token_slug_never_matches_approximately(
    store: NetworkXGraphStore,
) -> None:
    # "technique" would otherwise pull in rag_technique and anything else
    # sharing one common token, which is not evidence of anything.
    assert await store.resolve_nodes("technique") == []


async def test_unrelated_slug_matches_nothing(store: NetworkXGraphStore) -> None:
    assert await store.resolve_nodes("photosynthesis_pathway") == []


async def test_results_are_capped_and_ordered_by_overlap(
    store: NetworkXGraphStore,
) -> None:
    got = await store.resolve_nodes("dense_retrieval_system", limit=2)
    assert len(got) <= 2
    assert got[0].id == "dense_retrieval"


async def test_missing_node_yields_empty(store: NetworkXGraphStore) -> None:
    assert await store.resolve_nodes("") == []
