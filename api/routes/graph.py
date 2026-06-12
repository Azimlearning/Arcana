"""GET /graph — interactive knowledge graph view for the current user (FR-KG-08).

Returns all nodes and edges from the user's personal knowledge graph so the
frontend KnowledgeGraphView component can render an interactive visualisation.

The graph is lazily loaded from disk on first access (UserGraphRegistry) and
kept in-process for subsequent requests — cold reads are only paid once per
server lifetime per user.
"""

from __future__ import annotations

import networkx as nx
from fastapi import APIRouter, Depends, Request

from api.core.auth import CurrentUser, get_current_user
from api.genui._generated import GraphViewEdge, GraphViewNode, GraphViewResponse

router = APIRouter()


@router.get("/graph", response_model=GraphViewResponse)
async def get_graph(
    http_request: Request,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> GraphViewResponse:
    """Return the requesting user's full knowledge graph (nodes + edges).

    Empty graphs (new users or no documents ingested yet) return an empty
    response with nodeCount=0, edgeCount=0 — not a 404.
    """
    shared = getattr(http_request.app.state, "shared", {})
    registry = shared.get("graph_registry")

    if registry is None:
        return GraphViewResponse(nodes=[], edges=[], nodeCount=0, edgeCount=0)

    store = await registry.get_or_create(user.uid)
    g: nx.MultiDiGraph = store._g

    # Compute analytics lazily — empty graphs skip the nx calls.
    communities: dict[str, int] = {}
    ranks: dict[str, float] = {}
    if len(g) > 0:
        try:
            communities = await store.communities()
        except Exception:
            pass
        try:
            ranks = await store.pagerank()
        except Exception:
            pass

    nodes: list[GraphViewNode] = [
        GraphViewNode(
            id=nid,
            label=attrs.get("label", nid),
            nodeType=attrs.get("type", "Concept"),
            properties={k: v for k, v in attrs.items() if k not in ("label", "type")},
            community=communities.get(nid),
            pagerank=ranks.get(nid),
        )
        for nid, attrs in g.nodes(data=True)
    ]

    edges: list[GraphViewEdge] = [
        GraphViewEdge(
            id=f"{src}-[{key}]->{dst}",
            src=src,
            dst=dst,
            edgeType=str(key),
        )
        for src, dst, key in g.edges(keys=True)
    ]

    return GraphViewResponse(
        nodes=nodes,
        edges=edges,
        nodeCount=len(nodes),
        edgeCount=len(edges),
    )
