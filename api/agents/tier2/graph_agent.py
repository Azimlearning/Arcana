"""GraphAgent - Tier 2. Produces KnowledgeGraphView from the entity graph.

Pipeline:
  1. extract_entities(query) — identifies entity slugs the user is asking about.
  2. graph_store.get_node(slug) — verify each entity exists in the corpus graph.
  3. graph_store.expand(node_id, hops=1) — 1-hop neighborhood for each matched entity.
  4. Build wire-typed GraphNode + GraphEdge lists (source/target/relation).
  5. Return KnowledgeGraphView payload (no LLM synthesis step needed — the graph IS
     the structured data).

Wire types (api/genui/_generated.py): GraphNode(id, label, nodeType),
  GraphEdge(source, target, relation).
Store types (api/stores/graph_store.py): GraphNode(id, type, label),
  GraphEdge(src, dst, type).

Edge relations: synthetic "RELATED_TO" for all expand() neighbors (real relation
types not exposed via GraphStore ABC — see decisions.md Slice 7 ADR).

FR-KG-02: when a UserGraphRegistry is supplied, the agent resolves the calling
user's personal graph via state.user_id. Falls back to a shared GraphStore for
callers that haven't been updated (backward-compatible).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.errors import IngestFailed
from api.core.logging import get_logger
from api.ingestion.extractor import extract_entities
from api.llm.service import LLMService
from api.stores.graph_store import GraphNode as StoreNode
from api.stores.graph_store import GraphStore

if TYPE_CHECKING:
    from api.stores.user_graph_registry import UserGraphRegistry

logger = get_logger(__name__)

_MAX_QUERY_ENTITIES = 5
_MAX_NEIGHBORS_PER_ENTITY = 20


class GraphAgent(BaseAgent):
    """Tier-2 agent. Visualises the knowledge graph neighborhood of a query."""

    name = "graph_agent"
    tier = 2

    def __init__(
        self,
        *,
        llm_service: LLMService,
        graph_store: GraphStore | None = None,
        graph_registry: UserGraphRegistry | None = None,
    ) -> None:
        if graph_registry is None and graph_store is None:
            raise ValueError("Either graph_registry or graph_store must be supplied")
        self._llm = llm_service
        self._graph = graph_store
        self._registry = graph_registry

    async def _resolve_graph(self, user_id: str) -> GraphStore:
        """Return the graph store for this request's user."""
        if self._registry is not None:
            return await self._registry.get_or_create(user_id)
        assert self._graph is not None
        return self._graph

    async def run(self, query: str, state: AgentState) -> AgentResult:
        graph = await self._resolve_graph(state.user_id)

        # 1. Extract entity slugs from query text (reuses ingestion extractor).
        try:
            extraction = await extract_entities(
                text=query, chunk_id="query", doc_id="query", llm=self._llm
            )
        except IngestFailed as e:
            logger.warning("graph_agent.extract_failed", error=str(e), query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="Entity extraction from query failed.",
            )

        if not extraction.nodes:
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No entities found in query.",
            )

        # 2-3. Resolve entities in graph store; expand 1-hop neighborhood.
        nodes: dict[str, dict[str, str]] = {}  # id → wire GraphNode dict
        edges: list[dict[str, str]] = []
        focus_node_id: str | None = None

        for entity in extraction.nodes[:_MAX_QUERY_ENTITIES]:
            store_node = await graph.get_node(entity.id)
            if store_node is None:
                continue
            if focus_node_id is None:
                focus_node_id = store_node.id
            nodes[store_node.id] = _to_wire_node(store_node)

            neighbors = await graph.expand(store_node.id, hops=1)
            for nbr in neighbors[:_MAX_NEIGHBORS_PER_ENTITY]:
                if nbr.id not in nodes:
                    nodes[nbr.id] = _to_wire_node(nbr)
                edges.append(
                    {
                        "source": store_node.id,
                        "target": nbr.id,
                        "relation": "RELATED_TO",
                    }
                )

        if not nodes:
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No matching entities found in the knowledge graph.",
            )

        return AgentResult(
            agent_name=self.name,
            payload={
                "block_type": "KnowledgeGraphView",
                "data": {
                    "nodes": list(nodes.values()),
                    "edges": edges,
                    "focusNodeId": focus_node_id,
                },
            },
            status="ok",
        )


def _to_wire_node(store_node: StoreNode) -> dict[str, Any]:
    return {
        "id": store_node.id,
        "label": store_node.label,
        "nodeType": store_node.type,
    }
