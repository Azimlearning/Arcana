"""LangGraph StateGraph assembly. PRD §11.1, FR-AGT-04.

The agent runtime. `build_graph()` returns a compiled `StateGraph` keyed
on `AgentState`. Nodes are wrapped agents (one node per registered agent),
edges are the request lifecycle from PRD §11A.2:

  START -> orchestrator -> (intent-routed) -> ... -> ui_agent -> END

Slice 1 scope: nodes for orchestrator, research, ui_agent. Memory Agent
(chunk 5) and Fact Checker (chunk 4) land in this same slice and insert
into the graph as new nodes + edges; the chat route doesn't change.

Slice 2 addition: discovery intent node.
Slice 3 addition: learning and socratic intent nodes.

How state flows:
  - Each node receives the live `AgentState` snapshot for that step.
  - Agents may freely mutate the snapshot during their `run()` call
    (mutations within one node call persist via shared reference).
  - Across nodes, langgraph copies state and applies the node's returned
    partial-update via the Annotated reducers on `AgentState`.
  - The node wrapper diffs `len(field)` before/after the agent call and
    emits the new items only - so the reducer applies an append, not a
    replace.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from api.agents.base import AgentResult, AgentState, registry
from api.core.logging import get_logger

# Set on `state` by `_orchestrator_node` so `state.intent` always has a
# value before the conditional edge runs. Kept as a constant so the
# routing branch names below can reference the same string source-of-truth.
_DEFAULT_INTENT = "research"

logger = get_logger(__name__)

NodeFn = Callable[[AgentState], Awaitable[dict[str, Any]]]


def make_node(agent_name: str) -> NodeFn:
    """Wrap a registered agent as a LangGraph node.

    The wrapper takes a snapshot of accumulating-field lengths, calls
    `agent.run(...)`, and returns only the DELTAS so langgraph's `add`
    reducer appends new entries rather than duplicating the entire list.
    """

    async def node(state: AgentState) -> dict[str, Any]:
        agent = registry.get_agent(agent_name)
        if agent is None:
            logger.error("graph.node.missing_agent", agent=agent_name)
            return {
                "agent_results": {
                    agent_name: AgentResult(
                        agent_name=agent_name,
                        payload={},
                        status="failed",
                        error=f"agent {agent_name!r} not registered",
                    )
                }
            }

        # Snapshot lengths BEFORE the agent runs so we can compute deltas.
        ctx_before = len(state.retrieved_ctx)
        ui_before = len(state.ui_blocks)
        msgs_before = len(state.messages)

        try:
            result = await agent.run(query=state.query, state=state)
        except Exception as exc:  # one agent's crash must not kill the graph
            logger.exception("graph.node.failed", agent=agent_name)
            return {
                "agent_results": {
                    agent_name: AgentResult(
                        agent_name=agent_name,
                        payload={},
                        status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                }
            }

        updates: dict[str, Any] = {"agent_results": {agent.name: result}}

        new_ctx = state.retrieved_ctx[ctx_before:]
        if new_ctx:
            updates["retrieved_ctx"] = list(new_ctx)

        new_blocks = state.ui_blocks[ui_before:]
        if new_blocks:
            updates["ui_blocks"] = list(new_blocks)

        new_msgs = state.messages[msgs_before:]
        if new_msgs:
            updates["messages"] = list(new_msgs)

        return updates

    node.__name__ = f"node__{agent_name}"
    return node


async def _orchestrator_node(state: AgentState) -> dict[str, Any]:
    """Orchestrator runs as a free function, NOT via `make_node`, so
    calling the Orchestrator agent class from within the graph can't
    recurse into `invoke_graph`. PRD §11.2 keeps the orchestrator as the
    plan-producing entry; slice 1 ships a one-intent default."""
    intent = state.intent or _DEFAULT_INTENT
    logger.info(
        "orchestrator.plan",
        intent=intent,
        mode=state.active_mode,
        query_len=len(state.query),
    )
    return {
        "intent": intent,
        "agent_results": {
            "orchestrator": AgentResult(
                agent_name="orchestrator",
                payload={"intent": intent, "mode": state.active_mode},
                status="ok",
            )
        },
    }


# Branch labels recognised by the conditional edge below. Extend ALL of
# these together when adding a new intent:
#   1. Add the agent + register it
#   2. Add a node in `build_graph`
#   3. Add the label here AND in the conditional-edges dict in `build_graph`
_WIRED_INTENTS = frozenset({"research", "discovery", "study", "socratic"})


def _route_after_orchestrator(state: AgentState) -> str:
    """Conditional edge after Orchestrator. Returns a label from
    `_WIRED_INTENTS`. Unknown intents fall back to the default rather
    than raising a KeyError inside LangGraph at runtime - safer extension
    behaviour for in-flight slices that add new intents before the
    matching node is registered."""
    intent = state.intent or _DEFAULT_INTENT
    if intent not in _WIRED_INTENTS:
        logger.warning(
            "orchestrator.unknown_intent",
            intent=intent,
            fallback=_DEFAULT_INTENT,
        )
        return _DEFAULT_INTENT
    return intent


def build_graph() -> Any:
    """Compile the agent StateGraph for the current registered set.

    Call this AFTER `research` + `ui_agent` are registered (typically
    inside `Orchestrator.__init__`). The compiled graph is reusable
    across requests - state is per-call.

    Note: `orchestrator` is wired as a free-function node (not via
    `make_node`) so that the agent class can use the public method name
    `run()` as the graph runner without recursing into itself."""
    graph: StateGraph = StateGraph(AgentState)

    has_memory = registry.get_agent("memory") is not None
    has_fact_checker = registry.get_agent("fact_checker") is not None
    has_discovery = registry.get_agent("discovery") is not None
    has_learning = registry.get_agent("learning") is not None
    has_socratic = registry.get_agent("socratic") is not None

    if has_memory:
        graph.add_node("memory", make_node("memory"))
    graph.add_node("orchestrator", _orchestrator_node)
    graph.add_node("research", make_node("research"))
    graph.add_node("ui_agent", make_node("ui_agent"))

    # START -> memory (if present) -> orchestrator
    if has_memory:
        graph.add_edge(START, "memory")
        graph.add_edge("memory", "orchestrator")
    else:
        graph.add_edge(START, "orchestrator")

    # Build the conditional routing map: intent label → node name.
    conditional_map: dict[str, str] = {"research": "research"}
    if has_discovery:
        graph.add_node("discovery", make_node("discovery"))
        conditional_map["discovery"] = "discovery"
    if has_learning:
        graph.add_node("learning", make_node("learning"))
        conditional_map["study"] = "learning"
    if has_socratic:
        graph.add_node("socratic", make_node("socratic"))
        conditional_map["socratic"] = "socratic"

    graph.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        conditional_map,  # type: ignore[arg-type]
    )

    # research -> [fact_checker if present] -> ui_agent
    if has_fact_checker:
        graph.add_node("fact_checker", make_node("fact_checker"))
        graph.add_edge("research", "fact_checker")
        graph.add_edge("fact_checker", "ui_agent")
    else:
        graph.add_edge("research", "ui_agent")

    # Tier-2 specialist agents -> ui_agent (no fact_checker for these in Slice 3)
    if has_discovery:
        graph.add_edge("discovery", "ui_agent")
    if has_learning:
        graph.add_edge("learning", "ui_agent")
    if has_socratic:
        graph.add_edge("socratic", "ui_agent")

    graph.add_edge("ui_agent", END)

    return graph.compile()
