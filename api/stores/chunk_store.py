"""ChunkStore — the text-of-chunks store that BM25 indexes from.

Pinecone (the slice's `VectorStore`) returns chunk text in its metadata
on `query`, but offers no way to *enumerate* the full corpus — which BM25
needs to build its index. So we keep a separate, durable chunk store
that lives alongside the vector store. The ingestion pipeline writes to
both in lock-step.

Slice scope: single global file under `infra/local_storage/`. Per-notebook
isolation (FR-USR-06) lands in P1; the ABC will gain a `notebook_id`
keying then.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StoredChunk:
    id: str
    doc_id: str
    text: str
    page: int
    char_offset: int


class ChunkStore(ABC):
    """Async ABC: durable text-of-chunks storage for BM25 indexing."""

    @abstractmethod
    async def upsert_many(self, chunks: list[StoredChunk]) -> None:
        """Insert or replace by id. Empty input is a no-op."""

    @abstractmethod
    async def get(self, chunk_id: str) -> StoredChunk | None: ...

    @abstractmethod
    async def list_all(self) -> list[StoredChunk]:
        """Return every chunk currently in the store. BM25 calls this
        per query in the slice — fine for small corpora; revisit in P1."""

    @abstractmethod
    async def delete_by_doc(self, doc_id: str) -> int:
        """Remove all chunks for a doc. Returns count deleted."""

    @abstractmethod
    async def aclose(self) -> None: ...
