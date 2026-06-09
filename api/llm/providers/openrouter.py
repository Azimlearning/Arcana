"""OpenRouter fallback provider — OpenAI-compatible chat completions API.

Uses raw httpx (same pattern as the Anthropic provider) so the request/response
shape stays explicit. OpenRouter accepts any OpenAI-format body and routes to
the model named in `model`. Tool calls use the OpenAI function-calling format.
"""

from __future__ import annotations

import json

import httpx

from api.llm.types import (
    Completion,
    LLMProviderError,
    Message,
    ToolSpec,
    ToolUse,
    Usage,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "anthropic/claude-3-5-sonnet-20241022",
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
        if not self._api_key:
            raise LLMProviderError(self.name, "no API key configured")

        # Build OpenAI-format messages list (system inline as first message)
        oai_messages: list[dict] = []
        effective_system = system or next(
            (m.content for m in messages if m.role == "system"), None
        )
        if effective_system:
            oai_messages.append({"role": "system", "content": effective_system})
        oai_messages.extend(
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        )

        body: dict = {
            "model": self._model,
            "max_tokens": max_tokens or self._default_max_tokens,
            "messages": oai_messages,
        }

        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-OpenRouter-Title": "Arcana",
        }

        try:
            resp = await self._client.post(OPENROUTER_URL, json=body, headers=headers)
        except httpx.HTTPError as e:
            raise LLMProviderError(self.name, f"network error: {e}") from e

        if resp.status_code >= 400:
            raise LLMProviderError(
                self.name,
                f"HTTP {resp.status_code}: {resp.text[:300]}",
                status=resp.status_code,
            )

        data = resp.json()
        return _parse_openai_response(data, model=self._model, provider_name=self.name)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def __repr__(self) -> str:
        return f"OpenRouterProvider(model={self._model!r})"


def _parse_openai_response(data: dict, *, model: str, provider_name: str) -> Completion:
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}

    text = msg.get("content") or ""

    tool_uses: list[ToolUse] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}
        tool_uses.append(
            ToolUse(id=tc.get("id", ""), name=fn.get("name", ""), input=args)
        )

    raw_usage = data.get("usage") or {}
    usage = Usage(
        input_tokens=int(raw_usage.get("prompt_tokens", 0)),
        output_tokens=int(raw_usage.get("completion_tokens", 0)),
    )

    finish = choice.get("finish_reason") or "stop"
    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "stop_sequence",
    }
    stop_reason = stop_reason_map.get(finish, "end_turn")

    return Completion(
        text=text,
        tool_uses=tool_uses,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        usage=usage,
        model=data.get("model", model),
        provider=provider_name,
    )
