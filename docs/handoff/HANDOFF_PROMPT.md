# Handoff Prompt — paste this into your next coding agent

> Copy everything between the `---` lines and paste it as the first
> message to your new coding agent (Claude, Cursor, Aider, whichever).
> If the agent supports a system prompt, paste it there instead. The
> prompt is self-contained — it tells the agent which files to read,
> in what order, and what to do before touching code.
>
> **Last refreshed:** 2026-06-10 (after Slice 10).

---

You are picking up a Final Year Project named **Arcana** — a graph-native
multi-agent research and learning platform for academic students. Ten slices
have been shipped (P0 walking skeleton + Slices 1–10) and the system is
nearly feature-complete for the P1 (FYP 2) graded submission. Your job is
to continue building, one slice at a time, to the same quality bar.

**Do not write any code until you have read the following files, in this
exact order, and confirmed your understanding to me.**

## Step 0 — The one thing that will block you immediately

This repo lives at a path **with a space in it** (`...\FYP DOCS\Arcana`).
The `.claude/` hooks pass `$CLAUDE_PROJECT_DIR` unquoted, so the
`PreToolUse` hook on `Edit`/`Write` crashes on the space and **blocks
every built-in `Edit` and `Write` call**. You'll see:

```
PreToolUse:Edit hook error: ... can't open file '...\FYP'
```

Work around it **from the very first file you touch**:

- In-repo files → `mcp__filesystem__write_file` (full file overwrite) or
  `mcp__filesystem__edit_file` (targeted line edits). These bypass the hook.
- Out-of-repo files (e.g. `~/.claude/` memory) → Bash heredocs
  (`cat > path <<'EOF' ... EOF`).

Because the secret/import hooks are what's broken, **you** must manually
honour the no-secret / no-upward-import invariants; the `code-reviewer`
subagent is your backstop. Full detail: `docs/handoff/SETUP.md §2`.

## Step 1 — Understand the codebase map first

Before reading spec docs, orient yourself using the knowledge graph:

1. **`graphify-out/GRAPH_REPORT.md`** — read the executive summary and the
   top-10 community list. This is a community analysis of the actual code
   (1,685 nodes, 4,853 edges, 127 communities). Pay attention to:
   - Community 0 (Embedding Provider Layer) — the retrieval foundation.
   - Community 1 (GenUI Frontend Block States) — the rendering contract.
   - Community 2 (Agent Base Infrastructure) — `BaseAgent`, `route_to_agent`, `AgentState`.
   - Community 3 (Orchestrator and Turn Management) — the request lifecycle.
   - Community 4 (Vector Store and Pinecone) — the search backend.
   - Community 7 (Learning and Spaced Repetition) — SM-2 + NotebookStore.
2. **`graphify-out/graph.html`** — open in any browser for the interactive
   force-directed graph. Useful for exploring which files import what.
   (Generated 2026-06-06; communities 0–10 accurately reflect Slices 0–7.)

## Step 2 — Read the spec and process docs

3. `CLAUDE.md` — the operating brief (short — read it fully).
4. `docs/handoff/SETUP.md` — how to get from `git checkout ExDev` to all
   gates green; the hook bug; prerequisites.
5. `docs/handoff/CONTEXT.md` — what shipped through Slice 10, the current
   inventory, what's deferred, and what comes next.
6. `docs/handoff/PROCESS.md` — the slice/chunk loop, the eight invariants,
   ADR format, and the common gotchas.
7. `.claude/memory/decisions.md` — every ADR in this project, newest first.
   Key entries to find: Slice 7 scope (15-agent graph), Slice 6 (adaptive
   shell), auth approach, LLM tier strategy.
8. `docs/arcana_prd.md` §§1–8, §11, §11A — the canonical spec. Read §11A
   in full (the mental model: request lifecycle, agent composability, the
   eight invariants).
