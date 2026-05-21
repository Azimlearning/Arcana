"""In-process NetworkX-backed GraphStore. The FYP 1 prototype (FR-KG-07).

Persists as JSON (networkx node-link format) — not pickle — so a stray
graph file from anywhere can be loaded without arbitrary-code-exec risk.
Neo4j replaces this entirely in P1.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import networkx as nx

from api.stores.errors import GraphStoreError
from api.stores.graph_store import GraphEdge, GraphNode, GraphStore

_DEFAULT_SEED = 42  # deterministic Louvain runs for the FYP benchmark (R-02)


class NetworkXGraphStore(GraphStore):
    def __init__(self, *, persist_path: Path | None = None) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        self._persist_path = persist_path
        if persist_path is not None and persist_path.exists():
            self._load()

    # ── CRUD ───────────────────────────────────────────────────────
    async def upsert_node(self, node: GraphNode) -> str:
        attrs: dict[str, Any] = {"type": node.type, "label": node.label, **node.properties}
        self._g.add_node(node.id, **attrs)
        return node.id

    async def upsert_edge(self, edge: GraphEdge) -> str:
        if edge.src not in self._g:
            raise GraphStoreError(f"src node {edge.src!r} not in graph")
        if edge.dst not in self._g:
            raise GraphStoreError(f"dst node {edge.dst!r} not in graph")
        # MultiDiGraph keys an edge by (u, v, key) — use the typed label as key
        # so distinct relationship types between the same pair don't collide.
        self._g.add_edge(edge.src, edge.dst, key=edge.type, type=edge.type, **edge.properties)
        return f"{edge.src}-[{edge.type}]->{edge.dst}"

    # ── Reads / analytics ──────────────────────────────────────────
    async def expand(self, node_id: str, hops: int = 1) -> list[GraphNode]:
        if node_id not in self._g:
            return []
        if hops < 1:
            return []
        seen: set[str] = {node_id}
        frontier: set[str] = {node_id}
        for _ in range(hops):
            next_layer: set[str] = set()
            for n in frontier:
                next_layer.update(self._g.successors(n))
                next_layer.update(self._g.predecessors(n))
            next_layer -= seen
            seen.update(next_layer)
            frontier = next_layer
            if not frontier:
                break
        seen.discard(node_id)  # the starting node is not part of the expansion
        return [self._to_graphnode(n) for n in seen]

    async def shortest_path(self, src: str, dst: str) -> list[str] | None:
        if src not in self._g or dst not in self._g:
            return None
        try:
            path = nx.shortest_path(self._g, src, dst)
        except nx.NetworkXNoPath:
            return None
        return list(path)

    async def communities(self) -> dict[str, int]:
        if len(self._g) == 0:
            return {}
        und = self._g.to_undirected(as_view=False)
        try:
            groups = nx.community.louvain_communities(und, seed=_DEFAULT_SEED)
        except Exception as e:
            raise GraphStoreError(f"Louvain failed: {e}") from e
        return {node: i for i, group in enumerate(groups) for node in group}

    async def pagerank(self) -> dict[str, float]:
        if len(self._g) == 0:
            return {}
        try:
            # networkx returns dict[_Node, float]; our node ids are str by contract.
            return {str(k): v for k, v in nx.pagerank(self._g).items()}
        except Exception as e:
            raise GraphStoreError(f"PageRank failed: {e}") from e

    # ── Persistence (JSON node-link, NOT pickle — see module docstring) ──
    def save(self) -> None:
        """Persist to `persist_path`. No-op if path not configured."""
        if self._persist_path is None:
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._g, edges="edges")
        tmp = self._persist_path.with_suffix(self._persist_path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._persist_path)

    def _load(self) -> None:
        assert self._persist_path is not None
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise GraphStoreError(f"cannot read graph from {self._persist_path}: {e}") from e
        if not isinstance(data, dict) or not data.get("multigraph") or not data.get("directed"):
            raise GraphStoreError(
                f"{self._persist_path}: expected a node-link JSON dump of a "
                "directed multigraph"
            )
        try:
            loaded = nx.node_link_graph(data, multigraph=True, directed=True, edges="edges")
        except Exception as e:  # nx raises various subtypes
            raise GraphStoreError(f"cannot deserialise graph: {e}") from e
        if not isinstance(loaded, nx.MultiDiGraph):
            raise GraphStoreError(
                f"deserialised type was {type(loaded).__name__}, expected MultiDiGraph"
            )
        self._g = loaded

    async def aclose(self) -> None:
        return None

    # ── Internals ──────────────────────────────────────────────────
    def _to_graphnode(self, node_id: str) -> GraphNode:
        attrs = dict(self._g.nodes[node_id])
        node_type = attrs.pop("type", "Concept")
        label = attrs.pop("label", node_id)
        return GraphNode(id=node_id, type=node_type, label=label, properties=attrs)

    # ── Convenience for tests / debugging ──────────────────────────
    @property
    def node_count(self) -> int:
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._g.number_of_edges()
