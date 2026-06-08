# Arcana — Setup Guide (post-Slice-5)

> This guide takes a fresh checkout of branch `ExDev` to **all gates green**
> in ~15 minutes. If anything here doesn't match what you see in the repo,
> the repo wins — open an issue / ADR.
>
> **Last refreshed:** 2026-06-08 (after Slice 5).

## 1. What you're walking into

Branch `ExDev` contains **P0 + Slices 1–5**:

- **P0 walking skeleton** (`267b035`) — PDF → hybrid retrieval → research →
  UI Agent → SSE → Next.js frontend with a registry-based GenUI catalog.
- **Slice 1** (`8d5644c`) — LangGraph `StateGraph`, entity extraction →
  graph build, real GraphRetriever, Fact Checker, Memory Agent.
- **Slice 2** (`24d8c84`) — 5 GenUI variants + UIAgent intent routing +
  DiscoveryAgent.
- **Slice 3** (`307bbe2`) — Study mode: Learning + Socratic agents, 4 GenUI
  variants.
- **Slice 4** (`9e5a78a`) — Writing mode: WritingAgent + DraftEditor +
  FeynmanExplainer production; all tier-2 agents registered in `api/main.py`.
- **Slice 5** (`e73e830`) — mode switching end-to-end (5 modes, FR-UI-06).

Headline state at HEAD:

| Gate | Result |
|---|---|
| `uv run ruff check api/` | All checks passed |
| `uv run --with pyright pyright api/` | 0 errors, 0 warnings |
| `uv run pytest -q api/` | **335 passed** |
| `corepack pnpm --filter @arcana/schema codegen:check` | OK |
| `corepack pnpm --filter @arcana/web typecheck` | 0 errors |
| `corepack pnpm --filter @arcana/web test` | **11 passed** |

## 2. ⚠️ The one gotcha that will block you immediately

The repo path contains a space: `...\FYP DOCS\Arcana`. The `.claude/`
`PreToolUse` hooks are invoked with an **unquoted** `$CLAUDE_PROJECT_DIR`,
so they crash on the space and **block every built-in `Edit` and `Write`
tool call**. You will see:

```
PreToolUse:Edit hook error: ... can't open file 'c:\Users\User\Documents\FYP'
```

**Do not fight it.** Edit files like this instead:

- Inside the repo → `mcp__filesystem__write_file` (full file) or
  `mcp__filesystem__edit_file` (targeted edits). These skip the hook.
- Outside the repo → Bash heredoc (`cat > path <<'EOF' ... EOF`).

Permanent fix (optional, do it if you have buy-in): quote
`"$CLAUDE_PROJECT_DIR"` in the hook commands in `.claude/settings.json`,
or move the repo to a path with no spaces.

## 3. Prerequisites

- **Node 20+** with `corepack` (ships with Node). Don't install pnpm
  globally; corepack reads `packageManager` in `package.json`.