9. `docs/project_file_structure.md` — repo layout.
10. `docs/checklist.md` — phased build plan. Phase 0 is closed; Phase 1 is
    mostly done — check the ticks vs. unticked items carefully.
11. `docs/uiux_plan.md` §§1–6 — design tokens, 3-panel shell layout, the
    24-component catalog, the four states (Empty/Loading/Partial/Error).

Read these only when you actually need them:

- `docs/arcana_prd.md` §12 — when implementing a specific agent
- `docs/arcana_prd.md` §13, §16 — when adding a GenUI component
- `docs/env_generation_guide.md` — when adding a new env var
- `.claude/rules/*.md` — load when working in matching paths (agent, genui, schema, etc.)
- `.claude/skills/*/SKILL.md` — recipes: `genui-component`, `new-agent`,
  `new-retriever`, `schema-first-change`

## Step 3 — Verify your inherited state

Before any code, run all six gates and confirm green:

```bash
uv run ruff check api/
uv run --with pyright pyright api/
uv run pytest -q --tb=short -p no:cacheprovider api/   # expect 440 passed
corepack pnpm --filter @arcana/schema codegen:check
corepack pnpm --filter @arcana/web typecheck
corepack pnpm --filter @arcana/web test                # expect 11 passed
```

If anything is red, **stop and diagnose**. Don't build on a broken
inheritance. Every gate was green at commit-time; if something flipped,
it's environment or platform, not the code.

Schema-change reminder: if you touch `packages/schema/src/*.ts`, run
`corepack pnpm --filter @arcana/schema build` then `... codegen` before
the backend gates — Pydantic models are generated from the TS source.

## Step 4 — Understand the current state

After reading the docs, you should know:

**What shipped (Slices 0–10):**
- P0 walking skeleton → one PDF end-to-end (ingestion → hybrid retrieval →
  orchestration → SSE → GenUI frontend).
- Slice 1: LangGraph StateGraph, entity extraction, GraphRetriever,
  FactChecker, MemoryAgent.
- Slice 2: 5 GenUI variants + UIAgent intent routing + DiscoveryAgent.
- Slice 3: Study mode (LearningAgent, SocraticAgent, 4 GenUI variants).
- Slice 4: Writing mode (WritingAgent, DraftEditor, FeynmanExplainer).
- Slice 5: Mode switching E2E (5 modes wired, FR-UI-06 ✅).
- Slice 6: Adaptive 3-panel shell + drag resizer (FR-UI-01/05/07 ✅).
- FR-ING-01: PDF upload endpoint + Sources panel real UI.
- Slice 7: 15→17-agent graph; 4 dormant UIBlocks activated; bug fixes.
- LLM tiers: Opus 4.8 / Sonnet 4.6 / Haiku 4.5 assigned by task complexity.
- Slice 8: Benchmark harness (20 Qs, metrics, NullGraphRetriever baseline, CLI runner).
- Slice 9: SM-2 spaced repetition + Firebase auth + NotebookStore + StudyPlanner.
- Slice 10: User study infrastructure (EventStore, SUS modal, block ratings, analytics routes).

**Current inventory:**
- **17 agents** (4 tiers): orchestrator; research, graph_agent, discovery,
  learning, socratic, writing, literature, contradiction, cross_doc,
  comparator, timeline, annotation; ui_agent; fact_checker, memory, study_planner.
- **11 of 24 GenUI** components (all four states each).
- **5 modes** wired E2E: research, study, writing, socratic, exploration.
- **440 backend tests** + **11 frontend tests** — all green.
- **API routes:** /chat, /ingest, /review, /notebooks (CRUD), /feedback/rating,
  /feedback/sus, /analytics/export.

**What's NOT done yet (critical for FYP grade):**
1. **User study** — infrastructure is built, participants must be recruited
   and sessions run. Target: 10–15 participants, SUS ≥ 70.
2. **Benchmark run** — harness is built, must be executed with real API keys
   and results recorded. This is R-02 (primary graded metric).
