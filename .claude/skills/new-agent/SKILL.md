---
name: new-agent
description: Use when adding a new agent to Arcana's pipeline — when the user asks to "wire up the Methodology agent", "add a new Tier 2 specialist", or build any of the agents in PRD §12. Follows the per-agent template from §11A.5 and enforces the composability invariants (route_to_agent only, tool budget, no UI selection).
---

# Skill: Add a new agent

**Authority:** PRD §11, §11A, §12 (the 25-agent spec), §11A.5 (per-agent template); `.claude/rules/agent-composability.md`, `.claude/rules/dependency-direction.md`.

Every new agent follows the same shape. Drift from it once and the graph becomes harder to reason about; drift twice and debugging cross-agent failures gets miserable.

## Step 1 — Locate the agent's spec

Open `docs/arcana_prd.md` §12 and find the agent. Confirm its **Role**, **Phase** (P0/P1/P2), **System-prompt intent**, **Triggers**, **Tool calls** with input/output contracts, **Composes-with**, and **Build notes** with FR IDs.

If the agent isn't specified yet, stop. Don't invent one — add the spec to §12 first (and update the count if needed).

## Step 2 — Pick the tier and file

| Tier | Path | Examples |
|---|---|---|
| Tier 1 — Orchestration | `api/agents/orchestrator.py` | (only one) |
| Tier 2 — Specialists | `api/agents/tier2/<name>.py` | research, graph_agent, learning, writing, socratic, discovery |
| Tier 3 — Presentation | `api/agents/tier3/<name>.py` | ui_agent, citation, visual, document |
| Tier 4 — Support | `api/agents/tier4/<name>.py` | fact_checker, annotation, memory, ingestion_agent, web_search, study_planner, analytics |

Match the file structure in `docs/project_file_structure.md`. Don't put a Tier-3 agent in `tier4/`.

## Step 3 — Write the agent file (template)

```python
from api.agents.base import BaseAgent, tool, route_to_agent
from api.stores.graph_store import GraphStore
from api.stores.vector_store import VectorStore
# Import abstractions only. Never concrete backends. Never another agent module.

class <AgentName>Agent(BaseAgent):
    """<one-paragraph role description from §12>."""

    name = "<agent_name>"  # the route_to_agent key, snake_case

    @tool
    async def <tool_one>(self, <typed args>) -> <typed return>:
        """<what it does, in one sentence>."""
        # Implementation. Use storage ABCs. Append to AgentState. Return typed payload.

    @tool
    async def <tool_two>(self, <typed args>) -> <typed return>:
        ...

    async def run(self, state) -> <result>:
        """Entry point invoked by the graph. Reads from state, may call route_to_agent,
        returns a typed payload (or a UIBlock if this is the UI Agent)."""
        # 1. Read needed slots from state (never mutate upstream slots).
        # 2. Call own tools and/or route_to_agent(other_agent, payload, state).
        # 3. Append this agent's slot to state.
        # 4. Return.
```

## Step 4 — Honour the hard rules

- **Max 12 tools per agent** (NFR-AGT-05). If you need more, split the agent.
- **No direct imports of other agent modules.** Use `route_to_agent("<name>", payload, state)`. The hook (`check_imports.py`) will block direct imports.
- **No concrete store imports.** Use `GraphStore` / `VectorStore` / `DocStore` ABCs. The hook will block concrete ones.
- **Never select UI components.** Only the UI Agent does that (invariant #3). Return typed payloads only.
- **Never emit raw HTML/text/markdown.** Output is either a payload matching a `UIBlock` variant, or a `route_to_agent` call (invariant #2).
- **AgentState contributions are append-only.** Don't overwrite another agent's slot.

## Step 5 — Wire into the graph

If this agent participates in the LangGraph flow:

1. Open `api/agents/graph.py`.
2. Add a node for the agent.
3. Add conditional routing edges (from Orchestrator / other specialists / to UI Agent or Fact Checker).
4. Ensure terminal-join routes through the UI Agent (invariant #6).
5. If it's invokable A2A, add it to the registry consulted by `route_to_agent`.

## Step 6 — Tool injection scope

Open `INTENT_TOOL_MAP` (or equivalent in `api/agents/base.py`). For each intent the agent participates in, add its tools — but keep each intent's total tool count ≤ 12.

## Step 7 — Update docs

- `docs/checklist.md` — tick the matching FR-AGT-* item (or add a new line if it's a P1/P2 entry not yet listed).
- `docs/project_file_structure.md` — confirm the agent file is mentioned in the tree.

## Step 8 — Tests

Minimum: one unit test that mocks the LLM and confirms the agent's `run()` produces a payload matching the schema for its emitted `UIBlock` variant (or its expected `route_to_agent` call). Add to `api/tests/agents/test_<name>.py`.

## Done checklist (paste into the commit)

- [ ] File in the correct tier folder per §12.
- [ ] Inherits `BaseAgent`, tools via `@tool`, fully typed signatures.
- [ ] No agent-to-agent imports; all composition via `route_to_agent`.
- [ ] No concrete store imports.
- [ ] ≤ 12 tools.
- [ ] No raw text/HTML output paths.
- [ ] Node + edges added to `api/agents/graph.py` (if in the graph).
- [ ] `INTENT_TOOL_MAP` updated; per-intent tool count still ≤ 12.
- [ ] Unit test green.
- [ ] Commit references the FR-AGT-* ID.
- [ ] `code-reviewer` and `qa-runner` subagents report green.