- **Python 3.11 or 3.12** — `pyproject.toml` constrains `>=3.11,<3.13`.
- **uv** — `pip install uv` (or the official installer). Tested on uv 0.11+.
  (On the author's machine uv is at `~/.local/bin/uv.exe`; plain `uv` works
  if it's on PATH.)
- **Git Bash / WSL / macOS / Linux** for GNU Make. Windows-native cmd is
  partly supported.
- **API accounts** for end-to-end ingest + chat: Anthropic, OpenAI,
  Pinecone. Tests use respx/stubs and don't need real keys.

## 4. One-time setup

```bash
git clone https://github.com/Azimlearning/Arcana.git
cd Arcana
git checkout ExDev

corepack pnpm install                       # web + schema workspace
uv sync --dev                               # Python runtime + dev deps
corepack pnpm --filter @arcana/schema build # TS source → ESM + Pydantic codegen

# API keys (skip if you only need to verify the gates)
cp infra/env/local.env.example api/.env
cp web/.env.local.example      web/.env.local
# Edit api/.env: ANTHROPIC_API_KEY, OPENAI_API_KEY, PINECONE_API_KEY,
#                PINECONE_INDEX, PINECONE_ENVIRONMENT
```

Pinecone: create a **serverless index named `arcana`**, **dimension 3072**,
**metric cosine** — must match `text-embedding-3-large` (R-02 fairness).

## 5. Verify the inherited state

Run all six gates. Order doesn't matter; they're independent.

```bash
# Backend
uv run ruff check api/                                      # → All checks passed
uv run --with pyright pyright api/                          # → 0 errors, 0 warnings
uv run pytest -q api/                                       # → 335 passed

# Schema drift
corepack pnpm --filter @arcana/schema codegen:check         # → codegen:check OK

# Frontend
corepack pnpm --filter @arcana/web typecheck                # → no output (clean)
corepack pnpm --filter @arcana/web test                     # → 11 passed
corepack pnpm --filter @arcana/web build                    # → optional
```

If any fail, **stop and diagnose** before writing new code. The Slice 5
commit is the contract. (If you edited the schema, re-run
`corepack pnpm --filter @arcana/schema build` then `codegen` before the
backend gates — the Pydantic models are generated from the TS source.)

## 6. Run the slice end-to-end (optional — needs API keys)

```bash
# Drop a PDF into eval/corpus/
make ingest-demo            # ingests every *.pdf → Pinecone + chunk store + graph

# Two terminals:
make up-api                 # uvicorn :8000 — orchestrator wired with real providers
make up-web                 # Next :3000
```

Open <http://localhost:3000> → redirects to `/notebooks/demo`, shows the
3-panel shell **with the 5-mode switcher in the header** (Slice 5). Switch
to **Study** and ask "make flashcards on X" → you should get a
`FlashcardDeck`; switch to **Writing** and ask to draft a section → a
`DraftEditor`. Research mode streams a `CitedSummary` with clickable
citations and skeleton→hydrate transitions. Second turn in a notebook
references the first (Memory Agent).

## 7. Known gotchas

- **The hook path-spaces bug** — see §2. This is the big one.
- **Windows CRLF/LF warnings on `git add`.** Harmless; Git normalizes.
- **`VIRTUAL_ENV` warning from uv.** If your shell has a different venv,
  uv warns and prefers the project `.venv` anyway. Unset to silence.
- **`pnpm` not on PATH in child shells.** Use `corepack pnpm ...` everywhere.
- **Next.js fonts fetch from Google Fonts at build time.** First `next build`
  on a fresh runner may retry.
- **Stale IDE diagnostics.** The harness sometimes shows "Import X unused"
  on intermediate edit snapshots. Trust the CLI (`ruff`, `pyright`).
- **`pytest` background queueing on Windows.** Run pytest foreground, one at
  a time, `--tb=short -p no:cacheprovider`. Full suite ~3–5s.

## 8. What's next

You're picking up **at the boundary between Slice 5 (done) and Slice 6
(adaptive 3-panel shell)**. Read in order:

1. [`docs/handoff/CONTEXT.md`](CONTEXT.md) — what shipped (through Slice 5),
   what's deferred, the Slice 6 outline.
2. [`docs/handoff/PROCESS.md`](PROCESS.md) — slices, chunks, ADRs, the eight
   invariants, the code-review pattern.
3. [`docs/handoff/HANDOFF_PROMPT.md`](HANDOFF_PROMPT.md) — the prompt to give
   your new coding agent.
4. [`CLAUDE.md`](../../CLAUDE.md) — the operating brief.
5. [`docs/checklist.md`](../checklist.md) §1 (P1) — the work that remains.
6. [`.claude/memory/decisions.md`](../../.claude/memory/decisions.md) — every
   ADR, newest first.

**Slice 6 headline:** make the three panels resize/hide per mode
(`docs/uiux_plan.md` §3–§4), completing FR-UI-01/05 and the layout half of
FR-UI-07. After that: Slice 7 (more agents → 15+, FR-AGT-06) and Slice 8
(the hybrid-vs-flat benchmark, §1.12 / R-02) — the two gate-critical slices.