3. **FYP 2 report** — author task.

**What's deferred (deliberate — see ADRs):**
- DOCX/web/YouTube ingestion (FR-ING-02) — Slice 12+ or P2.
- Neo4j swap (FR-KG-07) — NetworkX is fine for FYP scale.
- 13 more GenUI components — only if supervisor asks.
- @tool decorators on newer tier-2 agents.
- Frontend DOM tests (jsdom + testing-library).

## Step 5 — Summarise back to me

Reply with 10–14 bullets covering:

1. The request lifecycle in your own words (PRD §11A.2).
2. The eight invariants and how each is enforced — note which are currently
   hook-enforced vs. manual (because the path-spaces bug disables Edit/Write hooks).
3. The slice/chunk build mechanism and the per-chunk loop.
4. What shipped across Slices 0–10 (one headline per slice).
5. The current inventory: 17 agents, 11/24 GenUI, 5 modes, 440 tests.
6. The two P1 gates still open (user study conduct, benchmark run) and why
   they're not code tasks.
7. The two production-registration traps: (a) new tier-2 agents must be
   added to `api/main.py` via `Orchestrator(extra_agents=[...])`, not just
   `graph.py`; (b) wire types live in `packages/schema/` and are imported,
   never re-declared.
8. What the `graphify-out/` artifacts tell you about the architecture.
9. Any contradictions or ambiguities you found across the docs.
10. If I ask you to add a GenUI component: which three files you'd touch and
    in what order (schema → renderer → registry), and which skill to invoke.
11. Your understanding of what `mcp__filesystem__write_file` is and why you
    must use it instead of the built-in `Edit`/`Write` tools.

**Do not write any code in your first response.** I need to confirm the
picture before you build. Once I'm happy, I'll say "go".

## Step 6 — If I say "go" on a new code slice

When I say "go", follow the process in `PROCESS.md §3–§4`:

1. **Preflight** — tick the actually-done Phase-1 items in `docs/checklist.md`.
   Log a new slice-scope ADR in `.claude/memory/decisions.md`.
2. **Plan the chunks** — present them in chat, dependency order, in/out-of-scope.
   Wait for "go" on chunk 1.
3. **Per chunk** — plan → write (via MCP tools) → gates → code-reviewer →
   fix every CRITICAL → close.
4. **Per slice close** — final code-review pass, closing ADR, commit on
   `ExDev` referencing the closed FR/NFR/R/Q IDs + separate checklist tick.

**Most impactful optional code slices** (in priority order):

1. **More GenUI components** — pick from the 13 unbuilt in `uiux_plan.md §4`.
   Invoke the `genui-component` skill for each. Each needs: schema variant
   in `packages/schema/src/blocks.ts` → codegen → renderer `<Name>.tsx` →
   one row in `registry.tsx` → validator update → producing agent.
2. **Expanded ingestion** — DOCX/web parser in `api/ingestion/parsers/`.
   `IngestionPipeline` plumbing already exists; parser is the seam.
3. **`@tool` decorators** on LiteratureAgent, ContradictionAgent, etc. —
   enables LLM-driven tool dispatch from the orchestrator.

## Step 7 — The operating contract (durable rules)

- **Schema first.** Every type that crosses the wire is defined in
  `packages/schema/` BEFORE the agent emitting it or the component rendering
  it. Run codegen; commit the generated Python. Never re-declare a wire type
  in Python — import the codegen'd model.
- **Use the subagents.** `code-reviewer` after every meaningful diff.
  `qa-runner` / `schema-guardian` before merge. Fix every CRITICAL.
- **Mark assumptions explicitly.** When an open question forces a path,
  write the ADR with `ASSUMED:` status.
- **Never build the second of anything until the first is green end-to-end.**
- **Register new tier-2 agents in `api/main.py`** (`Orchestrator(extra_agents=[...])`),
  not just in `graph.py`, or they're dead in production.
