"""Anthropic provider — request shape + response parsing.

We don't hit the real API; respx intercepts httpx requests so we can
assert on the wire body and stub the response.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from api.llm.providers.anthropic import ANTHROPIC_API_URL, AnthropicProvider
from api.llm.types import LLMProviderError, Message, ToolSpec


def _ok_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "msg_01",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "content": [{"type": "text", "text": "hi there"}],
            "usage": {"input_tokens": 12, "output_tokens": 5},
        },
    )


@respx.mock
async def test_complete_sends_correct_body():
    route = respx.post(ANTHROPIC_API_URL).mock(return_value=_ok_response())
    provider = AnthropicProvider(api_key="sk-ant-test-key", model="claude-sonnet-4-6", default_max_tokens=1024)
    try:
        result = await provider.complete(
            [Message(role="user", content="hi")],
            system="be brief",
        )
    finally:
        await provider.aclose()

    assert route.called
    req = route.calls.last.request
    body = json.loads(req.content)
    assert body["model"] == "claude-sonnet-4-6"
    assert body["max_tokens"] == 1024
    assert body["system"] == "be brief"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert req.headers["x-api-key"] == "sk-ant-test-key"
    assert req.headers["anthropic-version"] == "2023-06-01"

    assert result.text == "hi there"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 5
    assert result.stop_reason == "end_turn"
    assert result.provider == "anthropic"


@respx.mock
async def test_inline_system_message_promoted():
    route = respx.post(ANTHROPIC_API_URL).mock(return_value=_ok_response())
    provider = AnthropicProvider(api_key="sk-ant-test-key", model="claude-sonnet-4-6")
    try:
        await provider.complete(
            [Message(role="system", content="you are terse"), Message(role="user", content="hi")],
        )
    finally:
        await provider.aclose()
    body = json.loads(route.calls.last.request.content)
    assert body["system"] == "you are terse"
    assert body["messages"] == [{"role": "user", "content": "hi"}]


@respx.mock
async def test_tools_passed_through():
    route = respx.post(ANTHROPIC_API_URL).mock(return_value=_ok_response())
    provider = AnthropicProvider(api_key="sk-ant-test-key", model="claude-sonnet-4-6")
    try:
        await provider.complete(
            [Message(role="user", content="search")],
            tools=[ToolSpec(name="search_docs", description="search", input_schema={"type": "object"})],
        )
    finally:
        await provider.aclose()
    body = json.loads(route.calls.last.request.content)
    assert body["tools"][0]["name"] == "search_docs"
    assert body["tools"][0]["input_schema"] == {"type": "object"}


@respx.mock
async def test_http_error_raises_provider_error():
    respx.post(ANTHROPIC_API_URL).mock(return_value=httpx.Response(503, text="upstream gone"))
    provider = AnthropicProvider(api_key="sk-ant-test-key", model="claude-sonnet-4-6")
    try:
        with pytest.raises(LLMProviderError) as exc:
            await provider.complete([Message(role="user", content="hi")])
    finally:
        await provider.aclose()
    assert exc.value.status == 503
    assert exc.value.provider == "anthropic"


@respx.mock
async def test_network_error_raises_provider_error():
    respx.post(ANTHROPIC_API_URL).mock(side_effect=httpx.ConnectError("dns gone"))
    provider = AnthropicProvider(api_key="sk-ant-test-key", model="claude-sonnet-4-6")
    try:
        with pytest.raises(LLMProviderError) as exc:
            await provider.complete([Message(role="user", content="hi")])
    finally:
        await provider.aclose()
    assert exc.value.provider == "anthropic"
