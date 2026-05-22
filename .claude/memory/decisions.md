# Arcana — Decisions Log

> Lightweight ADR-style record of choices made during the build. The point isn't documentation theatre — it's that Claude Code sessions don't carry memory between runs, and the spec has open questions (Q-03 to Q-10) that may get resolved by *assumption* mid-build. Capturing those assumptions here keeps future sessions, the supervisor review, and the FYP defence on the same page.
>
> **When to write here:**
> - You hit an open question (Q-03..Q-10) without an answer and pick a path to keep moving.
> - You make a choice not explicitly in the PRD (a library, an algorithm constant, a UX detail).
> - You discover a spec contradiction and resolve it.
> - You opt out of a rule with a stated reason (e.g. `# pragma: allowlist secret`).
>
> **Format:** one short entry per decision. Date, the question, the decision, why, and what would force a revisit.

---

## Template

```markdown
### YYYY-MM-DD — <short title>

- **Status:** ASSUMED | DECIDED | REVISITED
- **Context:** what was unclear or open. Reference FR/NFR/R/Q IDs.
- **Decision:** what we're doing.
- **Why:** the trade-off that tipped it.
- **Revisit if:** the condition that would force reconsidering.
```

---

## Entries

<!-- New entries go below this line, newest first. -->

### 2026-05-22 — Slice 1 DONE: agent maturity landed

- **Status:** DECIDED
- **Context:** All five chunks of slice 1 (LangGraph + entity extraction + real GraphRetriever + Fact Checker + Memory Agent) are green. Backend 263 passed (P0: 200, slice 1: +63). Ruff + pyright clean. Multi-turn memory continuity test locks the contract. Error-status blocks excluded from memory writeback (W1). Prompt versions stamped on extraction + fact-check + graph scoring for R-02 partition (W4). Unknown-intent routing falls back to default with a warning log (W3).
- **Decision:** Phase 0 release gate (`docs/checklist.md` §0) is now satisfied as far as code goes: PDF ingest → graph built → 3-source hybrid retrieval → grounded cited answers; Orchestrator + Research + Graph (extraction+retrieval) + Fact Checker + Memory Agent all demonstrably running. Remaining gate items (FYP 1 report, hybrid-vs-flat benchmark) are P1 §1.12 / author tasks, not code.
- **Why:** The walking-skeleton mandate was "narrow first, breadth later." Slice 1 closes the agent-graph seam so every later tier-2 agent (Writing, Study, Socratic, …) drops into a path that already enforces hop budgets, fact-checks claims, remembers history, and traverses the entity graph.
- **Revisit if:** Never. Slice closed; next slice opens its own thread (slice 2 = wider GenUI catalog + UI-Agent intent-driven component selection).

### 2026-05-22 — Slice 1 scope: agent maturity (LangGraph + extraction + graph retriever + Fact Checker + Memory Agent)

- **Status:** DECIDED
- **Context:** P0 skeleton wired research → ui_agent as a direct call and shipped GraphRetriever as `return []`. Both were ADR'd deferrals so we could prove the wire contract before adding breadth. Slice 1 closes those gaps in dependency order: LangGraph first (every other agent registers as a node), then entity extraction (the GraphRetriever needs a populated graph), then GraphRetriever traversal logic, then Fact Checker (verifies the now-grounded synthesis), then Memory Agent (gates the LangGraph entry).
- **Decision:** Five-chunk slice with `langgraph` as the only new heavy dep. Pydantic `AgentState` is kept (langgraph 0.2+ supports BaseModel state); each existing agent gets a thin `make_node(agent)` wrapper that adapts `BaseAgent.run` to the langgraph node signature `(state) -> dict`.
- **Why:** Doing breadth (other tier-2 agents) before LangGraph would mean every new agent ships its own ad-hoc orchestration that gets ripped out later. Doing GraphRetriever before extraction would leave it returning empty for another slice. Order is forced by the dependency direction.
- **Revisit if:** LangGraph's BaseModel-state API regresses (pin a known-good version), OR entity-extraction LLM cost blows the per-PDF budget (slice 1 ADR will record actual measured cost; if it crosses a threshold we switch the extraction pass to a cheaper provider).

### 2026-05-22 — P0 walking-skeleton slice DONE

- **Status:** DECIDED
- **Context:** The walking-skeleton slice (subsystems 1–10) covered the end-to-end vertical path: drop a PDF → ingest → hybrid retrieve → research-agent synth → ui-agent emits CitedSummary → server-validates fail-closed → SSE-streams → web registry renders all four states. Ten subsystems, 200 backend tests + 7 frontend tests, all four gates (ruff / pyright / pytest / vitest) green, codegen drift detector wired into CI.
- **Decision:** Declare the P0 skeleton complete. Next slice (P1 first cut) starts with: LangGraph `StateGraph` assembly (FR-AGT-04), entity extraction → graph build → real `GraphRetriever`, Fact Checker (FR-AGT-09), Memory Agent.
- **Why:** The skeleton's job was to de-risk the schema codegen, the SSE wire contract, the dependency-direction enforcement, and the seven-layer dependency chain — all proven by the gates passing. Going wide before the seam was load-bearing would have been faster but fragile; going narrow first means every later component drops into a path that already works.
- **Revisit if:** Never. Slice is closed; the next slice opens its own thread.