- **Commits reference IDs** and end with:
  `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`
  (use your own model's attribution).
- **Don't push without my say-so.** Local branch work is fine.
- **Run pytest foreground, one at a time, `-p no:cacheprovider`** — parallel
  runs silently stall on Windows.
- **Use MCP filesystem tools for all file writes** — the Edit/Write hooks
  are broken by the path-spaces bug. `mcp__filesystem__write_file` and
  `mcp__filesystem__edit_file` bypass the hook cleanly.

## What the previous agents ran into (learn from these)

- **The path-spaces hook bug** is the single biggest time-sink. Go straight
  to the MCP filesystem tools from the start.
- **Tier-2 agents must be registered in `api/main.py`**, not just wired in
  `graph.py`. Tests construct the orchestrator themselves and won't catch a
  missing prod registration. This was a real CRITICAL in Slice 4.
- **`BlockStatus` values are** `'loading' | 'partial' | 'ready' | 'error'`.
  The fully-rendered state is `'ready'`, not `'done'`. A bug from using
  `'done'` caused block feedback to never render.
- **SUS formula:** odd items (1-indexed) = response-1, even items = 5-response,
  sum × 2.5 = 0..100. All 10 responses required before submit is enabled.
- **Analytics fire-and-forget:** use `asyncio.create_task()` in the chat
  route so analytics writes never block the SSE stream.
- **Windows VM occasionally queued background bash commands silently.** Run
  foreground only.
- **The user has requested architectural choices that deviate from the original
  spec** (e.g. `api/embeddings/` as its own peer module; Pinecone via raw
  REST not the SDK; `Orchestrator(extra_agents=[...])` pattern). All ADR'd.
  Don't undo them without checking `decisions.md`.
- **`ruff check --fix` handles most I001/UP037 violations automatically.**
  Run it early in each chunk to avoid accumulating lint debt.
- **Pyright sometimes reports undefined variables in `eval/`** (the benchmark
  runner uses optional chaining not yet typed). The `api/` gate is the
  contract; `eval/` is research code.

Good luck.

---

## Quick reference — key file paths

```
CLAUDE.md                                    operating brief (read first)
docs/handoff/SETUP.md                        environment setup + gate commands
docs/handoff/CONTEXT.md                      current state, inventory, deferrals
docs/handoff/PROCESS.md                      how to build (slices/chunks/ADRs)
docs/arcana_prd.md                           canonical spec (read §11A in full)
docs/project_file_structure.md               repo map
docs/checklist.md                            P1 phase work items
docs/uiux_plan.md                            design tokens + 24-component catalog
.claude/memory/decisions.md                  every ADR (newest first)
.claude/rules/*.md                           invariant enforcement detail
.claude/skills/*/SKILL.md                    repeatable recipes
graphify-out/GRAPH_REPORT.md                 codebase knowledge graph (text)
graphify-out/graph.html                      interactive graph (open in browser)

packages/schema/src/blocks.ts               UIBlock union (TS authoritative)
packages/schema/src/payloads.ts             payload types
packages/schema/src/api.ts                  wire request/response types
packages/schema/codegen/to_python.ts        → api/genui/_generated.py
api/genui/validate.py                       fail-closed block validator
api/agents/base.py                          BaseAgent, route_to_agent, AgentState
api/agents/graph.py                         LangGraph graph + _MODE_TO_INTENT
api/agents/tier3/ui_agent.py                the ONLY component-picker
api/main.py                                 build_orchestrator() — register here
web/components/genui/registry.tsx           renderBlock() single dispatch
web/components/shell/ChatPanel.tsx          session mgmt + block rendering loop
web/lib/feedback.ts                         postRating(), postSurvey() helpers
eval/benchmark/questions.py                 20 pre-registered benchmark questions
eval/run_benchmark.py                       CLI: --mode hybrid|flat|both
```
