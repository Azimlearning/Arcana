---
name: resume
description: Pick up Arcana development exactly where the last session left off. Reads git state, the handoff docs, the changelog/decisions log, and the batched checklist, then prints a tight "where we are / next batch / ready to go" briefing. Trigger: /resume
---

# Resume — session warm-start

Goal: in one pass, reconstruct the project's live state and hand the operator a short, accurate briefing plus the single most actionable next step. No code changes. No long file dumps — synthesise, don't paste.

## Order of authority (do not skip)

The five spec docs are source of truth (see `CLAUDE.md`). This skill *reads* them; it never resolves a doc conflict silently — if two sources disagree, surface it.

## Step 1 — Gather live state (run these, in parallel where possible)

```bash
git -C . rev-parse --abbrev-ref HEAD          # current branch
git -C . log --oneline -8                       # recent commits
git -C . status --short                         # uncommitted work
```

Then read, in this order (skim, extract the delta — not every line):

1. `docs/handoff/CONTEXT.md` — what the project is and the inherited state.
2. `docs/handoff/PROCESS.md` — the slice/batch build loop and invariant enforcement.
3. `.claude/memory/CHANGELOG.md` — the most recent sessions, to see what shipped since CONTEXT.md was last refreshed.
4. `.claude/memory/DECISIONS.md` — ADRs and any `ASSUMED` entries still open.
5. `.claude/memory/preflight.md` — gotchas to check before writing code.
6. `docs/checklist.md` — the **Phase 1 — Finish Plan (batched)** block near the end of Phase 1. This is the authoritative "what's next". Find the first batch (B1 to B5) with unchecked items.
7. The auto-memory index at `~/.claude/projects/<slug>/memory/MEMORY.md` if present (project_state.md especially).

## Step 2 — Reconcile

Cross-check three things and flag any mismatch rather than trusting one source:

- **Branch** from git vs. the branch named in CONTEXT.md.
- **Checklist boxes** vs. what the recent commits actually shipped (a box may lag a commit, or vice-versa).
- **Open gates** — the Phase 1 release gate (`docs/checklist.md`) and any open `Q-*` / `ASSUMED` ADRs in `DECISIONS.md`.

## Step 3 — Known traps to re-verify (don't assume from memory — check current files)

- **Write-hook bug (fixed 2026-06-22):** `.claude/settings.json` PreToolUse hooks used to pass unquoted `$CLAUDE_PROJECT_DIR`; the repo path has a space, so `Write`/`Edit` were blocked. Now quoted — native `Write`/`Edit` should work. Re-check it's still quoted: `grep -n CLAUDE_PROJECT_DIR .claude/settings.json` — if you see an unquoted occurrence, fall back to the filesystem MCP tools or a Bash heredoc until it's re-fixed.
- **Tier-2 agent registration:** new agents must be passed to `Orchestrator(extra_agents=[...])` in `api/main.py`, not only added to `api/agents/graph.py`.
- **Wire types:** import from `packages/schema` (codegen'd Python) — never re-declare a payload class in Python (R-10).

## Step 4 — Brief the operator (keep it to ~12 lines)

Print exactly this shape, filled from what you found:

```
ARCANA — resume briefing (<date>)
Branch:    <branch>  (<clean | N files dirty>)
Last ship: <newest commit subject>
Phase:     1 — <one-line gate status: which Must FRs / gates remain>

Next batch: <B#> — <name>
  Items: <FR ids + short labels still unchecked in that batch>
  Test:  <the single QA/test pass that closes the batch>

Open: <any ASSUMED / Q-* / doc conflict, or "none">
Traps verified: <write-hook status; anything notable>

Ready: <the one concrete first action to take now>
```

## Constraints

- Read-only. This skill plans and reports; it does not edit code or docs.
- If the checklist's batched finish plan is missing, say so and fall back to the first unchecked Phase 1 item top-to-bottom.
- Prefer the batched plan's grouping: a batch is "done" only when its single test pass is green (`qa-runner` subagent) — that's the whole point of batching (one QA pass per batch, not per item).
- End by asking whether to start the next batch, unless the operator already said go.
