"""GraphStore — the abstraction agents use for knowledge-graph reads/writes.

PRD Listing 10.3, FR-KG-07. Every backend (NetworkX prototype, Neo4j prod)
satisfies this interface; agents never import a concrete backend. That is
how a NetworkX→Neo4j swap stays a one-setting change (`graph_backend=...`).

Slice scope: types defined here are *internal* — they don't cross the wire
(the wire-visible `GraphNode`/`GraphEdge` would live in `packages/schema/`
when the graph view is exposed to the frontend in P1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """An entity in the knowledge graph (Concept, Person, Document, Topic)."""

    id: str
    type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A typed relationship between two nodes
    (MENTIONS, AGREES_WITH, CONTRADICTS, INFLUENCES, …)."""

    src: str
    dst: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)


class GraphStore(ABC):
    """Async ABC for the knowledge graph. PRD §10.3, Listing 10.3."""

    @abstractmethod
    async def upsert_node(self, node: GraphNode) -> str:
        """Insert or update a node. Returns the node id."""

    @abstractmethod
    async def upsert_edge(self, edge: GraphEdge) -> str:
        """Insert or update a directed typed edge. Returns a stable edge id."""

    @abstractmethod
    async def get_node(self, node_id: str) -> GraphNode | None:
        """Fetch a node by id, or None if missing. Used by the ingestion
        pipeline to merge multi-chunk entity mentions into one node."""

    @abstractmethod
    async def expand(self, node_id: str, hops: int = 1) -> list[GraphNode]:
        """N-hop neighborhood around `node_id`. Empty list if node missing."""

    @abstractmethod
    async def shortest_path(self, src: str, dst: str) -> list[str] | None:
        """Shortest path of node ids from src to dst, or None if no path."""

    @abstractmethod
    async def communities(self) -> dict[str, int]:
        """Louvain community assignment: `{node_id: community_id}`."""

    @abstractmethod
    async def pagerank(self) -> dict[str, float]:
        """PageRank score per node id."""

    @abstractmethod
    async def aclose(self) -> None:
        """Release resources. Idempotent."""
