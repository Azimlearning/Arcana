"""LLMService — disk cache hit/put semantics."""

from __future__ import annotations

import pytest

from api.llm.cache import LLMCache
from api.llm.service import LLMService
from api.llm.types import Completion, Message, Usage


class _CountingProvider:
    name = "counting"

    def __init__(self, completion: Completion) -> None:
        self._completion = completion
        self.calls = 0

    async def complete(self, messages, *, system=None, tools=None, max_tokens=None):
        self.calls += 1
        return self._completion

    async def aclose(self) -> None:
        return None


def _make_completion(text: str = "cached!") -> Completion:
    return Completion(
        text=text,
        stop_reason="end_turn",
        usage=Usage(input_tokens=10, output_tokens=5),
        model="m",
        provider="counting",
    )


@pytest.fixture
def cache(tmp_path):
    return LLMCache(tmp_path)


async def test_cache_hit_does_not_call_provider(settings_factory, cache):
    provider = _CountingProvider(_make_completion("first call"))
    svc = LLMService(settings=settings_factory(), providers=[provider], cache=cache)
    try:
        first = await svc.complete([Message(role="user", content="same")])
        second = await svc.complete([Message(role="user", content="same")])
    finally:
        await svc.aclose()
    assert first.text == "first call"
    assert second.text == "first call"
    assert provider.calls == 1


async def test_different_messages_miss_cache(settings_factory, cache):
    provider = _CountingProvider(_make_completion())
    svc = LLMService(settings=settings_factory(), providers=[provider], cache=cache)
    try:
        await svc.complete([Message(role="user", content="msg one")])
        await svc.complete([Message(role="user", content="msg two")])
    finally:
        await svc.aclose()
    assert provider.calls == 2


async def test_cache_survives_service_restart(settings_factory, tmp_path):
    # First service: populates the on-disk cache.
    provider1 = _CountingProvider(_make_completion("persisted"))
    cache1 = LLMCache(tmp_path)
    svc1 = LLMService(settings=settings_factory(), providers=[provider1], cache=cache1)
    try:
        await svc1.complete([Message(role="user", content="warm me")])
    finally:
        await svc1.aclose()

    # Second service: fresh in-memory cache, same disk dir. Same query.
    provider2 = _CountingProvider(_make_completion("would be different"))
    cache2 = LLMCache(tmp_path)
    svc2 = LLMService(settings=settings_factory(), providers=[provider2], cache=cache2)
    try:
        result = await svc2.complete([Message(role="user", content="warm me")])
    finally:
        await svc2.aclose()

    assert result.text == "persisted"   # loaded from disk
    assert provider2.calls == 0


async def test_cache_none_disables_caching(settings_factory):
    provider = _CountingProvider(_make_completion())
    svc = LLMService(settings=settings_factory(), providers=[provider], cache=None)
    try:
        await svc.complete([Message(role="user", content="same")])
        await svc.complete([Message(role="user", content="same")])
    finally:
        await svc.aclose()
    assert provider.calls == 2
