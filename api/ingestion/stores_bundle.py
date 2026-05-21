"""Thin grouping struct so the ingestion pipeline takes one parameter
instead of three. Layered ABCs only — never concrete backends (invariant #7)."""

from __future__ import annotations

from dataclasses import dataclass

from api.stores.chunk_store import ChunkStore
from api.stores.doc_store import DocStore
from api.stores.graph_store import GraphStore
from api.stores.vector_store import VectorStore


@dataclass(frozen=True, slots=True)
class Stores:
    doc: DocStore
    vector: VectorStore
    graph: GraphStore
    chunks: ChunkStore
