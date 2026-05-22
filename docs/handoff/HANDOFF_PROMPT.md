# Handoff Prompt — paste this into your next coding agent

> Copy everything between the `---` lines and paste it as the first
> message to your new coding agent (Claude, Cursor, Aider, whichever).
> If the agent supports a system prompt, paste it there instead. The
> prompt is self-contained — it tells the agent which files to read,
> in what order, and what to do before touching code.

---

You are picking up a Final Year Project named **Arcana** — a
graph-native multi-agent research and learning platform. The prior
agent shipped two slices (P0 walking skeleton + Slice 1 agent maturity)
and just handed off to you. Your job is to continue building, one slice
at a time, to the same quality bar.

**Do not write any code until you have read the following files, in
this exact order, and summarised back to me what you understand.**

## Step 1 — Read these files

1. `CLAUDE.md` — the operating brief for the whole project (short).
2. `docs/handoff/SETUP.md` — how to get from `git checkout ExDev` to all gates green.
3. `docs/handoff/CONTEXT.md` — what shipped, what's deferred, where you're picking up.
4. `docs/handoff/PROCESS.md` — how this codebase is built (slice-by-slice, the eight invariants, ADR-keeping, the gates, the code-reviewer subagent).
5. `.claude/memory/decisions.md` — every ADR. Newest first.
6. `docs/arcana_prd.md` §§1–8, §11, §11A — the canonical spec (read §11A in full; it's the mental model).
7. `docs/project_file_structure.md` — repo layout.
8. `docs/checklist.md` — phased build plan. Phase 0 is closed; Phase 1 is your work.
9. `docs/uiux_plan.md` §§1–6 — design system tokens, three-panel shell, 24-component catalog, the four states.

Then read these only when you actually need them:

- `docs/arcana_prd.md` §12 — when implementing a specific agent
- `docs/arcana_prd.md` §13, §16 — when adding a GenUI component
- `docs/env_generation_guide.md` — when adding a new env var
- `.claude/rules/*.md` — auto-load when working in matching paths
- `.claude/skills/*/SKILL.md` — recipes you load on demand

## Step 2 — Verify your inherited state

Before any code, run all the gates and confirm green:

```bash
uv run ruff check api/ eval/
uv run --with pyright pyright api/ eval/
uv run pytest -q api/                # expect 263 passed
corepack pnpm --filter @arcana/schema codegen:check
corepack pnpm --filter @arcana/web typecheck
corepack pnpm --filter @arcana/web test    # expect 7 passed
```

If anything is red, **stop and diagnose**. Don't write new code on top
of a broken inheritance. The previous agent left every gate green at
commit-time; if something flipped, it's environment or platform,
not the code.

## Step 3 — Summarise back to me

Reply with 8–12 bullet points covering:

1. The mental model in your own words (the request lifecycle from PRD §11A.2).
2. The eight invariants and how each is enforced (hook vs reviewer vs test).
3. The slice-by-slice mechanism (slices, chunks, per-chunk loop, per-slice loop).
4. What ships in Slice 0 (P0 walking skeleton) — major modules, no exhaustive list.
5. What ships in Slice 1 (agent maturity) — the five chunks.
6. Active deferrals you noticed and where they're recorded.
7. The five non-blocking warnings from the Slice 1 code review (see CONTEXT.md).
8. Your understanding of where the next slice picks up.
9. Any contradictions or ambiguities across the docs that I should resolve before you start.
10. The first three files you intend to create or modify in the next slice, and why.

**Do not write any code in your first response.** I need to confirm the
picture before you build. Once I'm happy with your summary, I'll say
"go" and you start the next slice.

## Step 4 — Slice planning

When I say "go", the next slice (Slice 2 — GenUI catalog breadth) is
the natural starting point. Its sketch is in `CONTEXT.md` §"The next
slice's outline". Before you write code:

1. **Preflight** — tick the actually-done items in `docs/checklist.md`
   Phase 1 that Slice 1 closed (none yet — Phase 1 hasn't started).
   Log a new slice-scope ADR in `.claude/memory/decisions.md`.
2. **Plan the chunks** — present them to me in chat, in dependency
   order, with in/out-of-scope per chunk. Wait for "go" on chunk 1.
3. **Per chunk** — follow the loop in `docs/handoff/PROCESS.md` §3
   (plan → write → gates → review → fix → close).
4. **Per slice close** — final code-review pass, closing ADR, single
   commit on `ExDev` referencing the closed FR/NFR/R/Q IDs.

## Step 5 — The operating contract (durable rules)

These hold for the entire FYP build, not just one slice:

- **Schema first.** Every type that crosses the wire is defined in
  `packages/schema/` BEFORE either the agent that emits it or the
  component that renders it. Run codegen; commit the generated Python.
- **Use the existing subagents.** `code-reviewer` after every meaningful
  diff. `qa-runner` (not yet wired in this repo, but referenced in
  `CLAUDE.md`) before declaring DONE.
- **Mark assumptions explicitly.** When an open question forces a path,
  write the ADR with `ASSUMED:` status.
- **Never build the second of anything until the first is green
  end-to-end.** If you catch yourself doing it, stop and check with me.
- **Commits reference IDs.** `feat(retrieval): RRF fusion — closes
  FR-RET-04`. Include `Co-Authored-By: Claude Opus 4.7
  <noreply@anthropic.com>`.
- **Don't push without my say-so.** Branch operations are fine; remote
  pushes need explicit permission.
- **Stale IDE diagnostics aren't real.** Run the CLI gates yourself.
- **Run pytest one at a time, foreground, `-p no:cacheprovider`** —
  parallel pytest queues silently stall on Windows.

That's everything. Read the files, run the gates, summarise back. I'll
take it from there.

---

## Optional — what the previous agent would do differently

If you're curious what context the previous agent (Claude Opus 4.7,
running in Claude Code) ran into:

- The Windows VM occasionally queued background bash commands without
  ever writing their output, which forced foreground-only test runs.
- The IDE diagnostics surfaced through the harness lagged by 1–2 edit
  cycles, producing scary-looking "Import unused" / "name not found"
  messages that were always false alarms. The CLI runs were the
  source of truth.
- The user requested specific architectural choices that deviated from
  the original PRD/spec (e.g. `api/embeddings/` as its own peer module;
  Pinecone via raw REST instead of the SDK). Those are ADR'd. Don't
  un-do them without checking.
- The slice-1 code-reviewer raised three warnings that were fixed
  before commit (error-block memory pollution, missing multi-turn
  test, route_after_orchestrator brittleness). Read the slice-1 closing
  ADR for the rationale.

Good luck.
