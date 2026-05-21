"""EmbeddingService — batching + provider fallback."""

from __future__ import annotations

import pytest

from api.core.errors import AllProvidersFailed
from api.embeddings.service import EmbeddingService
from api.embeddings.types import EmbeddingProviderError, EmbeddingResult


class _StubProvider:
    def __init__(self, name: str, *, dimension: int = 3072, fail: bool = False) -> None:
        self.name = name
        self.dimension = dimension
        self._fail = fail
        self.batches_received: list[list[str]] = []

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self.batches_received.append(list(texts))
        if self._fail:
            raise EmbeddingProviderError(self.name, "boom")
        return EmbeddingResult(
            vectors=[[float(i)] * self.dimension for i, _ in enumerate(texts)],
            model="stub",
            provider=self.name,
        )

    async def aclose(self) -> None:
        return None


async def test_batches_large_input(settings_factory):
    provider = _StubProvider("p")
    svc = EmbeddingService(settings=settings_factory(), providers=[provider], batch_size=10)
    try:
        vectors = await svc.embed([f"text-{i}" for i in range(25)])
    finally:
        await svc.aclose()
    assert len(vectors) == 25
    assert [len(b) for b in provider.batches_received] == [10, 10, 5]


async def test_fallback_used_on_primary_failure(settings_factory):
    primary = _StubProvider("primary", fail=True)
    fallback = _StubProvider("fallback")
    svc = EmbeddingService(
        settings=settings_factory(),
        providers=[primary, fallback],
        batch_size=100,
    )
    try:
        vectors = await svc.embed(["one", "two"])
    finally:
        await svc.aclose()
    assert len(vectors) == 2
    assert len(fallback.batches_received) == 1


async def test_all_providers_failed_raises(settings_factory):
    p1 = _StubProvider("p1", fail=True)
    p2 = _StubProvider("p2", fail=True)
    svc = EmbeddingService(settings=settings_factory(), providers=[p1, p2], batch_size=100)
    try:
        with pytest.raises(AllProvidersFailed):
            await svc.embed(["x"])
    finally:
        await svc.aclose()


async def test_empty_input_returns_empty_list(settings_factory):
    provider = _StubProvider("p")
    svc = EmbeddingService(settings=settings_factory(), providers=[provider])
    try:
        assert await svc.embed([]) == []
    finally:
        await svc.aclose()
    assert provider.batches_received == []


async def test_dimension_exposed_from_first_provider(settings_factory):
    provider = _StubProvider("p", dimension=512)
    svc = EmbeddingService(settings=settings_factory(), providers=[provider])
    assert svc.dimension == 512
    await svc.aclose()
