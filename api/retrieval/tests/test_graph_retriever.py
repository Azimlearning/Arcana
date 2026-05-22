"""GraphRetriever — slice 1 real-traversal path.

The slice-0 stub (return-[]) is gone. These tests cover:
  - Empty graph / missing entities → []
  - Direct entity match scores chunks at weight 1.0
  - 1-hop neighbor expansion scores chunks at weight 0.5
  - Score-descending top_k
  - LLM=None or ChunkStore=None still degrades cleanly
  - Query-extraction failure doesn't raise
"""

from __future__ import annotations

from api.core.errors import IngestFailed
from api.llm.types import Completion, Usage
from api.retrieval.graph import GraphRetriever
from api.stores.chunk_store import StoredChunk
from api.stores.graph_store import GraphEdge, GraphNode
from api.stores.jsonl_chunk_store import JsonlChunkStore
from api.stores.networkx_store import NetworkXGraphStore

# ── Stub LLM that returns a canned extraction JSON ────────────────


class _StubLLM:
    def __init__(self, *, entities: list[str], raise_exc: Exception | None = None) -> None:
        self._entities = entities
        self._raise = raise_exc

    async def complete(self, messages, *, system=None, tools=None, max_tokens=None, budget=None):
        if self._raise:
            raise self._raise
        ents = ",".join(
            f'{{"label": "{e}", "type": "Concept"}}' for e in self._entities
        )
        return Completion(
            text=f'{{"entities": [{ents}], "relationships": []}}',
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=20),
            model="stub", provider="stub",
        )


async def _make_populated_graph(tmp_path) -> tuple[NetworkXGraphStore, JsonlChunkStore]:
    """A small fixture corpus:
        Concept(graph_rag) -- RELATES_TO --> Concept(vector_retrieval)
        Concept(graph_rag) mentioned_in: [ch1, ch2]
        Concept(vector_retrieval) mentioned_in: [ch2, ch3]
        Concept(unrelated) mentioned_in: [ch4]
    """
    graph = NetworkXGraphStore()
    await graph.upsert_node(GraphNode(
        id="graph_rag", type="Concept", label="graph rag",
        properties={"mentioned_in_chunks": ["ch1", "ch2"], "doc_ids": ["d1"]},
    ))
    await graph.upsert_node(GraphNode(
        id="vector_retrieval", type="Concept", label="vector retrieval",
        properties={"mentioned_in_chunks": ["ch2", "ch3"], "doc_ids": ["d1"]},
    ))
    await graph.upsert_node(GraphNode(
        id="unrelated", type="Concept", label="unrelated",
        properties={"mentioned_in_chunks": ["ch4"], "doc_ids": ["d1"]},
    ))
    await graph.upsert_edge(GraphEdge(
        src="graph_rag", dst="vector_retrieval", type="CONTRASTS_WITH",
    ))

    chunks = JsonlChunkStore(root=tmp_path)
    await chunks.upsert_many([
        StoredChunk(id="ch1", doc_id="d1", text="GraphRAG intro.", page=1, char_offset=0),
        StoredChunk(id="ch2", doc_id="d1", text="GraphRAG vs vector.", page=2, char_offset=100),
        StoredChunk(id="ch3", doc_id="d1", text="Vector retrieval body.", page=3, char_offset=200),
        StoredChunk(id="ch4", doc_id="d1", text="Unrelated material.", page=4, char_offset=300),
    ])
    return graph, chunks


# ── Degradation paths ────────────────────────────────────────────


async def test_no_llm_returns_empty():
    """Slice-0 compatibility: without an LLM, the retriever degrades cleanly."""
    graph = NetworkXGraphStore()
    retriever = GraphRetriever(graph_store=graph)
    assert await retriever.retrieve("anything", top_k=5) == []


async def test_no_chunk_store_returns_empty():
    graph = NetworkXGraphStore()
    retriever = GraphRetriever(
        graph_store=graph,
        llm=_StubLLM(entities=["x"]),  # type: ignore[arg-type]
    )
    assert await retriever.retrieve("anything", top_k=5) == []


async def test_query_extraction_failure_returns_empty(tmp_path):
    graph, chunks = await _make_populated_graph(tmp_path)
    retriever = GraphRetriever(
        graph_store=graph,
        chunk_store=chunks,
        llm=_StubLLM(entities=[], raise_exc=IngestFailed("LLM down")),  # type: ignore[arg-type]
    )
    assert await retriever.retrieve("compare GraphRAG and vector retrieval", top_k=5) == []


