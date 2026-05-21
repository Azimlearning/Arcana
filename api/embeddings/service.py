"""EmbeddingService — batching + provider chain.

Sibling module to `api/llm/` (not below it). Both call external model
APIs; neither imports the other. Ingestion (subsystem 5) and retrieval
(subsystem 6) call `EmbeddingService.embed(...)`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from api.core.errors import AllProvidersFailed
from api.core.logging import get_logger
from api.core.settings import Settings, get_settings
from api.embeddings.providers.base import EmbeddingProvider
from api.embeddings.providers.openai import OpenAIEmbeddingProvider
from api.embeddings.types import EmbeddingProviderError, EmbeddingResult

logger = get_logger(__name__)

@runtime_checkable
class EmbedderProtocol(Protocol):
    """Minimum contract anything-that-embeds must satisfy.

    Consumers (e.g. the ingestion pipeline) depend on this, NOT on the
    concrete `EmbeddingService` class. That keeps tests trivially
    stubbable and lets a future caching wrapper drop in without changes."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


# OpenAI's embeddings endpoint accepts up to 2048 inputs per call (model-dependent);
# stay well under that to leave headroom for retries & avoid bigger-payload latency.
DEFAULT_BATCH_SIZE = 96


OPENAI_BATCH_HARD_CAP = 2048  # OpenAI /v1/embeddings refuses more than this per request.


class EmbeddingService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        providers: list[EmbeddingProvider] | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        if batch_size < 1 or batch_size > OPENAI_BATCH_HARD_CAP:
            raise ValueError(
                f"batch_size must be 1..{OPENAI_BATCH_HARD_CAP} (got {batch_size}). "
                "OpenAI rejects larger batches."
            )
        self.settings = settings or get_settings()
        self.providers: list[EmbeddingProvider] = providers or self._default_providers()
        self.batch_size = batch_size

    def _default_providers(self) -> list[EmbeddingProvider]:
        return [
            OpenAIEmbeddingProvider(
                api_key=self.settings.openai_api_key.get_secret_value(),
                model=self.settings.embedding_model,
            ),
        ]

    @property
    def dimension(self) -> int:
        return self.providers[0].dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            result = await self._embed_batch(batch)
            all_vectors.extend(result.vectors)
        return all_vectors

    async def aclose(self) -> None:
        for p in self.providers:
            try:
                await p.aclose()
            except Exception:
                pass

    # ── Internals ─────────────────────────────────────────────────
    async def _embed_batch(self, batch: list[str]) -> EmbeddingResult:
        errors: list[tuple[str, str]] = []
        for provider in self.providers:
            try:
                return await provider.embed(batch)
            except EmbeddingProviderError as e:
                logger.warning(
                    "embeddings.provider_failed", provider=provider.name, error=str(e)
                )
                errors.append((provider.name, str(e)))
                continue

        raise AllProvidersFailed(
            "Every embedding provider failed",
            details={
                "errors": [{"provider": p, "error": e} for p, e in errors],
                "batch_size": len(batch),
            },
        )
