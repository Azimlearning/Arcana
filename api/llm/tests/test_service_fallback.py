"""LLMService — provider fallback + AllProvidersFailed semantics."""

from __future__ import annotations

import pytest

from api.core.budget import TokenBudget
from api.core.errors import AllProvidersFailed
from api.llm.service import LLMService
from api.llm.types import Completion, LLMProviderError, Message, ToolSpec, Usage


class _StubProvider:
    """Configurable provider for tests — always raises, or always returns."""

    def __init__(self, name: str, *, result: Completion | None = None, error: str | None = None) -> None:
        self.name = name
        self._result = result
        self._error = error
        self.call_count = 0

    async def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        self.call_count += 1
        if self._error:
            raise LLMProviderError(self.name, self._error)
        assert self._result is not None
        return self._result

    async def aclose(self) -> None:
        return None


def _completion(text: str = "ok", in_tok: int = 10, out_tok: int = 5) -> Completion:
    return Completion(
        text=text,
        stop_reason="end_turn",
        usage=Usage(input_tokens=in_tok, output_tokens=out_tok),
        model="m",
        provider="stub",
    )


async def test_primary_success_short_circuits_fallback(settings_factory):
    primary = _StubProvider("primary", result=_completion("primary said hi"))
    fallback = _StubProvider("fallback", error="should never be called")
    s = settings_factory()
    svc = LLMService(settings=s, providers=[primary, fallback], cache=None)
    try:
        result = await svc.complete([Message(role="user", content="hi")])
    finally:
        await svc.aclose()
    assert result.text == "primary said hi"
    assert primary.call_count == 1
    assert fallback.call_count == 0


async def test_fallback_used_on_primary_failure(settings_factory):
    primary = _StubProvider("primary", error="boom")
    fallback = _StubProvider("fallback", result=_completion("fallback ran"))
    svc = LLMService(settings=settings_factory(), providers=[primary, fallback], cache=None)
    try:
        result = await svc.complete([Message(role="user", content="hi")])
    finally:
        await svc.aclose()
    assert result.text == "fallback ran"
    assert primary.call_count == 1
    assert fallback.call_count == 1


async def test_all_providers_failed(settings_factory):
    p1 = _StubProvider("p1", error="x")
    p2 = _StubProvider("p2", error="y")
    svc = LLMService(settings=settings_factory(), providers=[p1, p2], cache=None)
    try:
        with pytest.raises(AllProvidersFailed) as exc:
            await svc.complete([Message(role="user", content="hi")])
    finally:
        await svc.aclose()
    errs = exc.value.details["errors"]
    assert {e["provider"] for e in errs} == {"p1", "p2"}


async def test_budget_charged_on_success(settings_factory):
    primary = _StubProvider("primary", result=_completion(in_tok=100, out_tok=50))
    svc = LLMService(settings=settings_factory(), providers=[primary], cache=None)
    budget = TokenBudget(tokens_limit=1000)
    try:
        await svc.complete([Message(role="user", content="hi")], budget=budget)
    finally:
        await svc.aclose()
    assert budget.tokens_used == 150


async def test_exceeded_budget_short_circuits(settings_factory):
    primary = _StubProvider("primary", result=_completion())
    svc = LLMService(settings=settings_factory(), providers=[primary], cache=None)
    budget = TokenBudget(tokens_limit=10, tokens_used=20)
    try:
        with pytest.raises(AllProvidersFailed):
            await svc.complete([Message(role="user", content="hi")], budget=budget)
    finally:
        await svc.aclose()
    assert primary.call_count == 0   # never called once budget exceeded
