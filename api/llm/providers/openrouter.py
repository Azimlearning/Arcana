"""OpenRouter fallback — P0 slice stub.

The interface satisfies `LLMProvider`. `complete()` always raises
`LLMProviderError`, so the LLMService's fallback path is exercised in
tests today and a real implementation can drop in here without changing
any caller (NFR-REL-02).

TODO(subsystem-3-followup): real implementation against
https://openrouter.ai/api/v1/chat/completions.
"""

from __future__ import annotations

from api.llm.types import Completion, LLMProviderError, Message, ToolSpec


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, *, api_key: str | None = None, model: str = "openrouter/auto") -> None:
        self._api_key = api_key
        self._model = model

    async def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        raise LLMProviderError(self.name, "OpenRouter provider is a P0 stub — real impl in slice 2.")

    async def aclose(self) -> None:
        return None
