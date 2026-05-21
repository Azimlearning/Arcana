"""Embedding-provider protocol.

A provider declares its `dimension` (informational — the slice's pipeline
treats 3072 as canonical) and implements `embed(texts) -> EmbeddingResult`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from api.embeddings.types import EmbeddingResult


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    dimension: int

    async def embed(self, texts: list[str]) -> EmbeddingResult: ...

    async def aclose(self) -> None: ...