### 2026-05-21 — Python `pyproject.toml` lives at repo root (not `api/`)

- **Status:** DECIDED
- **Context:** `docs/project_file_structure.md` §1 places `pyproject.toml` at `api/pyproject.toml`. But the dependency-direction hook (`.claude/hooks/check_imports.py`) detects layer membership by matching `api.<layer>.*` import prefixes — meaning the codebase has to use `from api.core.settings import ...`, not `from core.settings import ...`. For `api.*` imports to resolve via setuptools' `packages.find`, the package root (where pyproject lives) must sit **above** `api/`, not inside it.
- **Decision:** Place `pyproject.toml` and `.python-version` at the repo root. Top-level Python packages are `api` (and `eval/` once it lands). Imports throughout use the `api.<layer>.<module>` form the hook enforces.
- **Why:** The hook is the mechanism behind invariant #5 (composability) and invariant #7 (storage abstractions). Breaking the hook to satisfy a structural-doc preference would gut the enforcement layer. Updating the doc is cheap; rewriting the hook to also recognise bare `from core.…` imports is fragile.
- **Revisit if:** A second Python project lands (e.g. `eval/` grows its own deps) and we genuinely need separate package roots.

### 2026-05-21 — Walking-skeleton slice deferrals (StateGraph, Memory Agent, Fact Checker)

- **Status:** ASSUMED
- **Context:** PRD §11A.2 mandates a canonical lifecycle (Memory Agent first, hybrid retrieve, specialists, Fact Checker before any user-facing claim, terminal UI Agent) and FR-AGT-04 requires the LangGraph `StateGraph` assembly in `api/agents/graph.py`. The user's walking-skeleton brief explicitly defers all of these: orchestrator → research → ui_agent runs as a direct async call, Memory Agent and Fact Checker are absent.
- **Decision:** Build the slice without `agents/graph.py`, Memory Agent, or Fact Checker. The `CitedSummary` produced by this slice is grounded (hybrid retrieve participates) but **not fact-checked** — citation-accuracy invariant target (≥90%, FR-AGT-09) is *deferred*, not satisfied.
- **Why:** Walking-skeleton mandate (PRD §11A "build P0 as a vertical slice end-to-end before going wide"). FR-AGT-04 + Memory Agent + Fact Checker are P1 in `docs/checklist.md` §1.4–§1.5, so deferring matches the checklist.
- **Revisit if:** Subsystem 7 (agents) is green and we begin the second slice — the next slice MUST add `agents/graph.py` (FR-AGT-04) and the Fact Checker before any user-facing demo or evaluation run.

### 2026-05-21 — `DocStore` is a local-filesystem stub for the slice

- **Status:** ASSUMED
- **Context:** PRD locks Firebase Firestore + Storage for `DocStore`. The slice does not have accounts, multi-user isolation, or persisted metadata as in-scope concerns, and `docs/env_generation_guide.md` §2.6 explicitly permits a "P0 shortcut" stubbing auth + local metadata until P1 §1.8.
- **Decision:** Implement `DocStore` as a thin filesystem-backed module (`api/stores/doc_store.py`) that writes raw files under `infra/local_storage/` and metadata as JSON sidecars. The `DocStore` ABC is the seam; the Firestore impl arrives in a later slice.
- **Why:** Permitted by env guide §2.6; removes Firebase credential dependency for the slice; preserves the storage-abstraction invariant (#7) because agents still see only `DocStore`.
- **Revisit if:** P1 §1.8 (accounts & persistence) begins.

### 2026-05-21 — Spec docs moved to `docs/`

- **Status:** DECIDED
- **Context:** Repo shipped with the 5 spec docs at root, but `CLAUDE.md`, `.claude/memory/preflight.md`, and `docs/project_file_structure.md` §0 all reference them under `docs/`. Three authority files in agreement; the filesystem disagreed.
- **Decision:** Moved `arcana_prd.md`, `project_file_structure.md`, `uiux_plan.md`, `checklist.md`, and (newly supplied) `env_generation_guide.md` into `docs/`. `RefDocs/` (older snapshots) left untouched; not authoritative.
- **Why:** When authority and filesystem disagree, follow authority — it's the less-coupled change (one move vs. editing 3+ docs and the operating layer).
- **Revisit if:** Never. Locked.

### 2026-05-21 — `.claude/` operating layer scaffolded

- **Status:** DECIDED
- **Context:** No mechanism enforced the eight invariants and the architectural rules — they lived only in spec prose.
- **Decision:** Created `.claude/` with a trimmed `CLAUDE.md`, path-scoped rule files, three subagents (schema-guardian, code-reviewer, qa-runner), four Skills, and three hooks (secret-literal block, dependency-direction block, post-write format + check).
- **Why:** Spec invariants enforced in review only are spec invariants honoured maybe. Hooks turn them into mechanism.
- **Revisit if:** Claude Code hook/agent schema changes (track release notes); new invariants emerge from PRD updates.
