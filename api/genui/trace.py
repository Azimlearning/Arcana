"""Build the pipeline trace payload from a completed AgentState.

The trace event is emitted on the SSE stream (event: trace) before the
first block so the frontend can start rendering the agent chain immediately.
It is metadata — not a UIBlock — so it lives here (genui tier) rather than
in packages/schema.

Wire format emitted in the SSE stream:
  {
    "agents": [
      {"name": "orchestrator", "tier": 1, "status": "ok", "is_hop": false},
      {"name": "comparator",   "tier": 2, "status": "ok", "is_hop": false},
      {"name": "graph_agent",  "tier": 2, "status": "ok", "is_hop": true},
      ...
    ],
    "hops_used": 2,
    "intent": "compare"
  }
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api.agents.base import AgentState

# Maps agent registry names to their tier numbers (from PRD §11 + uiux_plan §2.1).
_AGENT_TIERS: dict[str, int] = {
    # Tier 1 — Orchestration
    "orchestrator": 1,
    # Tier 2 — Core Intelligence
    "research": 2,
    "comparator": 2,
    "graph_agent": 2,
    "literature": 2,
    "contradiction": 2,
    "cross_doc": 2,
    "discovery": 2,
    "learning": 2,
    "socratic": 2,
    "writing": 2,
    "timeline": 2,
    "annotate": 2,
    # Tier 3 — Output
    "ui_agent": 3,
    # Tier 4 — Quality / Meta
    "fact_checker": 4,
    "memory": 4,
    "study_planner": 4,
}

# Maps intent labels to their primary tier-2 agent (mirrors graph._INTENT_TO_AGENT
# but maintained independently to avoid a genui→agents import, which would violate
# the dependency direction rule: routes→agents→retrieval, not genui→agents).
_INTENT_PRIMARY: dict[str, str] = {
    "research": "research",
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
}


def build_trace(state: AgentState) -> dict[str, Any]:
    """Build the trace payload dict from a finished AgentState.

    Iterates agent_results in insertion order (Python 3.7+ dict) to preserve
    execution sequence. Marks tier-2 agents as A2A hops when they ran but
    were not the primary agent for the detected intent and budget.hops_used > 0.
    """
    intent = state.intent or "research"
    primary = _INTENT_PRIMARY.get(intent)
    hops_used = state.budget.hops_used

    agents: list[dict[str, Any]] = []
    for name, result in state.agent_results.items():
        tier = _AGENT_TIERS.get(name, 2)
        is_hop = (
            hops_used > 0
            and tier == 2
            and name != primary
        )
        agents.append({
            "name": name,
            "tier": tier,
            "status": result.status,
            "is_hop": is_hop,
        })

    return {
        "agents": agents,
        "hops_used": hops_used,
        "intent": intent,
    }
