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
Slice 4 addition: writing intent node; active_mode → intent mapping.
Slice 7 addition: graph_agent, literature, contradiction, cross_doc,
  compare, timeline, annotate intent nodes (FR-AGT-06: ≥15 agents).
  New intents are NOT in _MODE_TO_INTENT — they are triggered by explicit
  state.intent (future intent classifier) or route_to_agent in tests.

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

# Maps active_mode strings to intent labels. A mode takes priority over
# a blank state.intent; an explicit state.intent (set by a future full
# intent-detection pass) beats both. "research" is absent on purpose: it
# falls through to _DEFAULT_INTENT. "exploration" routes to the Discovery
# agent (gap/insight analysis) added in Slice 2.
_MODE_TO_INTENT: dict[str, str] = {
    "study": "study",
    "socratic": "socratic",
    "writing": "writing",
    "exploration": "discovery",
}

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
        # Snapshot agent_results keys so we can capture any sub-agents written
        # via route_to_agent A2A hops during this node's run.
        agent_results_before = set(state.agent_results.keys())

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

        # Include any sub-agent results produced via route_to_agent A2A hops
        # (written to state.agent_results by route_to_agent's writeback).
        sub_results = {
            k: v for k, v in state.agent_results.items()
            if k not in agent_results_before
        }
        updates: dict[str, Any] = {"agent_results": {agent.name: result, **sub_results}}

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
    plan-producing entry.

    Intent derivation priority (Slice 4):
      1. Explicit state.intent (set by a future full intent-classifier).
      2. active_mode → intent heuristic (_MODE_TO_INTENT).
      3. _DEFAULT_INTENT ("research") as the safe fallback.
    """
    intent = (
        state.intent
        or _MODE_TO_INTENT.get(state.active_mode or "", "")
        or _detect_intent_from_query(state.query)
        or _DEFAULT_INTENT
    )
    # FR-AGT-05 / §11.5: inject only the tools relevant to this intent, capped
    # at max_tools_per_prompt (NFR-AGT-05). The specialist the intent routes to,
    # plus the always-on research base, define the scoped set.
    from api.core.settings import get_settings

    specialist = _INTENT_TO_AGENT.get(intent, "research")
    scoped = registry.select_tools(
        [specialist, "research"],
        limit=get_settings().max_tools_per_prompt,
    )
    scoped_tools = [spec.name for spec in scoped]

    logger.info(
        "orchestrator.plan",
        intent=intent,
        mode=state.active_mode,
        query_len=len(state.query),
        scoped_tools=len(scoped_tools),
    )
    return {
        "intent": intent,
        "agent_results": {
            "orchestrator": AgentResult(
                agent_name="orchestrator",
                payload={
                    "intent": intent,
                    "mode": state.active_mode,
                    "scoped_tools": scoped_tools,
                    "scoped_tool_count": len(scoped_tools),
                },
                status="ok",
            )
        },
    }


# Branch labels recognised by the conditional edge below. These are *intent*
# labels, NOT mode names — `_MODE_TO_INTENT` translates modes to these (e.g.
# the "exploration" mode maps to the "discovery" intent). Extend ALL of these
# together when adding a new intent:
#   1. Add the agent + register it
#   2. Add a node in `build_graph`
#   3. Add the label here AND in the conditional-edges dict in `build_graph`
#
# Slice 7 intents (not mode-triggered; callable via route_to_agent + explicit
# state.intent from a future intent classifier — FR-AGT-06):
_WIRED_INTENTS = frozenset({
    "research",
    "discovery",
    "study",
    "socratic",
    "writing",
    # Slice 7
    "graph",
    "literature",
    "contradiction",
    "cross_doc",
    "compare",
    "timeline",
    "annotate",
    # Slice 19 tier-3
    "citation",
    "visual",
    "document",
    # B2 tier-4
    "websearch",
})




def _detect_intent_from_query(query: str) -> str:
    """Keyword heuristic: map compare/contradiction/graph/timeline queries to
    the matching intent so the orchestrator can route them without the frontend
    having to set state.intent explicitly.  Returns '' when no rule matches."""
    q = query.lower()
    if any(kw in q for kw in ("compare", "comparison", "contrast", " vs ",
                               "versus", "differences between", "similar")):
        return "compare"
    if any(kw in q for kw in ("contradict", "contradiction", "conflicting",
                               "disagree", "inconsisten")):
        return "contradiction"
    if any(kw in q for kw in ("knowledge graph", "concept map", "related concepts",
                               "graph of", "conceptually")):
        return "graph"
    if any(kw in q for kw in ("timeline", "chronological", "history of",
                               "evolution of", "over time")):
        return "timeline"
    if any(kw in q for kw in ("bibliography", "bibtex", "all references",
                               "format citation", "apa format", "mla format",
                               "cite all", "references list", "full bibliography")):
        return "citation"
    if any(kw in q for kw in ("concept map", "mind map", "visualize", "concept diagram",
                               "comparison chart", "compare visually")):
        return "visual"
    if any(kw in q for kw in ("summarize document", "document overview", "document outline",
                               "summarize this document", "overview of this paper",
                               "sections of", "breakdown of this")):
        return "document"
    if any(kw in q for kw in ("find papers", "search for papers", "papers about",
                               "papers on", "literature on", "recent work on",
                               "related papers", "find sources", "arxiv",
                               "semantic scholar", "search the literature")):
        return "websearch"
    return ""

# Maps each non-default intent label to its primary registered agent name.
# Used by _route_after_orchestrator to fall back gracefully when the agent
# for a detected intent is not registered in the current graph instance.
_INTENT_TO_AGENT: dict[str, str] = {
    "discovery": "discovery",
    "study": "learning",
    "socratic": "socratic",
    "writing": "writing",
    "graph": "graph_agent",
    "literature": "literature",
    "contradiction": "contradiction",
    "cross_doc": "cross_doc",
    "compare": "comparator",
    "timeline": "timeline",
    "annotate": "annotate",
    "schedule": "study_planner",
    # Slice 19 tier-3
    "citation": "citation",
    "visual": "visual_agent",
    "document": "document",
    "websearch": "web_search",
}


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
    # Guard: intent detection may fire for an agent that isn't registered in
    # this particular graph instance (e.g. tests that only wire research+ui).
    # Fall back to the default so LangGraph never gets a KeyError on the edge.
    agent_name = _INTENT_TO_AGENT.get(intent)
    if agent_name and registry.get_agent(agent_name) is None:
        logger.warning(
            "orchestrator.intent_agent_not_registered",
            intent=intent,
            agent=agent_name,
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
    has_writing = registry.get_agent("writing") is not None
    # Slice 9 agents
    has_study_planner = registry.get_agent("study_planner") is not None
    # Slice 19 tier-3 agents
    has_citation = registry.get_agent("citation") is not None
    has_visual = registry.get_agent("visual_agent") is not None
    has_document = registry.get_agent("document") is not None
    has_web_search = registry.get_agent("web_search") is not None
    # Slice 7 agents
    has_graph_agent = registry.get_agent("graph_agent") is not None
    has_literature = registry.get_agent("literature") is not None
    has_contradiction = registry.get_agent("contradiction") is not None
    has_cross_doc = registry.get_agent("cross_doc") is not None
    has_comparator = registry.get_agent("comparator") is not None
    has_timeline = registry.get_agent("timeline") is not None
    has_annotate = registry.get_agent("annotate") is not None

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
    if has_writing:
        graph.add_node("writing", make_node("writing"))
        conditional_map["writing"] = "writing"
    # Slice 7 nodes
    if has_graph_agent:
        graph.add_node("graph_agent", make_node("graph_agent"))
        conditional_map["graph"] = "graph_agent"
    if has_literature:
        graph.add_node("literature", make_node("literature"))
        conditional_map["literature"] = "literature"
    if has_contradiction:
        graph.add_node("contradiction", make_node("contradiction"))
        conditional_map["contradiction"] = "contradiction"
    if has_cross_doc:
        graph.add_node("cross_doc", make_node("cross_doc"))
        conditional_map["cross_doc"] = "cross_doc"
    if has_comparator:
        graph.add_node("comparator", make_node("comparator"))
        conditional_map["compare"] = "comparator"
    if has_timeline:
        graph.add_node("timeline", make_node("timeline"))
        conditional_map["timeline"] = "timeline"
    if has_annotate:
        graph.add_node("annotate", make_node("annotate"))
        conditional_map["annotate"] = "annotate"
    # Slice 9
    if has_study_planner:
        graph.add_node("study_planner", make_node("study_planner"))
        conditional_map["schedule"] = "study_planner"
    # Slice 19 tier-3
    if has_citation:
        graph.add_node("citation", make_node("citation"))
        conditional_map["citation"] = "citation"
    if has_visual:
        graph.add_node("visual_agent", make_node("visual_agent"))
        conditional_map["visual"] = "visual_agent"
    if has_document:
        graph.add_node("document", make_node("document"))
        conditional_map["document"] = "document"
    if has_web_search:
        graph.add_node("web_search", make_node("web_search"))
        conditional_map["websearch"] = "web_search"

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

    # Tier-2 specialist agents -> ui_agent
    if has_discovery:
        graph.add_edge("discovery", "ui_agent")
    if has_learning:
        graph.add_edge("learning", "ui_agent")
    if has_socratic:
        graph.add_edge("socratic", "ui_agent")
    if has_writing:
        graph.add_edge("writing", "ui_agent")
    # Slice 7
    if has_graph_agent:
        graph.add_edge("graph_agent", "ui_agent")
    if has_literature:
        graph.add_edge("literature", "ui_agent")
    if has_contradiction:
        graph.add_edge("contradiction", "ui_agent")
    if has_cross_doc:
        graph.add_edge("cross_doc", "ui_agent")
    if has_comparator:
        graph.add_edge("comparator", "ui_agent")
    if has_timeline:
        graph.add_edge("timeline", "ui_agent")
    if has_annotate:
        graph.add_edge("annotate", "ui_agent")
    # Slice 9
    if has_study_planner:
        graph.add_edge("study_planner", "ui_agent")
    # Slice 19 tier-3
    if has_citation:
        graph.add_edge("citation", "ui_agent")
    if has_visual:
        graph.add_edge("visual_agent", "ui_agent")
    if has_document:
        graph.add_edge("document", "ui_agent")
    if has_web_search:
        graph.add_edge("web_search", "ui_agent")

    graph.add_edge("ui_agent", END)

    return graph.compile()
