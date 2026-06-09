"""GraphAgent — KnowledgeGraphView producer tests."""

from __future__ import annotations

from api.agents.base import AgentState
from api.agents.tier2.graph_agent import GraphAgent, _to_wire_node
from api.stores.graph_store import GraphNode as StoreNode

# ---- Stubs ------------------------------------------------------------------


class _StubLLM:
    """Minimal LLM stub that returns an extraction-friendly JSON response."""

    def __init__(self, response_text: str = "", raise_exc: Exception | None = None):
        self._response = response_text
        self._raise = raise_exc
        self.calls: list = []

    async def complete(self, messages, *, system=None, max_tokens=None, budget=None, tools=None):
        self.calls.append(messages)
        if self._raise:
            raise self._raise
        from api.llm.types import Completion, Usage
        return Completion(
            text=self._response,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=20),
            model="stub",
            provider="stub",
        )


class _StubGraphStore:
    """In-memory graph store stub."""

    def __init__(self, nodes: dict[str, StoreNode], edges: dict[str, list[StoreNode]]):
        self._nodes = nodes
        self._edges = edges  # node_id → list of neighbor StoreNodes

    async def get_node(self, node_id: str) -> StoreNode | None:
        return self._nodes.get(node_id)

    async def expand(self, node_id: str, hops: int = 1) -> list[StoreNode]:
        return self._edges.get(node_id, [])

    async def upsert_node(self, node): ...
    async def upsert_edge(self, edge): ...
    async def shortest_path(self, src, dst): return None
    async def communities(self): return {}
    async def pagerank(self): return {}
    async def aclose(self): ...


_EXTRACTION_JSON = """\
{
  "entities": [
    {"label": "RAG", "type": "Concept"},
    {"label": "Transformer", "type": "Concept"}
  ],
  "relationships": []
}
"""


def _make_agent(llm_response: str, nodes: dict, edges: dict) -> GraphAgent:
    return GraphAgent(
        llm_service=_StubLLM(response_text=llm_response),  # type: ignore[arg-type]
        graph_store=_StubGraphStore(nodes=nodes, edges=edges),  # type: ignore[arg-type]
    )


# ---- Unit tests: _to_wire_node ----------------------------------------------


def test_to_wire_node_maps_store_type_to_nodeType():
    store_node = StoreNode(id="rag", type="Concept", label="RAG")
    wire = _to_wire_node(store_node)
    assert wire == {"id": "rag", "label": "RAG", "nodeType": "Concept"}


# ---- Integration tests: agent.run -------------------------------------------


async def test_run_produces_knowledge_graph_view():
    rag_node = StoreNode(id="rag", type="Concept", label="RAG")
    transformer_node = StoreNode(id="transformer", type="Concept", label="Transformer")
    store_nodes = {"rag": rag_node}
    store_edges = {"rag": [transformer_node]}

    agent = _make_agent(_EXTRACTION_JSON, store_nodes, store_edges)
    state = AgentState(query="explain RAG")
    result = await agent.run("explain RAG", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "KnowledgeGraphView"
    data = result.payload["data"]
    assert any(n["id"] == "rag" for n in data["nodes"])
    assert any(n["id"] == "transformer" for n in data["nodes"])
    assert len(data["edges"]) >= 1
    assert data["edges"][0]["source"] == "rag"
    assert data["edges"][0]["target"] == "transformer"
    assert data["edges"][0]["relation"] == "RELATED_TO"
    assert data["focusNodeId"] == "rag"


async def test_run_fails_when_no_entities_in_query():
    agent = _make_agent(
        '{"nodes": [], "edges": []}',
        nodes={},
        edges={},
    )
    state = AgentState(query="something vague")
    result = await agent.run("something vague", state=state)
    assert result.status == "failed"


async def test_run_fails_when_entities_not_in_graph():
    # LLM extraction returns entities but none exist in graph store.
    agent = _make_agent(_EXTRACTION_JSON, nodes={}, edges={})
    state = AgentState(query="explain RAG")
    result = await agent.run("explain RAG", state=state)
    assert result.status == "failed"
    assert "No matching" in (result.error or "")


async def test_run_fails_gracefully_when_llm_raises():
    agent = GraphAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("timeout")),  # type: ignore[arg-type]
        graph_store=_StubGraphStore(nodes={}, edges={}),  # type: ignore[arg-type]
    )
    state = AgentState(query="x")
    result = await agent.run("x", state=state)
    assert result.status == "failed"