async def test_empty_graph_returns_empty(tmp_path):
    graph = NetworkXGraphStore()
    chunks = JsonlChunkStore(root=tmp_path)
    retriever = GraphRetriever(
        graph_store=graph,
        chunk_store=chunks,
        llm=_StubLLM(entities=["graph rag"]),  # type: ignore[arg-type]
    )
    assert await retriever.retrieve("graphrag", top_k=5) == []


# ── Real traversal ───────────────────────────────────────────────


async def test_direct_match_scores_chunks(tmp_path):
    graph, chunks = await _make_populated_graph(tmp_path)
    retriever = GraphRetriever(
        graph_store=graph,
        chunk_store=chunks,
        llm=_StubLLM(entities=["graph rag"]),  # type: ignore[arg-type]
    )
    hits = await retriever.retrieve("tell me about graph rag", top_k=10)
    by_id = {h.id: h.score for h in hits}

    # Direct mentions of `graph_rag`: ch1, ch2 → weight 1.0 each
    assert by_id.get("ch1") == 1.0
    assert by_id.get("ch2") == 1.5   # direct + neighbor (via vector_retrieval)
    # `vector_retrieval` is a 1-hop neighbor of `graph_rag`
    # → ch3 (mentioned_in vector_retrieval) gets weight 0.5
    assert by_id.get("ch3") == 0.5
    # `unrelated` is not connected → ch4 is NOT in results
    assert "ch4" not in by_id


async def test_score_descending_order(tmp_path):
    graph, chunks = await _make_populated_graph(tmp_path)
    retriever = GraphRetriever(
        graph_store=graph,
        chunk_store=chunks,
        llm=_StubLLM(entities=["graph rag"]),  # type: ignore[arg-type]
    )
    hits = await retriever.retrieve("graph rag", top_k=10)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


async def test_top_k_caps_results(tmp_path):
    graph, chunks = await _make_populated_graph(tmp_path)
    retriever = GraphRetriever(
        graph_store=graph,
        chunk_store=chunks,
        llm=_StubLLM(entities=["graph rag"]),  # type: ignore[arg-type]
    )
    hits = await retriever.retrieve("graph rag", top_k=2)
    assert len(hits) <= 2


async def test_source_is_graph(tmp_path):
    graph, chunks = await _make_populated_graph(tmp_path)
    retriever = GraphRetriever(
        graph_store=graph,
        chunk_store=chunks,
        llm=_StubLLM(entities=["graph rag"]),  # type: ignore[arg-type]
    )
    hits = await retriever.retrieve("graph rag", top_k=5)
    assert all(h.source == "graph" for h in hits)


async def test_missing_chunk_in_store_silently_skipped(tmp_path):
    """If the graph references a chunk_id that the chunk store no longer
    has (e.g. after a delete), we skip rather than crash."""
    graph = NetworkXGraphStore()
    # Slug of "orphan entity" → "orphan_entity", matches the node id.
    await graph.upsert_node(GraphNode(
        id="orphan_entity", type="Concept", label="orphan entity",
        properties={"mentioned_in_chunks": ["does_not_exist", "ch_real"], "doc_ids": ["d1"]},
    ))
    chunks = JsonlChunkStore(root=tmp_path)
    await chunks.upsert_many([
        StoredChunk(id="ch_real", doc_id="d1", text="real body", page=1, char_offset=0),
    ])
    retriever = GraphRetriever(
        graph_store=graph,
        chunk_store=chunks,
        llm=_StubLLM(entities=["orphan entity"]),  # type: ignore[arg-type]
    )
    hits = await retriever.retrieve("orphan entity", top_k=10)
    assert [h.id for h in hits] == ["ch_real"]


async def test_query_entity_not_in_graph_returns_empty(tmp_path):
    """Query mentions an entity the corpus never recorded."""
    graph, chunks = await _make_populated_graph(tmp_path)
    retriever = GraphRetriever(
        graph_store=graph,
        chunk_store=chunks,
        llm=_StubLLM(entities=["completely novel concept"]),  # type: ignore[arg-type]
    )
    hits = await retriever.retrieve("completely novel concept", top_k=10)
    assert hits == []
