"""Provider protocol — anything `LLMService` can call must satisfy this.

The protocol is intentionally tiny: one `complete()` coroutine, plus a
`name` for telemetry/error messages. Real providers translate their
HTTP/SDK shapes into the internal `Completion` and raise
`LLMProviderError` on any failure they want the service to retry past.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from api.llm.types import Completion, Message, ToolSpec


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> Completion: ...

    async def aclose(self) -> None: ...
