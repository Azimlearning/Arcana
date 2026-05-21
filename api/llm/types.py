"""Internal LLM types — provider-agnostic so swapping Anthropic ↔ OpenRouter
is a one-line change in the service.

These models do NOT cross the wire (the wire contract lives in
`packages/schema/`). They're the protocol between `LLMService` and its
`LLMProvider` implementations.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ToolSpec(BaseModel):
    """Schema description the LLM sees when deciding which tool to call.
    Matches the Anthropic tools API shape (also acceptable to OpenAI/OpenRouter)."""

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ToolUse(BaseModel):
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class Completion(BaseModel):
    text: str
    tool_uses: list[ToolUse] = Field(default_factory=list)
    stop_reason: Literal["end_turn", "max_tokens", "tool_use", "stop_sequence", "error"]
    usage: Usage = Field(default_factory=Usage)
    model: str
    provider: str


class LLMProviderError(Exception):
    """A provider failed to complete a request. Service falls through to next."""

    def __init__(self, provider: str, message: str, *, status: int | None = None) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.status = status
