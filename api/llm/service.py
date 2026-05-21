"""LLMService — provider-agnostic completion seam (PRD §10.2, NFR-REL-02).

Single entry point for every LLM call in the codebase. Owns:
  - Provider chain (Anthropic primary, OpenRouter fallback today; trivial
    to extend).
  - Caching (disk-backed, active in ENV=local).
  - Token-budget integration (charged from provider usage on success).
  - `AllProvidersFailed` when every provider raises (NFR-REL-02).

Callers never instantiate providers directly — `LLMService()` builds the
default chain from `Settings`. Tests inject a custom provider list.
"""

from __future__ import annotations

from typing import Any

from api.core.budget import TokenBudget
from api.core.errors import AllProvidersFailed
from api.core.logging import get_logger
from api.core.settings import REPO_ROOT, Settings, get_settings
from api.llm.cache import LLMCache
from api.llm.providers.anthropic import AnthropicProvider
from api.llm.providers.base import LLMProvider
from api.llm.providers.openrouter import OpenRouterProvider
from api.llm.types import Completion, LLMProviderError, Message, ToolSpec

logger = get_logger(__name__)


# Sentinel for "use default" vs "None means disable cache".
class _UNSET:
    pass


_UNSET_T = type[_UNSET]


class LLMService:
    """One-stop shop for completions. PRD §10.2 Listing 10.2."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        providers: list[LLMProvider] | None = None,
        cache: LLMCache | None | _UNSET_T = _UNSET,
    ) -> None:
        self.settings = settings or get_settings()
        self.providers: list[LLMProvider] = providers or self._default_providers()
        if cache is _UNSET:
            cache = self._default_cache()
        self.cache: LLMCache | None = cache  # type: ignore[assignment]

    # ── Construction helpers ──────────────────────────────────────
    def _default_providers(self) -> list[LLMProvider]:
        return [
            AnthropicProvider(
                api_key=self.settings.anthropic_api_key.get_secret_value(),
                model=self.settings.llm_primary,
                default_max_tokens=self.settings.llm_primary_max_tokens,
            ),
            OpenRouterProvider(
                api_key=(
                    self.settings.openrouter_api_key.get_secret_value()
                    if self.settings.openrouter_api_key
                    else None
                ),
                model=self.settings.llm_fallback,
            ),
        ]

    def _default_cache(self) -> LLMCache | None:
        if self.settings.env != "local":
            return None
        return LLMCache(REPO_ROOT / ".llm_cache")

    # ── Public API ────────────────────────────────────────────────
    async def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
        budget: TokenBudget | None = None,
    ) -> Completion:
        if budget is not None and budget.exceeded:
            raise AllProvidersFailed(
                "Token / hop budget exceeded before LLM call",
                details={"tokens_used": budget.tokens_used, "hops_used": budget.hops_used},
            )

        cache_key = self._cache_key(messages, system=system, tools=tools, max_tokens=max_tokens)
        if self.cache is not None:
            hit = self.cache.get(cache_key)
            if hit is not None:
                logger.debug("llm.cache_hit", key=cache_key[:8], provider=hit.provider)
                if budget is not None:
                    budget.charge_tokens(hit.usage.total)
                return hit

        errors: list[tuple[str, str]] = []
        for provider in self.providers:
            try:
                completion = await provider.complete(
                    messages, system=system, tools=tools, max_tokens=max_tokens
                )
            except LLMProviderError as e:
                logger.warning("llm.provider_failed", provider=provider.name, error=str(e))
                errors.append((provider.name, str(e)))
                continue
            if self.cache is not None:
                self.cache.put(cache_key, completion)
            if budget is not None:
                budget.charge_tokens(completion.usage.total)
            return completion

        raise AllProvidersFailed(
            "Every LLM provider failed",
            details={"errors": [{"provider": p, "error": e} for p, e in errors]},
        )

    async def aclose(self) -> None:
        for p in self.providers:
            try:
                await p.aclose()
            except Exception:
                pass

    # ── Internals ─────────────────────────────────────────────────
    def _cache_key(
        self,
        messages: list[Message],
        *,
        system: str | None,
        tools: list[ToolSpec] | None,
        max_tokens: int | None,
    ) -> str:
        # Note on canonicalization: callers must pass `tools` and `messages`
        # in a stable order — the hash is order-sensitive. Two calls with
        # the same tools in different order miss the cache (correctness is
        # preserved; only cache hit-rate suffers). If a caller starts
        # passing dynamically-ordered tools, sort here by `tool.name`.
        provider_signature = [p.name for p in self.providers]
        payload: dict[str, Any] = {
            "providers": provider_signature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "system": system,
            "tools": [t.model_dump() for t in tools] if tools else None,
            "max_tokens": max_tokens,
        }
        return LLMCache.make_key(payload)
