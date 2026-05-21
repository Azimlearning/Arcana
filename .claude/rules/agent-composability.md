---
applies_to: "api/agents/**"
---

# Rule: Agents compose through `route_to_agent` only

**Authority:** PRD §11.3, §11.4, §11A.3 (invariants #4, #5, #6); FR-AGT-03, FR-AGT-04, FR-AGT-10.

## The mechanism

Agents call other agents **only** through `route_to_agent(agent_name, payload, hop_state)`. Never via direct import.

```python
# WRONG
from api.agents.graph_agent import GraphAgent
result = GraphAgent().expand(concept)

# RIGHT
result = await route_to_agent("graph_agent", {"concept": concept}, state)
```

## Why

- `route_to_agent` enforces the hop budget (HOP_BUDGET) and the token budget (TOKEN_BUDGET_PER_TURN). Direct imports bypass both — agents loop, costs explode.
- `route_to_agent` appends to shared `AgentState`. Direct imports don't — the trace becomes unreadable, debugging a 25-agent graph turns into archaeology.
- `route_to_agent` routes through the LangGraph terminal-join. Direct imports skip the UI Agent — you return raw text instead of a typed block. Invariant #6 broken.
- Direct imports create dependencies between agents. Adding the 18th agent shouldn't require touching the 17th.

## The agent template

Every agent file follows the per-agent template from PRD §11A.5:

1. Subclasses `BaseAgent`.
2. Exposes tools via `@tool` decorators on methods — schema inferred from type hints.
3. Reads from `AgentState` (never mutates upstream slots; appends to its own slot).
4. Returns either: a typed payload to be wrapped, or a `route_to_agent` call, or both.
5. Never picks UI components. Only the UI Agent does that (invariant #3).
6. Never emits raw HTML, raw text, or markdown to the user. Only typed `UIBlock` payloads (invariant #2).

## Hard limits

- `max_tools_per_prompt = 12` (NFR-AGT-05). If your agent needs more, split it.
- Hop budget enforced at runtime — exceeding it terminates at the UI Agent with a partial result, never silently truncates.
- Every agent invocation logs a span (per `decisions.md` if Langfuse is wired).

## Checklist before committing an agent

- [ ] Inherits `BaseAgent`. No direct imports of other agent modules.
- [ ] All inter-agent calls go through `route_to_agent`.
- [ ] Tools declared via `@tool`, signatures typed.
- [ ] No raw text/HTML output — only typed payloads matching a `UIBlock` variant in `packages/schema/blocks.ts`.
- [ ] No direct backend imports (uses `GraphStore`, `VectorStore`, `DocStore` ABCs).
- [ ] Tool count ≤ 12.
- [ ] Registered in the agent registry; new node added to `api/agents/graph.py` if it joins the LangGraph flow.
