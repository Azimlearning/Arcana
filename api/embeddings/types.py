"""Internal embeddings types — provider-agnostic.

Vectors stay as `list[float]` (3072-d for OpenAI text-embedding-3-large)
so they round-trip cleanly through Pinecone and pickle.
"""

from __future__ import annotations

from pydantic import BaseModel

Vector = list[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int = 0
    total_tokens: int = 0


class EmbeddingResult(BaseModel):
    vectors: list[Vector]
    model: str
    provider: str
    usage: EmbeddingUsage = EmbeddingUsage()


class EmbeddingProviderError(Exception):
    """A provider failed to embed. Service falls through to next."""

    def __init__(self, provider: str, message: str, *, status: int | None = None) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.status = status
