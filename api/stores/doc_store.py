"""DocStore — raw document bytes + metadata.

The slice uses the filesystem-backed implementation
(`FilesystemDocStore`) writing under `Settings.local_storage_path`.
Firebase Storage + Firestore implementation lands in P1 §1.8.

The abstraction sits between ingestion (which writes raw bytes + meta)
and any future export/replay (which reads them back).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IngestStatus = Literal["pending", "parsing", "embedding", "ready", "failed"]


class DocMetadata(BaseModel):
    """Internal doc metadata.

    A superset of the wire-visible `Document` in `packages/schema/`:
    adds `content_type`, `size_bytes`, `created_at`, ingestion progress
    fields. Wire mapping happens at the route layer.
    """

    id: str
    title: str
    source_uri: str
    content_type: str
    size_bytes: int = Field(ge=0)
    ingest_status: IngestStatus = "pending"
    created_at: datetime
    extra: dict[str, str] = Field(default_factory=dict)


class DocStore(ABC):
    """Async ABC for raw document storage + metadata."""

    @abstractmethod
    async def put(
        self,
        doc_id: str,
        raw: bytes,
        *,
        content_type: str,
        title: str,
        source_uri: str,
        ingest_status: IngestStatus = "pending",
    ) -> DocMetadata:
        """Store the raw bytes and persist a metadata record. Returns the
        canonical metadata (with id, size_bytes, created_at filled in)."""

    @abstractmethod
    async def get_bytes(self, doc_id: str) -> bytes: ...

    @abstractmethod
    async def get_metadata(self, doc_id: str) -> DocMetadata: ...

    @abstractmethod
    async def update_status(
        self,
        doc_id: str,
        status: IngestStatus,
        *,
        extra_update: dict[str, str] | None = None,
    ) -> DocMetadata: ...

    @abstractmethod
    async def list_documents(self) -> list[DocMetadata]: ...

    @abstractmethod
    async def aclose(self) -> None: ...
