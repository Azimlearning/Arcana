"""ingest_highlight — fold a user note back into the graph (FR-USR-05)."""

from __future__ import annotations

import json

from api.ingestion.pipeline import ingest_highlight
from api.llm.types import Completion, Usage
from api.stores.networkx_store import NetworkXGraphStore


class _StubLLM:
    def __init__(self, *, text: str) -> None:
        self._text = text

    async def complete(self, messages, *, system=None, tools=None, max_tokens=None, budget=None):
        return Completion(
            text=self._text,
            stop_reason="end_turn",
            usage=Usage(input_tokens=5, output_tokens=10),
            model="stub",
            provider="stub",
        )


_EXTRACTION = json.dumps(
    {
        "entities": [
            {"label": "Knowledge Graph", "type": "Concept"},
            {"label": "Retrieval", "type": "Concept"},
        ],
        "relationships": [
            {"src": "Knowledge Graph", "dst": "Retrieval", "type": "SUPPORTS"}
        ],
    }
)


async def test_highlight_merges_concepts_into_graph_with_doc_provenance():
    graph = NetworkXGraphStore()
    llm = _StubLLM(text=_EXTRACTION)

    result = await ingest_highlight(
        text="Knowledge graphs improve retrieval.",
        doc_id="doc_a",
        graph=graph,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )

    assert result["nodes"] == 2
    assert result["edges"] == 1
    assert set(result["concepts"]) == {"knowledge_graph", "retrieval"}
    # Provenance: the highlight's concepts carry the source doc id.
    node = await graph.get_node("knowledge_graph")
    assert node is not None
    assert "doc_a" in node.properties["doc_ids"]


async def test_highlight_merges_into_existing_graph_incrementally():
    graph = NetworkXGraphStore()
    llm = _StubLLM(text=_EXTRACTION)
    await ingest_highlight(text="note one", doc_id="doc_a", graph=graph, llm=llm)  # type: ignore[arg-type]
    # A second highlight from another doc sharing a concept accumulates provenance.
    await ingest_highlight(text="note two", doc_id="doc_b", graph=graph, llm=llm)  # type: ignore[arg-type]
    node = await graph.get_node("knowledge_graph")
    assert node is not None
    assert set(node.properties["doc_ids"]) == {"doc_a", "doc_b"}
