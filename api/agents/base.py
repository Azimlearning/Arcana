"""Agent base layer - PRD §11.1-11.4.

The keystone of the agentic pipeline. Defines:
  - `AgentState` — the shared ledger every agent reads/writes (PRD §11.1).
  - `AgentResult` — return envelope each agent produces.
  - `BaseAgent` — abstract base for all 25 agents.
  - `@tool` decorator + `registry` — typed tool catalog the LLM sees.
  - `route_to_agent` — composability primitive (PRD §11.4, FR-AGT-03).

Slice-shape simplifications (carry-overs from the slice ADR):
  - AgentState omits `user_profile`.
  - LangGraph reducer annotations are absent — the slice wires agents with
    direct async calls (orchestrator → research → ui_agent), so append
    semantics are caller-enforced rather than reducer-enforced.
  - `route_to_agent` is implemented but unused by the slice's call graph;
    its tests prove it works so subsystem 8+ can rely on it.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from operator import add
from typing import Annotated, Any, Literal, TypeVar, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field

from api.core.budget import TokenBudget
from api.core.logging import get_logger
from api.genui._generated import Mode, UIBlock
from api.llm.types import Message
from api.retrieval.types import RetrievedChunk

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _merge_agent_results(
    left: dict[str, AgentResult], right: dict[str, AgentResult]
) -> dict[str, AgentResult]:
    """LangGraph reducer for `agent_results`: right wins on key conflict
    (e.g. Fact Checker can overwrite Research's entry with a verified
    revision)."""
    return {**left, **right}


# ─── Result envelope ──────────────────────────────────────────────


class AgentResult(BaseModel):
    """What every agent returns. Lands in `state.agent_results[agent_name]`."""

    agent_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: Literal["ok", "partial", "failed"] = "ok"
    error: str | None = None


# ─── Shared state ─────────────────────────────────────────────────


class AgentState(BaseModel):
    """Shared per-turn ledger. PRD §11.1 Listing 11.1.

    `Annotated[..., reducer]` on accumulating fields tells LangGraph how to
    merge each node's partial update into the running state. Reducers fire
    only when a node returns a value for that key; nodes that don't touch
    a field omit it from their return dict.

    `budget` has no reducer — it's a stdlib dataclass shared by reference
    across all nodes within one turn, so mutations to `budget.tokens_used`
    persist via Python aliasing (langgraph's model_copy does shallow copy).
    """

    # TokenBudget is a stdlib @dataclass; Pydantic needs the allow-list.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str
    notebook_id: str = ""
    user_id: str = "anon"   # populated by chat route from CurrentUser.uid (FR-KG-02)
    # `Mode` is the schema-owned wire type (packages/schema/src/api.ts →
    # codegen). Imported, never re-declared, so a new mode added to the
    # schema can't drift from the agent state (R-10).
    active_mode: Mode = "research"
    intent: str = ""   # set by Orchestrator; consumed by conditional routing
    # FR-RET-07: local/global/hybrid/auto retrieval scope; set by chat route
    # from ChatRequest.retrievalMode (defaults to auto). Read by grounded agents.
    retrieval_mode: str = "auto"
    messages: Annotated[list[Message], add] = Field(default_factory=list)
    retrieved_ctx: Annotated[list[RetrievedChunk], add] = Field(default_factory=list)
    agent_results: Annotated[
        dict[str, AgentResult], _merge_agent_results
    ] = Field(default_factory=dict)
    ui_blocks: Annotated[list[UIBlock], add] = Field(default_factory=list)
    budget: TokenBudget = Field(default_factory=TokenBudget)


# ─── @tool decorator + global registry ────────────────────────────


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """JSON-schema representation of a tool the LLM can call."""

    name: str
    description: str
    input_schema: dict[str, Any]
    agent: str
    tier: int


class AgentRegistry:
    """Global agent + tool registry. One per-process instance is enough.

    Tests call `reset()` between cases so the registry doesn't leak state.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._tools: dict[str, list[ToolSpec]] = defaultdict(list)

    def register_agent(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get_agent(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def register_tool(self, spec: ToolSpec) -> None:
        self._tools[spec.agent].append(spec)

    def tools_for(self, agent_name: str) -> list[ToolSpec]:
        return list(self._tools[agent_name])

    def select_tools(self, agent_names: list[str], *, limit: int) -> list[ToolSpec]:
        """Intent-scoped tool selection (FR-AGT-05, PRD §11.5).

        Gathers the tools registered for `agent_names` (the specialist an
        intent routes to, plus any always-on base agents), dedupes by name,
        orders deterministically by (tier, name), and caps the result at
        `limit` — the `max_tools_per_prompt` budget (NFR-AGT-05). Only the
        scoped, capped set is ever injected into a prompt, never the full
        catalogue."""
        seen: set[str] = set()
        specs: list[ToolSpec] = []
        for agent_name in agent_names:
            for spec in self._tools.get(agent_name, []):
                if spec.name in seen:
                    continue
                seen.add(spec.name)
                specs.append(spec)
        specs.sort(key=lambda s: (s.tier, s.name))
        return specs[:limit]

    def reset(self) -> None:
        """Clear all registrations. Test-only — production never calls this."""
        self._agents.clear()
        self._tools.clear()


registry = AgentRegistry()


def tool(*, agent: str, tier: int) -> Callable[[F], F]:
    """Register `fn` as a typed tool for `agent`.

    Derives a JSON-schema input contract from the function's annotations
    and stores it in the global `registry`. The function is returned
    unchanged so it remains directly callable (PRD §11.3 Listing 11.3)."""

    def decorator(fn: F) -> F:
        schema = _json_schema_from_signature(fn)
        spec = ToolSpec(
            name=fn.__name__,
            description=(fn.__doc__ or "").strip().split("\n", 1)[0],
            input_schema=schema,
            agent=agent,
            tier=tier,
        )
        registry.register_tool(spec)
        return fn

    return decorator


def _json_schema_from_signature(fn: Callable[..., Any]) -> dict[str, Any]:
    """Best-effort JSON-schema for the LLM. Handles the slice's actual
    parameter shapes (str, int, float, bool, list[T], T | None). Anything
    else falls back to an empty schema for that parameter; the runtime
    still receives the value, just without a precise type hint to the LLM."""

    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    sig = inspect.signature(fn)
    hints = inspect.get_annotations(fn, eval_str=True)

    for name, param in sig.parameters.items():
        if name in {"self", "cls"}:
            continue
        properties[name] = _annotation_to_schema(hints.get(name))
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {"type": "object", "properties": properties, "required": required}


def _annotation_to_schema(ann: Any) -> dict[str, Any]:
    if ann is None or ann is inspect.Parameter.empty:
        return {}
    if ann is str:
        return {"type": "string"}
    if ann is int:
        return {"type": "integer"}
    if ann is float:
        return {"type": "number"}
    if ann is bool:
        return {"type": "boolean"}
    origin = get_origin(ann)
    if origin in (list, tuple):
        args = get_args(ann)
        if args:
            return {"type": "array", "items": _annotation_to_schema(args[0])}
        return {"type": "array"}
    # `T | None` (PEP 604): unwrap to `T`.
    if origin is type(None) or origin is None:
        return {}
    args = get_args(ann)
    non_null = [a for a in args if a is not type(None)]
    if len(non_null) == 1:
        return _annotation_to_schema(non_null[0])
    return {}  # union or unsupported — let the LLM see the param untyped


# ─── BaseAgent ────────────────────────────────────────────────────


class BaseAgent(ABC):
    """Abstract base for every agent. Subclasses MUST set `name` and `tier`
    as class attributes and implement `run()`."""

    name: str = ""
    tier: int = 0

    @abstractmethod
    async def run(self, query: str, state: AgentState) -> AgentResult:
        """Execute the agent's reasoning. Writes its result to
        `state.agent_results[self.name]` and optionally to other state
        fields (`retrieved_ctx`, `ui_blocks`, ...)."""


# ─── Composability primitive ─────────────────────────────────────


async def route_to_agent(
    agent_name: str,
    query: str,
    *,
    state: AgentState,
) -> AgentResult:
    """Invoke another agent as a tool (PRD §11.4, FR-AGT-03).

    Charges the hop budget before dispatch; returns a `partial` result if
    the budget is exceeded. Looks up the target in the global registry.

    Slice scope: implemented and tested, but not used by the slice's
    direct-call orchestrator. Subsystem 8 (routes) and later A2A flows
    rely on this primitive."""

    state.budget.charge_hop()
    if state.budget.exceeded:
        logger.warning(
            "route_to_agent.budget_exceeded",
            agent=agent_name,
            hops_used=state.budget.hops_used,
        )
        return AgentResult(
            agent_name=agent_name,
            payload={},
            status="partial",
            error=f"hop budget reached (hops_used={state.budget.hops_used})",
        )
    agent = registry.get_agent(agent_name)
    if agent is None:
        result = AgentResult(
            agent_name=agent_name,
            payload={},
            status="failed",
            error=f"agent {agent_name!r} not registered",
        )
        state.agent_results[agent_name] = result
        return result
    result = await agent.run(query=query, state=state)
    # Write back to shared state so UIAgent sees sub-agent results from A2A hops.
    state.agent_results[agent_name] = result
    return result
