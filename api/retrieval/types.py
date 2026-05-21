"""Unified retrieval result type.

Every retriever (vector / BM25 / graph) returns a list of `RetrievedChunk`.
RRF fusion (`fusion.py`) consumes those lists and produces a fused list
of the same type, marked `source="hybrid"`.

`source` is informational — once the agent gets the fused list it doesn't
case which retriever a chunk came from, but the field is preserved so
logs/traces can show retrieval provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

RetrieverSource = Literal["vector", "bm25", "graph", "hybrid"]


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    id: str
    doc_id: str
    text: str
    page: int
    score: float
    source: RetrieverSource


@runtime_checkable
class RetrieverProtocol(Protocol):
    """Minimum contract every retriever (vector / BM25 / graph / custom)
    must satisfy. Mirrors the `EmbedderProtocol` pattern from subsystem 3
    so callers depend on the interface, not the concrete class."""

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]: ...
