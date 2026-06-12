# Arcana — How We Build (slice-by-slice mechanism)

> The thing to learn ONCE then apply. Read this top to bottom before
> writing any code on this branch. Companion to [`CLAUDE.md`](../../CLAUDE.md)
> (operating brief — also load it; it's shorter), [`SETUP.md`](SETUP.md)
> (how to verify your inherited state), and [`CONTEXT.md`](CONTEXT.md)
> (what's already shipped).
>
> **Last refreshed:** 2026-06-10 (after Slice 10).

## 1. The mental model

Arcana is built as a **vertical walking-skeleton**: one slice at a time,
top-to-bottom across every layer. The first slice (P0) wired ingestion
through frontend with one example of everything. Each subsequent slice
adds breadth on top of the same path, never sideways.

Per PRD §11A.5: *"Never build the second of anything until the first is
green end-to-end."* If you're tempted to ship two agents in parallel,
two GenUI components, two retrievers — stop and check the slice plan.

## 2. Slices vs chunks

- A **slice** is a deliverable vertical increment, typically 1–2 weeks
  of work. It has a stated goal and a closing ADR that records what was
  deferred.
- A **chunk** is a single logical unit within a slice — usually 1 file
  + 1 test file + ~30 minutes of focused work. Each chunk ends with all
  gates green and (when meaningful) a code-review pass.

Shipped so far (all on `ExDev`):

| Slice | Goal | Commit |
|---|---|---|
| 0 | P0 walking skeleton (10 chunks, one per subsystem) | `267b035` |
| 1 | Agent maturity (LangGraph, extraction, GraphRetriever, Fact Checker, Memory) | `8d5644c` |
| 2 | GenUI catalog breadth + UIAgent intent routing + DiscoveryAgent | `24d8c84` |
| 3 | Study mode (Learning + Socratic agents, 4 GenUI variants) | `307bbe2` |
| 4 | Writing mode (WritingAgent + DraftEditor + Feynman production) | `9e5a78a` |
| 5 | Mode switching end-to-end (5 modes, FR-UI-06) | `e73e830` |
| 6 | Adaptive 3-panel shell with drag resizer (FR-UI-01/05/07) | `3e2e430` |
| — | PDF upload endpoint + Sources panel UI (FR-ING-01) | `e4100f3` |
| 7 | 15-agent graph, activate 4 dormant UIBlocks (FR-AGT-06) | `837404e` |
| — | Three-tier LLM strategy Opus/Sonnet/Haiku (NFR-COST-01) | `25ab104` |
| 8 | Benchmark harness: hybrid vs flat-RAG, 20 Qs (R-02, Q-03) | `1b4d5b9` |
| 9 | SM-2 spaced repetition + auth + notebooks (FR-LRN-02, FR-USR-01/03/06) | `28560f6` |
| 10 | User study infrastructure: events, SUS, block ratings (FR-ANL-01/03) | `13abd86` |

**Next:** user study conduct + benchmark run (author tasks); optional code
slices for more GenUI components or expanded ingestion.

## 3. The per-chunk loop

Every chunk follows the same shape:

```
1. PLAN   — say what you're going to build, in words, in chat
2. WRITE  — files + tests
3. GATES  — ruff + pyright + pytest + (vitest if web) + codegen:check
4. REVIEW — code-reviewer subagent on the chunk's diff
5. FIX    — address every CRITICAL; weigh WARNINGs; defer SUGGESTIONs
6. CLOSE  — mark the chunk's todo complete, move to the next
```

### ⚠️ You cannot use the `Edit`/`Write` tools in this repo

The repo path has a space (`FYP DOCS`) and the `.claude/` hooks pass
`$CLAUDE_PROJECT_DIR` unquoted, so the `PreToolUse` hook crashes and
**blocks every `Edit`/`Write` call**. Use the MCP filesystem tools for
in-repo files (`mcp__filesystem__write_file`, `mcp__filesystem__edit_file`)
and Bash heredocs for files outside the repo (e.g. memory). Full detail in
SETUP.md §2 and CONTEXT.md. Reach for these from the start — don't burn a
turn rediscovering the block.

### The gates that must be green

| Gate | Command | What it catches |
|---|---|---|
| ruff | `uv run ruff check api/` | Style, dead imports, simple bugs |
| pyright | `uv run --with pyright pyright api/` | Type errors |
| pytest | `uv run pytest -q --tb=short -p no:cacheprovider api/` | Behaviour (**440 passing**) |
| codegen | `corepack pnpm --filter @arcana/schema codegen:check` | Schema drift (TS↔Pydantic) |
| web types | `corepack pnpm --filter @arcana/web typecheck` | Frontend types |
| web tests | `corepack pnpm --filter @arcana/web test` | Frontend logic (**11 passing**) |

**Schema-first reminder:** if you touch `packages/schema/src/*.ts`, run
`corepack pnpm --filter @arcana/schema build` then `... codegen` (regenerates
`api/genui/_generated.py`) **before** the backend gates. `codegen:check`
fails the build if the generated Python drifts from the TS source.

**Run gates in foreground, one at a time, with `-p no:cacheprovider` on
pytest.** Background pytest runs from the harness queue and silently stall
on Windows. The CLI is the source of truth — trust it over IDE hints.

### Code review subagent

After every meaningful diff, invoke the project's `code-reviewer` subagent:

```
Use the code-reviewer subagent on the changes since HEAD.
```

It enforces the eight invariants and the rules in `.claude/rules/*.md`,
producing a CRITICAL / WARNING / SUGGESTION report with file:line refs.
**Fix every CRITICAL before proceeding**; weigh WARNINGs; defer SUGGESTIONs
into the slice's follow-up list. (Slices 4 and 5 each found a real CRITICAL
this way — agents not registered in `main.py`, and an inline Literal
duplicating the schema `Mode`. Both were fixed pre-commit.)

## 4. The per-slice loop

A slice is opened by:

1. **Plan the slice in chat.** Present the chunks, the dependency order,
   the in/out-of-scope list, and any decisions you want the user to make.
   Wait for "go". Once in rhythm, batching is allowed.
2. **Preflight.** Always two things:
   - Tick the actually-done boxes in `docs/checklist.md` for the previous
     slice. Be honest about deferrals — annotate each `(→ slice N)`.
   - Log a slice-scope ADR in `.claude/memory/decisions.md` recording the
     scope decision, what forced the chunk order, and new constraints.

A slice is closed by:

1. **Final code-review pass** on the full slice diff.
2. **Apply CRITICAL + worthwhile WARNING fixes.**
3. **Write the closing ADR** — `### YYYY-MM-DD — Slice N complete`.
4. **Commit on `ExDev`** with a message referencing the IDs it closes:

   ```
   feat(slice-N): <name> — <highlights> — closes FR-XXX-YY

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
   ```

   Use the attribution for whatever model you actually are (the system
   prompt's git protocol specifies it). **Don't push without the user's
   say-so** — local branch work is fine; remote pushes need permission.
   Keep a separate `chore(checklist): ...` commit for the checklist tick.

## 5. The eight invariants & how they're enforced

PRD §11A.3 is authoritative. Paraphrased:

1. **Ground before generating** — every claim has retrieval evidence.
2. **UI is data, never code** — agents emit typed `UIBlock`, never HTML/text.
3. **Only the UI Agent picks components** — others produce data.
4. **Append to shared state** — never overwrite arbitrarily.
5. **Composability only via `route_to_agent`** — no direct agent imports.
6. **Always terminate at the UI Agent** — including failure paths.
7. **Storage behind abstractions** — `GraphStore`/`VectorStore`/`DocStore` ABCs only.
8. **No secret literals** — config via `Settings`, secrets via env.

| Invariant | Mechanism |
|---|---|
| #1 | Tests + code review |
| #2 | `api/genui/validate.py` fail-closes before SSE |
| #3 | `web/components/genui/registry.tsx` single dispatch |
| #4 | LangGraph reducers (`Annotated[..., add]`) |
| #5 | `.claude/hooks/check_imports.py` blocks agent→agent imports |
| #6 | `Orchestrator` graph + SSE error-frame terminator |
| #7 | `.claude/hooks/check_imports.py` blocks concrete-store imports from agents |
| #8 | `.claude/hooks/check_secrets.py` regex-scans every write |

Note: the import/secret hooks **also** run on `Edit`/`Write` as
`PreToolUse` — which is exactly what the path-spaces bug breaks (§3). When
you write via the MCP filesystem tools you bypass the hook, so **you are
responsible for honouring #5/#7/#8 manually** — the code-reviewer is your
backstop. Don't import an agent into another agent, don't import a concrete
store into an agent, don't inline a secret.

## 6. ADR-keeping (`.claude/memory/decisions.md`)

Every non-obvious decision lands as an ADR. Format:

```markdown
### YYYY-MM-DD — <short title>

- **Status:** ASSUMED | DECIDED | REVISITED
- **Context:** what was unclear or open. Reference FR/NFR/R/Q IDs.
- **Decision:** what we're doing.
- **Why:** the trade-off that tipped it.
- **Revisit if:** the condition that would force reconsidering.
```

Insert newest-first below the `<!-- New entries go below this line -->`
marker. Don't backfill into older entries; never delete. Two specific
times to write one: you hit an open question (PRD §25 Q-03..Q-10) — mark
`ASSUMED:`; or you deviate from a spec doc — quote both sides, justify, log.

## 7. Common gotchas you'll hit

### The hook path-spaces bug (the big one)

Covered in §3 and SETUP.md §2. `Edit`/`Write` are blocked; use MCP
filesystem tools / Bash heredocs.

### IDE diagnostics lag behind your edits

The harness sometimes shows "Import X unused" / "Could not find name Y"
from an intermediate file state. The CLI gates reflect actual state. CLI
green + IDE complaining → trust the CLI.

### Pytest in the background queues silently on Windows

Run pytest synchronously in foreground, one at a time, with
`-p no:cacheprovider`. The full suite finishes in ~5–10 seconds.

### `pnpm` isn't on PATH in child shells

Use `corepack pnpm` everywhere, or don't call pnpm recursively in scripts.

### CRLF/LF warnings on `git add`

Windows checkout converts LF → CRLF. Harmless; Git normalizes.

### LangGraph + Pydantic state

LangGraph 0.2+ supports Pydantic BaseModel state. Reducers via
`Annotated[..., reducer_fn]`. Mutation within a single node call IS
preserved (Python aliasing); mutation ACROSS nodes is NOT (langgraph
`model_copy`s between steps). The `make_node` wrapper in `graph.py`
snapshots list lengths and returns only deltas so `add` reducers don't
double-count.

### New tier-2 agents must be registered in `api/main.py`

Adding a node in `graph.py` is not enough — the production orchestrator is
built in `api/main.py::build_orchestrator()`. Pass new tier-2 agents via
`Orchestrator(extra_agents=[...])` or they're unreachable at runtime (this
was a real Slice-4 CRITICAL). Tests construct the orchestrator themselves,
so a passing test suite won't catch a missing prod registration.

### Auth in tests

Tests that hit auth-guarded routes need the `X-Dev-User-Id: test-user` header
(or a mock of `get_current_user`). The anonymous fallback (`"anon"`) is the
default when neither Firebase JWT nor the dev header is present. The EventStore
and NotebookStore partition by `user_id`, so tests should use a deterministic
test user ID to avoid cross-test interference.

## 8. Where new components / agents / retrievers live

Spec in `docs/project_file_structure.md`. Repeatable recipes in
`.claude/skills/*/SKILL.md` — load the matching skill before adding the
second of anything:

- New GenUI component → `genui-component` skill
- New agent → `new-agent` skill
- New retriever → `new-retriever` skill
- Anything that crosses the wire → `schema-first-change` skill

## 9. When you're stuck

1. **Re-read CLAUDE.md.** Most ambiguity resolves there.
2. **Search `.claude/memory/decisions.md`** for prior context.
3. **Check the failure mode.** A hook blocked? Read its stderr — but
   remember the path-spaces bug makes the *Edit/Write* hooks crash
   spuriously (that's not your code failing a check; that's the bug).
4. **Surface the conflict to the user.** Quote both sides. Per CLAUDE.md:
   *"If two docs disagree, stop and ask."*

## 10. The end state

When P1 is done, this codebase will have:

- 15+ agents across four tiers (**done: 17 ✅**)
- 24-component GenUI catalog (**now: 11 of 24**)
- ≥3 demonstrated modes + 2 more for show (**done: 5 wired, FR-UI-06 ✅**)
- A learning module with spaced repetition (**done: SM-2 ✅, FR-LRN-02 ✅**)
- Firebase auth + Firestore persistence (**auth done ✅; Firestore seam ready**)
- A 20-question hybrid-vs-flat benchmark (**harness done ✅; run needed**)
- A 10–15 participant user study with SUS ≥ 70 (**infrastructure done ✅; conduct needed**)
- An FYP 2 report (**author task**)

Ten slices in. The remaining grade-weight concentrates in the benchmark run
(R-02) and user study conduct (R-03) — both author tasks now that the
infrastructure is complete. Write good ADRs for any further code slices so
the next agent in the chain can pick up cleanly.
