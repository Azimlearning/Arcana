"""Incremental graph update on new documents (FR-KG-03).

Proves that ingesting a second document merges into the existing graph
*without reprocessing the first*: prior nodes/edges survive, the new
doc's content is added, and a concept shared across both documents
accumulates both doc_ids on a single node (no duplicate node). Also
proves re-ingesting the same document is idempotent.
"""

from __future__ import annotations

import pytest

from api.ingestion.extractor import ExtractionResult
from api.ingestion.pipeline import _merge_extraction
from api.stores.graph_store import GraphEdge, GraphNode
from api.stores.networkx_store import NetworkXGraphStore


def _node(slug: str, doc_id: str, chunk_id: str) -> GraphNode:
    return GraphNode(
        id=slug,
        type="Concept",
        label=slug,
        properties={"mentioned_in_chunks": [chunk_id], "doc_ids": [doc_id]},
    )


@pytest.mark.asyncio
async def test_second_doc_merges_without_reprocessing_first() -> None:
    graph = NetworkXGraphStore()

    # Doc A: graph_rag -> vector_retrieval
    await _merge_extraction(
        ExtractionResult(
            nodes=[_node("graph_rag", "docA", "a1"), _node("vector_retrieval", "docA", "a1")],
            edges=[GraphEdge(src="graph_rag", dst="vector_retrieval", type="USES")],
        ),
        graph=graph,
    )
    assert graph.node_count == 2
    assert graph.edge_count == 1

    # Doc B: shares graph_rag, adds knowledge_graph + a new edge
    await _merge_extraction(
        ExtractionResult(
            nodes=[_node("graph_rag", "docB", "b1"), _node("knowledge_graph", "docB", "b1")],
            edges=[GraphEdge(src="graph_rag", dst="knowledge_graph", type="BUILDS")],
        ),
        graph=graph,
    )

    # Doc A's content survives (no reprocess); Doc B's content is added.
    assert graph.node_count == 3
    assert graph.edge_count == 2

    # The shared concept is ONE node carrying both documents' provenance.
    shared = await graph.get_node("graph_rag")
    assert shared is not None
    assert set(shared.properties["doc_ids"]) == {"docA", "docB"}
    assert set(shared.properties["mentioned_in_chunks"]) == {"a1", "b1"}

    # Doc A's other node is untouched by Doc B's ingest.
    assert await graph.get_node("vector_retrieval") is not None


@pytest.mark.asyncio
async def test_reingesting_same_doc_is_idempotent() -> None:
    graph = NetworkXGraphStore()
    extraction = ExtractionResult(nodes=[_node("graph_rag", "docA", "a1")], edges=[])

    await _merge_extraction(extraction, graph=graph)
    await _merge_extraction(extraction, graph=graph)  # same doc again

    assert graph.node_count == 1
    node = await graph.get_node("graph_rag")
    assert node is not None
    assert node.properties["doc_ids"] == ["docA"]  # not duplicated
    assert node.properties["mentioned_in_chunks"] == ["a1"]
