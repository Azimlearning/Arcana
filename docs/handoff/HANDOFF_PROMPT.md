# Handoff Prompt — paste this into your next coding agent

> Copy everything between the `---` lines and paste it as the first
> message to your new coding agent (Claude, Cursor, Aider, whichever).
> If the agent supports a system prompt, paste it there instead. The
> prompt is self-contained — it tells the agent which files to read,
> in what order, and what to do before touching code.
>
> **Last refreshed:** 2026-06-08 (after Slice 5).

---

You are picking up a Final Year Project named **Arcana** — a graph-native
multi-agent research and learning platform. The prior agent shipped six
slices (P0 walking skeleton + Slices 1–5) and just handed off to you. Your
job is to continue building, one slice at a time, to the same quality bar.

**Do not write any code until you have read the following files, in this
exact order, and summarised back to me what you understand.**

## Step 0 — The one thing that will block you immediately

This repo lives at a path **with a space in it** (`...\FYP DOCS\Arcana`).
The `.claude/` hooks pass `$CLAUDE_PROJECT_DIR` unquoted, so the
`PreToolUse` hook on `Edit`/`Write` crashes on the space and **blocks every
built-in `Edit` and `Write` call**. You'll see `can't open file
'...\FYP'`. Work around it:

- In-repo files → `mcp__filesystem__write_file` / `mcp__filesystem__edit_file`.
- Out-of-repo files → Bash heredocs (`cat > path <<'EOF' ... EOF`).

Because the secret/import hooks are what's broken, **you** must manually
honour the no-secret / no-upward-import invariants when you write via MCP;
the `code-reviewer` subagent is your backstop. Full detail: `SETUP.md` §2.

## Step 1 — Read these files

1. `CLAUDE.md` — the operating brief for the whole project (short).
2. `docs/handoff/SETUP.md` — how to get from `git checkout ExDev` to all gates green (+ the hook bug).
3. `docs/handoff/CONTEXT.md` — what shipped (through Slice 5), what's deferred, where you pick up.
4. `docs/handoff/PROCESS.md` — how this codebase is built (slices, chunks, the eight invariants, ADRs, the code-reviewer subagent, the gotchas).
5. `.claude/memory/decisions.md` — every ADR. Newest first.
6. `docs/arcana_prd.md` §§1–8, §11, §11A — the canonical spec (read §11A in full; it's the mental model).
7. `docs/project_file_structure.md` — repo layout.
8. `docs/checklist.md` — phased build plan. Phase 0 is closed; Phase 1 is your work (and is partly done — see the ticks).
9. `docs/uiux_plan.md` §§1–6 — design tokens, three-panel shell, the 24-component catalog, the four states. (For the next slice, also read §3 and §4 closely.)

Then read these only when you actually need them:

- `docs/arcana_prd.md` §12 — when implementing a specific agent
- `docs/arcana_prd.md` §13, §16 — when adding a GenUI component
- `docs/env_generation_guide.md` — when adding a new env var
- `.claude/rules/*.md` — the rules behind the invariants (load when working in matching paths)
- `.claude/skills/*/SKILL.md` — recipes you load on demand (genui-component, new-agent, new-retriever, schema-first-change)

## Step 2 — Verify your inherited state

Before any code, run all the gates and confirm green:

```bash
uv run ruff check api/
uv run --with pyright pyright api/
uv run pytest -q --tb=short -p no:cacheprovider api/   # expect 335 passed
corepack pnpm --filter @arcana/schema codegen:check
corepack pnpm --filter @arcana/web typecheck
corepack pnpm --filter @arcana/web test                 # expect 11 passed
```

If anything is red, **stop and diagnose**. Don't build on a broken
inheritance. Every gate was green at commit-time; if something flipped,
it's environment or platform, not the code. (If you changed the schema,
run `corepack pnpm --filter @arcana/schema build` + `... codegen` first —
the Pydantic models are generated from TS.)

## Step 3 — Summarise back to me

Reply with 8–12 bullets covering:

1. The mental model in your own words (the request lifecycle, PRD §11A.2).
2. The eight invariants and how each is enforced (hook vs reviewer vs test) — and note that the Edit/Write hooks are currently broken by the path-spaces bug, so some enforcement is manual + reviewer-backed.
3. The slice-by-slice mechanism (slices, chunks, per-chunk loop, per-slice loop).
4. What shipped across Slices 0–5 (the headline of each — no exhaustive lists).
5. The current inventory: 10 agents, 11/24 GenUI components, 5 modes wired (FR-UI-06).
6. Active deferrals you noticed and where they're recorded (CONTEXT.md "What's deferred" + decisions.md).
7. The two production-registration / schema-first traps (new tier-2 agents must be added to `api/main.py`; wire types live in `packages/schema` and are imported, never re-declared).
8. Your understanding of where the next slice (Slice 6 — adaptive 3-panel shell) picks up, per CONTEXT.md + uiux_plan §3–§4.
9. Any contradictions or ambiguities across the docs I should resolve before you start (e.g. `FR-WRT-01` is an assumed id not in the PRD).
10. The first three files you intend to create or modify in Slice 6, and why.

**Do not write any code in your first response.** I need to confirm the
picture before you build. Once I'm happy, I'll say "go".

## Step 4 — Slice planning

When I say "go", the next slice is **Slice 6 — adaptive 3-panel shell**
(FR-UI-01/05, and the layout half of FR-UI-07). Its outline is in
`CONTEXT.md` §"Next slice", grounded in `uiux_plan.md` §3–§4. Before code:

1. **Preflight** — tick the actually-done Phase-1 items in `docs/checklist.md`
   that prior slices closed (do not double-tick). Log a new slice-scope ADR
   in `.claude/memory/decisions.md`.
2. **Plan the chunks** — present them in chat, dependency order, in/out-of-scope
   per chunk. Flag the one scope decision Slice 6 needs: frontend mode→layout
   map now vs. UI-Agent-emitted layout over the wire (uiux §3 implies the
   agent ultimately decides; a frontend map is the pragmatic first cut). Wait
   for "go" on chunk 1.
3. **Per chunk** — follow the loop in `PROCESS.md` §3 (plan → write → gates →
   review → fix → close). Remember: write via MCP filesystem tools, not Edit/Write.
4. **Per slice close** — final code-review pass, closing ADR, a commit on
   `ExDev` referencing the closed FR/NFR/R/Q IDs + a separate checklist tick.

After Slice 6 the gate-critical work is **Slice 7** (more agents → 15+,
FR-AGT-06) and **Slice 8** (the hybrid-vs-flat eval benchmark, §1.12 / R-02).
Those carry most of the remaining grade-weight.

## Step 5 — The operating contract (durable rules)

- **Schema first.** Every type that crosses the wire is defined in
  `packages/schema/` BEFORE the agent that emits it or the component that
  renders it. Run codegen; commit the generated Python. Never re-declare a
  wire type in Python — import the codegen'd model.
- **Use the subagents.** `code-reviewer` after every meaningful diff;
  `qa-runner` / `schema-guardian` where relevant. Fix every CRITICAL.
- **Mark assumptions explicitly.** When an open question forces a path, write
  the ADR with `ASSUMED:` status.
- **Never build the second of anything until the first is green end-to-end.**
- **Register new tier-2 agents in `api/main.py`** (`Orchestrator(extra_agents=…)`),
  not just in `graph.py`, or they're dead in production.
- **Commits reference IDs** and end with `Co-Authored-By: Claude Opus 4.8
  <noreply@anthropic.com>` (use your own model's attribution).
- **Don't push without my say-so.** Local branch work is fine; remote pushes
  need explicit permission.
- **Stale IDE diagnostics aren't real.** Run the CLI gates yourself.
- **Run pytest one at a time, foreground, `-p no:cacheprovider`** — parallel
  pytest queues silently stall on Windows.

That's everything. Read the files, run the gates, summarise back. I'll take
it from there.

---

## Optional — what the previous agents ran into

- **The path-spaces hook bug** (above) is the single biggest time-sink if
  you don't know about it — you'll try `Edit`, get a cryptic
  `can't open file '...\FYP'`, and waste a turn. Go straight to the MCP
  filesystem tools.
- The Windows VM occasionally queued background bash commands without
  writing output — forced foreground-only test runs.
- IDE diagnostics through the harness lag 1–2 edit cycles, producing
  false "unused import" / "name not found" warnings. CLI runs are truth.
- The user has requested architectural choices that deviate from the
  original spec (e.g. `api/embeddings/` as its own peer module; Pinecone via
  raw REST not the SDK; `Orchestrator(extra_agents=…)`). All ADR'd. Don't
  undo them without checking.
- Slices 4 and 5 each surfaced a real CRITICAL in code review (tier-2 agents
  not registered in `main.py`; an inline `Literal` duplicating the schema
  `Mode`). Both fixed before commit. Read the closing ADRs for the rationale.

Good luck.
