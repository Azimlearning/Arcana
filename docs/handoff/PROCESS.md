# Arcana — How We Build (slice-by-slice mechanism)

> The thing to learn ONCE then apply. Read this top to bottom before
> writing any code on this branch. Companion to [`CLAUDE.md`](../../CLAUDE.md)
> (operating brief — also load it; it's shorter), [`SETUP.md`](SETUP.md)
> (how to verify your inherited state), and [`CONTEXT.md`](CONTEXT.md)
> (what's already shipped).

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
  of work. It has a stated goal (e.g. "Agent maturity") and a closing
  ADR that records what was deferred.
- A **chunk** is a single logical unit within a slice — usually 1 file
  + 1 test file + ~30 minutes of focused work. Each chunk ends with all
  gates green and (when meaningful) a code-review pass.

The repo has shipped two slices so far:
- **Slice 0** = P0 walking skeleton, 10 chunks (one per subsystem).
- **Slice 1** = Agent maturity, 5 chunks (LangGraph, extraction,
  GraphRetriever, Fact Checker, Memory Agent).

Slice 2 is sketched in CONTEXT.md but not yet planned in detail.

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

### The five gates that must be green

| Gate | Command | What it catches |
|---|---|---|
| ruff | `uv run ruff check api/ eval/` | Style, dead imports, simple bugs |
| pyright | `uv run --with pyright pyright api/ eval/` | Type errors |
| pytest | `uv run pytest -q --tb=short -p no:cacheprovider` | Behaviour |
| codegen | `corepack pnpm --filter @arcana/schema codegen:check` | Schema drift (TS↔Pydantic) |
| web | `corepack pnpm --filter @arcana/web typecheck && ... test` | Frontend types + logic |

**Run gates in foreground, one at a time, with `-p no:cacheprovider` on
pytest.** Background pytest runs from the harness queue and silently
stall on Windows. The CLI is the source of truth — trust it over IDE
hints (the IDE often shows diagnostics from intermediate edit snapshots
that don't match the current file).

### Code review subagent

After every meaningful diff, invoke the project's code-reviewer subagent.
In Claude Code that's:

```
Use the code-reviewer subagent on the changes since HEAD.
```

The subagent enforces the eight invariants and the architectural rules
in `.claude/rules/*.md`. It produces a CRITICAL / WARNING / SUGGESTION
report with file:line references. **Fix every CRITICAL before
proceeding**; weigh WARNINGs; defer SUGGESTIONs into the slice's
follow-up list.

If the project's custom subagent isn't available, invoke
`general-purpose` with the `.claude/agents/code-reviewer.md` content as
its operating brief — same outcome.

## 4. The per-slice loop

A slice is opened by:

1. **Plan the slice in chat.** Present the chunks, the dependency
   order, the in/out-of-scope list, and any decisions you want the user
   to make. Wait for "go" on chunk 1. Once in rhythm, batch is allowed.
2. **Preflight.** Two things, always:
   - Tick the actually-done boxes in `docs/checklist.md` for the
     previous slice. Be honest about what was deferred — write
     `(→ slice N)` next to each deferral.
   - Log a slice-scope ADR in `.claude/memory/decisions.md` recording
     the scope decision, what dependencies forced the chunk order, and
     any new constraints.

A slice is closed by:

1. **Final code-review pass** on the full slice diff.
2. **Apply CRITICAL + worthwhile WARNING fixes.**
3. **Write the closing ADR** — `### YYYY-MM-DD — Slice N complete`. List
   what shipped, what's deferred, what's the next slice's starting
   point.
4. **Commit on `ExDev`** with a message ending with the requirement IDs
   it closes:

   ```
   feat(slice-N): <name> — <highlights>

   Refs: FR-AGT-04, FR-AGT-09, FR-KG-01, FR-ING-06, ...
   ```

   Include `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
   per the system prompt's git protocol.

## 5. The eight invariants & how they're enforced

PRD §11A.3 is the authoritative list. Paraphrased:

1. **Ground before generating** — every claim has retrieval evidence.
2. **UI is data, never code** — agents emit typed `UIBlock`, never HTML/text.
3. **Only the UI Agent picks components** — others produce data.
4. **Append to shared state** — never overwrite arbitrarily.
5. **Composability only via `route_to_agent`** — no direct agent imports.
6. **Always terminate at the UI Agent** — including failure paths.
7. **Storage behind abstractions** — `GraphStore`/`VectorStore`/`DocStore` ABCs only.
8. **No secret literals** — config via `Settings`, secrets via env.

How each is enforced:

| Invariant | Mechanism |
|---|---|
| #1 | Tests + code review |
| #2 | `api/genui/validate.py` fail-closes before SSE |
| #3 | `web/components/genui/registry.tsx` is the single dispatch; renderer never `switch`es on type |
| #4 | LangGraph reducers (`Annotated[..., add]`) |
| #5 | `.claude/hooks/check_imports.py` AST-parses every Python write; blocks agent→agent imports |
| #6 | `Orchestrator.invoke_graph` + SSE error-frame terminator |
| #7 | `.claude/hooks/check_imports.py` blocks concrete-store imports from agents |
| #8 | `.claude/hooks/check_secrets.py` regex-scans every write |

Hooks are mechanical; reviewer is judgement. Trust both.

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
marker. Don't backfill into older entries; never delete.

Two specific times to write an ADR:

- **You hit an open question (PRD §25 Q-03..Q-10).** Mark `ASSUMED:` and
  proceed.
- **You deviate from a spec doc.** Quote both sides, justify the
  deviation, log it.

## 7. Common gotchas you'll hit

These have all bitten the previous agent. They're documented inline in
the relevant files but worth knowing up front.

### IDE diagnostics lag behind your edits

The harness occasionally shows "Import X unused" or "Could not find name
Y" diagnostics that reflect an intermediate file state from mid-edit.
The CLI gates (`ruff`, `pyright`) reflect actual state. If CLI is green
and the IDE complains, trust the CLI.

### Pytest in the background queues silently on Windows

If you fire two pytest commands back-to-back, the second often stays at
0 bytes of output for the rest of the session. Run pytest **synchronously
in foreground**, one at a time, with `-p no:cacheprovider`. The full
suite finishes in ~2 seconds.

### `pnpm` isn't on PATH in child shells

The host shell calls pnpm via corepack. Child shells (npm scripts)
don't inherit corepack's shim. **Use `corepack pnpm` everywhere**, or
configure your npm scripts to not call pnpm recursively.

### CRLF/LF warnings on `git add`

Windows checkout converts LF → CRLF. `git add` warns. Harmless; once a
file is in the index, Git normalizes.

### Edit tool cache invalidation

When you do many sequential `Edit` calls on the same file, the harness
sometimes rejects later edits with "File has not been read yet" because
an autoformatter / linter modified the file between edits. Re-read the
file before re-applying.

### LangGraph + Pydantic state

LangGraph 0.2+ supports Pydantic BaseModel state. Reducers via
`Annotated[..., reducer_fn]` on fields. Mutation within a single node
call IS preserved (Python aliasing); mutation ACROSS nodes is NOT
(langgraph calls `model_copy` between steps). The `make_node` wrapper
in `api/agents/graph.py` snapshots list lengths and returns only deltas
so the `add` reducer doesn't double-count.

### `make_node` only emits agent_results for the current agent

If an agent mutates `state.agent_results[OTHER_NAME]`, the change is
LOST across the node boundary (the wrapper only returns
`{agent.name: result}`). Currently no agent does this; if you ever
need it, return both entries explicitly or refactor the wrapper.

## 8. Where new components / agents / retrievers live

The spec is in `docs/project_file_structure.md`. The repeatable recipes
are in `.claude/skills/*/SKILL.md`. Load the matching skill before
adding the second of anything:

- New GenUI component → `genui-component` skill
- New agent → `new-agent` skill
- New retriever → `new-retriever` skill
- Anything that crosses the wire → `schema-first-change` skill

The skills encode the exact step order. Following them keeps the wire
contract and dependency direction intact automatically.

## 9. When you're stuck

Order of operations:

1. **Re-read CLAUDE.md.** Most ambiguity resolves there.
2. **Search `.claude/memory/decisions.md`** for prior context on the
   thing you're about to do. Someone may have ADR'd it.
3. **Check the failure mode.** Did a hook block? Read its stderr; it
   tells you exactly which invariant tripped.
4. **Surface the conflict to the user.** Quote both sides. Don't pick
   silently. Per CLAUDE.md: *"If two docs disagree, stop and ask."*

## 10. The end state

When P1 is done, this codebase will have:

- 15+ agents across four tiers
- 24-component GenUI catalog
- ≥3 demonstrated modes (Research, Writing, Study) + 2 more for show
- A learning module with spaced repetition
- Firebase auth + Firestore persistence
- A 20-question hybrid-vs-flat benchmark with stat-sig result
- A 10–15 participant user study with SUS ≥ 70
- An FYP 2 report documenting all of the above

You're about 1/14 of the way there. Slow down, write good ADRs, and the
next agent in the chain will thank you.
