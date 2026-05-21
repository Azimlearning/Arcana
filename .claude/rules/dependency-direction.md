---
applies_to: "api/**"
---

# Rule: One-directional dependency flow

**Authority:** PRD §9, §11A.3; project_file_structure.md golden rule #2.

## The direction

```
routes  →  agents  →  retrieval / stores  →  llm  →  core
```

Imports flow **down only**. Nothing imports upward. Ever.

- `routes/` may import from `agents/`, `retrieval/`, `stores/`, `llm/`, `core/`.
- `agents/` may import from `retrieval/`, `stores/`, `llm/`, `core/` — **never** from `routes/`, **never** from another concrete agent module.
- `retrieval/` may import from `stores/`, `llm/`, `core/` — never agents, never routes.
- `stores/` may import from `core/` only — never `llm/`, `retrieval/`, `agents/`, `routes/`.
- `llm/` may import from `core/` only.
- `core/` imports nothing from the rest of the app.

## What violates it

- `from api.agents.research import ...` inside a retriever — violation (agents import retrievers, not the other way around).
- `from api.routes.chat import ...` anywhere outside `routes/` — violation.
- `from api.agents.graph_agent import GraphAgent` inside another agent — violation. Use `route_to_agent("graph_agent", payload)` (see `rules/agent-composability.md`).
- `from api.stores.neo4j_store import Neo4jGraphStore` inside an agent — violation. Use the `GraphStore` ABC.

## How to check

The pre-commit hook (`.claude/hooks/check_imports.py`) AST-parses changed Python files and flags upward imports. Run it locally before commit:

```bash
python .claude/hooks/check_imports.py path/to/changed_file.py
```

CI runs it too — a violation fails the build.

## Why this is non-negotiable

The dependency direction is what lets `GraphStore` swap from NetworkX to Neo4j with one config change (R-06), what lets us add an agent without touching another agent, and what makes the schema codegen safe. Break the direction once and you've coupled layers that have to be uncoupled before P1.
