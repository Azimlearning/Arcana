"""Shared pytest fixtures for the api/ test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# Test-only dummy values — short enough to NOT trip check_secrets.py's
# Anthropic / OpenAI patterns (which both require 20+ chars after the prefix).
_DEFAULT_TEST_ENV = {
    "ANTHROPIC_API_KEY": "test-anthropic",
    "OPENAI_API_KEY": "test-openai",
    "PINECONE_API_KEY": "test-pinecone",
}


@pytest.fixture
def settings_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., object]]:
    """Yield a factory that returns a fresh `Settings` with overrides.

    Two correctness rules baked in:
      1. **No .env leak.** `Settings(_env_file=None)` is used so a populated
         developer `api/.env` cannot inject real values (or real keys!) into
         test runs. `PYDANTIC_SETTINGS_ENV_FILE` is NOT honored by
         pydantic-settings 2.x — `_env_file=None` is the only escape hatch.
      2. **No cache leakage between tests.** The lru_cache on `get_settings()`
         is cleared on fixture teardown so a later test that calls it without
         this fixture doesn't see the previous test's overrides.

    Usage:
        def test_x(settings_factory):
            s = settings_factory(rrf_k="42")
            assert s.rrf_k == 42
    """
    from api.core.settings import Settings, get_settings

    def _factory(**overrides: str | int | float) -> object:
        for k, v in _DEFAULT_TEST_ENV.items():
            monkeypatch.setenv(k, v)
        for k, v in overrides.items():
            monkeypatch.setenv(k.upper(), str(v))
        return Settings(_env_file=None)  # type: ignore[call-arg]

    try:
        yield _factory
    finally:
        get_settings.cache_clear()
