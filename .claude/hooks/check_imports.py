#!/usr/bin/env python3
"""
Arcana — dependency-direction guard (PreToolUse on Write/Edit/MultiEdit for *.py).

Reads the Claude Code hook JSON on stdin. For Python files under api/, parses
the post-edit content with `ast` and flags imports that violate the one-way
layer order:

  routes  →  agents  →  retrieval / stores  →  llm  →  core

Imports flow DOWN only. Anything pointing back upward is a violation.
Also flags agent-to-agent direct imports (must use route_to_agent).
Also flags agent imports of concrete store implementations (must use ABCs).

Exit 0 = OK, exit 2 = block (stderr shown to the model).

Authority: PRD §9, §11A.3 invariants #5, #7; .claude/rules/dependency-direction.md,
.claude/rules/agent-composability.md.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

# Layer order, low index = upper layer (depends on layers below).
LAYERS = ["routes", "agents", "retrieval", "stores", "llm", "core"]
LAYER_INDEX = {name: i for i, name in enumerate(LAYERS)}

# Concrete store modules that agents must NOT import directly.
CONCRETE_STORES = {
    "api.stores.neo4j_store",
    "api.stores.networkx_store",
    "api.stores.pinecone_store",
    "api.stores.firestore_store",
}


def layer_of(module_path: str) -> str | None:
    """Return the layer name for an api.<layer>.… module path, else None."""
    parts = module_path.split(".")
    if len(parts) >= 2 and parts[0] == "api" and parts[1] in LAYER_INDEX:
        return parts[1]
    return None


def file_layer(file_path: str) -> str | None:
    """Return the layer of the file being edited (best effort).

    Handles both absolute paths (`/repo/api/agents/x.py`) and repo-relative
    paths (`api/agents/x.py`). Requires the file to be under `api/<layer>/`.
    """
    p = Path(file_path).as_posix()
    # Normalise: split on `/api/` and inspect what follows.
    if "/api/" in p:
        tail = p.split("/api/", 1)[1]
    elif p.startswith("api/"):
        tail = p[len("api/"):]
    else:
        return None

    parts = tail.split("/", 1)
    if not parts:
        return None
    candidate = parts[0]
    return candidate if candidate in LAYER_INDEX else None


def violations(content: str, current_layer: str, file_path: str) -> list[str]:
    """Return human-readable violation messages."""
    msgs: list[str] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # If it doesn't parse, let downstream tooling (linter, type-checker) complain.
        return []

    cur_idx = LAYER_INDEX[current_layer]

    for node in ast.walk(tree):
        targets: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            targets.append(node.module)
        elif isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)

        for module in targets:
            target_layer = layer_of(module)
            if target_layer is None:
                continue

            target_idx = LAYER_INDEX[target_layer]

            # Rule 1: imports flow down only.
            if target_idx < cur_idx:
                msgs.append(
                    f"  ✗ upward import: `{current_layer}/` cannot import from `{target_layer}/`\n"
                    f"    offending: from {module} import …\n"
                    f"    fix: invert the dependency, or move the shared code into a lower layer."
                )

            # Rule 2: agent ↛ agent direct import.
            if current_layer == "agents" and target_layer == "agents":
                # Allow imports from agents/base, agents/graph (LangGraph wiring), or the same file.
                allowed_siblings = {"api.agents.base", "api.agents.graph"}
                same_file = module.replace(".", "/") in file_path.replace(".py", "")
                if module not in allowed_siblings and not same_file:
                    msgs.append(
                        f"  ✗ agent-to-agent import: `{module}` — agents compose via `route_to_agent` only.\n"
                        f"    fix: replace the import with `await route_to_agent(\"<agent_name>\", payload, state)`."
                    )

            # Rule 3: agents must use store ABCs, not concrete backends.
            if current_layer == "agents" and module in CONCRETE_STORES:
                msgs.append(
                    f"  ✗ concrete store import: `{module}` — agents must use the abstract `GraphStore`/"
                    f"`VectorStore`/`DocStore` interfaces.\n"
                    f"    fix: import from `api.stores.graph_store` (etc.) and inject the concrete impl via settings."
                )

    return msgs


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[check_imports] warning: malformed hook JSON ({e}); pass-through.", file=sys.stderr)
        return 0  # Don't block on malformed hook input.

    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    if tool == "Write":
        path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")
    elif tool == "Edit":
        path = tool_input.get("file_path", "")
        content = tool_input.get("new_string", "")
    elif tool == "MultiEdit":
        path = tool_input.get("file_path", "")
        edits = tool_input.get("edits", [])
        content = "\n".join(e.get("new_string", "") for e in edits)
    else:
        return 0

    if not path.endswith(".py"):
        return 0
    posix = path.replace("\\", "/")
    if "/api/" not in posix and not posix.startswith("api/"):
        return 0

    cur_layer = file_layer(path)
    if cur_layer is None:
        return 0

    msgs = violations(content, cur_layer, path)
    if not msgs:
        return 0

    print(f"🚫 Dependency-direction violations in {path}", file=sys.stderr)
    print(file=sys.stderr)
    for m in msgs:
        print(m, file=sys.stderr)
        print(file=sys.stderr)
    print("Layer order (down only): routes → agents → retrieval/stores → llm → core", file=sys.stderr)
    print("See .claude/rules/dependency-direction.md and .claude/rules/agent-composability.md", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
