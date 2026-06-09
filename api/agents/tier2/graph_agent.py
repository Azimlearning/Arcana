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
"""

from __future__ import annotations

from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.errors import IngestFailed
from api.core.logging import get_logger
from api.ingestion.extractor import extract_entities
from api.llm.service import LLMService
from api.stores.graph_store import GraphNode as StoreNode
from api.stores.graph_store import GraphStore

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
        graph_store: GraphStore,
    ) -> None:
        self._llm = llm_service
        self._graph = graph_store

    async def run(self, query: str, state: AgentState) -> AgentResult:
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
            store_node = await self._graph.get_node(entity.id)
            if store_node is None:
                continue
            if focus_node_id is None:
                focus_node_id = store_node.id
            nodes[store_node.id] = _to_wire_node(store_node)

            neighbors = await self._graph.expand(store_node.id, hops=1)
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
