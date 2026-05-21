"""VectorStore — dense vector index abstraction.

The slice's only concrete impl is `PineconeVectorStore`. The ABC defines
upsert/query/delete; the retrieval layer (subsystem 6) calls `query`,
ingestion (subsystem 5) calls `upsert`. Both touch only the ABC.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

Vector = list[float]


@dataclass
class VectorItem:
    """Payload for upsert: id + dense vector + arbitrary metadata."""

    id: str
    vector: Vector
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorHit:
    """Single result row from `query()`."""

    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """Async ABC for dense vector search."""

    dimension: int  # backends populate from index config; consulted by retrieval

    @abstractmethod
    async def upsert(self, items: list[VectorItem]) -> None:
        """Insert or replace vectors. Empty list is a no-op."""

    @abstractmethod
    async def query(
        self,
        vector: Vector,
        *,
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Top-k cosine neighbors, optionally filtered by metadata predicate."""

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """Delete by id. Missing ids are silently ignored."""

    @abstractmethod
    async def aclose(self) -> None: ...
