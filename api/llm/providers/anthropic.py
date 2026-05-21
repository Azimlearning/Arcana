"""Anthropic Claude provider — uses the public /v1/messages API directly.

Why raw httpx and not the official SDK: keeps the request/response shape
explicit (easy to inspect during the FYP defence) and saves a dep. If we
later need streaming or batch features the SDK gives us, swap here.
"""

from __future__ import annotations

import httpx

from api.llm.types import (
    Completion,
    LLMProviderError,
    Message,
    ToolSpec,
    ToolUse,
    Usage,
)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    """Calls Anthropic /v1/messages. One instance per LLMService."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        default_max_tokens: int = 4096,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._default_max_tokens = default_max_tokens
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        body: dict = {
            "model": self._model,
            "max_tokens": max_tokens or self._default_max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
        }
        # Anthropic expects `system` as a top-level field, not a message.
        if system:
            body["system"] = system
        else:
            inline_system = next((m.content for m in messages if m.role == "system"), None)
            if inline_system:
                body["system"] = inline_system
        if tools:
            body["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        try:
            resp = await self._client.post(ANTHROPIC_API_URL, json=body, headers=headers)
        except httpx.HTTPError as e:
            raise LLMProviderError(self.name, f"network error: {e}") from e

        if resp.status_code >= 400:
            raise LLMProviderError(
                self.name,
                f"HTTP {resp.status_code}: {resp.text[:200]}",
                status=resp.status_code,
            )

        data = resp.json()
        return _parse_anthropic_response(data, model=self._model, provider_name=self.name)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def __repr__(self) -> str:
        # Override default repr so accidental `logger.debug(provider=...)`
        # doesn't dump `_api_key`. (Belt-and-suspenders — structlog calls
        # in service.py pass `.name`, not the object.)
        return f"AnthropicProvider(model={self._model!r})"


def _parse_anthropic_response(data: dict, *, model: str, provider_name: str) -> Completion:
    text_parts: list[str] = []
    tool_uses: list[ToolUse] = []
    for block in data.get("content", []):
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_uses.append(
                ToolUse(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    input=block.get("input", {}) or {},
                )
            )
    raw_usage = data.get("usage", {}) or {}
    usage = Usage(
        input_tokens=int(raw_usage.get("input_tokens", 0)),
        output_tokens=int(raw_usage.get("output_tokens", 0)),
    )
    stop_reason = data.get("stop_reason", "end_turn")
    if stop_reason not in {"end_turn", "max_tokens", "tool_use", "stop_sequence", "error"}:
        stop_reason = "end_turn"
    return Completion(
        text="".join(text_parts),
        tool_uses=tool_uses,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        usage=usage,
        model=data.get("model", model),
        provider=provider_name,
    )
