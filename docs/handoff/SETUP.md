# Arcana — Setup Guide (post-Slice-1)

> This guide takes a fresh checkout of branch `ExDev` to **all gates green**
> in ~15 minutes. If anything here doesn't match what you see in the repo,
> the repo wins — open an issue / ADR.

## 1. What you're walking into

This branch contains:

- **P0 walking skeleton** (commit `267b035`) — end-to-end vertical: PDF →
  hybrid retrieval → research → UI Agent → SSE → Next.js frontend with a
  registry-based GenUI catalog.
- **Slice 1 — agent maturity** (the most recent commit) — LangGraph
  `StateGraph`, entity extraction → graph build, real GraphRetriever,
  Fact Checker (FR-AGT-09), Memory Agent with start-of-turn read +
  end-of-turn writeback.

Headline state at the end of slice 1:

| Gate | Result |
|---|---|
| `uv run ruff check api/ eval/` | All checks passed |
| `uv run --with pyright pyright api/ eval/` | 0 errors, 0 warnings |
| `uv run pytest -q api/` | **263 passed** |
| `corepack pnpm --filter @arcana/schema codegen:check` | OK |
| `corepack pnpm --filter @arcana/web typecheck` | 0 errors |
| `corepack pnpm --filter @arcana/web test` | 7 passed |

## 2. Prerequisites

- **Node 20+** with `corepack` (ships with Node). Don't install pnpm
  globally; corepack reads `packageManager` in `package.json` and pins
  pnpm 9.12.0 per-project.
- **Python 3.11 or 3.12** — the project's `pyproject.toml` constrains
  `>=3.11,<3.13`.
- **uv** — `pip install uv` (or use the official installer). Tested
  against uv 0.11+.
- **Git for Windows / WSL / macOS / Linux** — any platform that ships
  GNU Make. Windows-native cmd.exe is partly supported but `make clean`
  needs Git Bash / WSL / MSYS (cross-platform path runs through Python).
- **API accounts** for end-to-end ingest + chat:
  [Anthropic](https://console.anthropic.com),
  [OpenAI](https://platform.openai.com),
  [Pinecone](https://app.pinecone.io). Tests use respx/stubs and don't
  need real keys.

## 3. One-time setup

```bash
# 1. Get the branch
git clone https://github.com/Azimlearning/Arcana.git
cd Arcana
git checkout ExDev

# 2. Install workspace + Python deps
corepack pnpm install        # web + schema workspace packages
uv sync --dev                # Python runtime + dev deps

# 3. Build the schema package (TS source → compiled ESM + Pydantic codegen)
corepack pnpm --filter @arcana/schema build

# 4. Fill in your API keys (skip if you only need to verify the gates)
cp infra/env/local.env.example api/.env
cp web/.env.local.example      web/.env.local
# Edit api/.env: ANTHROPIC_API_KEY, OPENAI_API_KEY, PINECONE_API_KEY,
#                PINECONE_INDEX, PINECONE_ENVIRONMENT
```

Pinecone setup detail: create a **serverless index named `arcana`** with
**dimension 3072** and **metric cosine**. The dimension must match what
OpenAI's `text-embedding-3-large` emits (R-02 — benchmark fairness).

## 4. Verify the inherited state

Run all six gates. Order doesn't matter; they're independent.

```bash
# Backend
uv run ruff check api/ eval/                                # → All checks passed
uv run --with pyright pyright api/ eval/                    # → 0 errors
uv run pytest -q api/                                       # → 263 passed (slice 1)

# Schema drift
corepack pnpm --filter @arcana/schema codegen:check         # → codegen:check OK

# Frontend
corepack pnpm --filter @arcana/web typecheck                # → no output (clean)
corepack pnpm --filter @arcana/web test                     # → 7 passed
corepack pnpm --filter @arcana/web build                    # → optional; ~92 kB First Load JS
```

If any of these fail, **stop and diagnose** before writing new code.
The slice 1 commit is the contract.

## 5. Run the slice end-to-end (optional — needs API keys)

```bash
# Drop a PDF into eval/corpus/
make ingest-demo            # ingests every *.pdf into Pinecone + chunk store + graph

# Two terminals:
make up-api                 # uvicorn on :8000 — orchestrator wired with real providers
make up-web                 # Next on :3000
```

Open <http://localhost:3000> — it redirects to `/notebooks/demo` and
shows the 3-panel shell. Ask a question; you should see a streaming
`CitedSummary` block with skeleton → hydrated state transitions, with
clickable citations. The second turn in the same notebook should
reference the first turn's history (Memory Agent in action).

## 6. Known gotchas

- **Windows + Git: CRLF/LF warnings.** Harmless. `core.autocrlf` is on
  by default; the repo's line endings normalize on first checkout.
- **`VIRTUAL_ENV` warning from uv.** If your shell has `VIRTUAL_ENV` set
  to a different Python venv, uv warns and prefers the project's `.venv`
  anyway. Unset it (`Remove-Item Env:VIRTUAL_ENV` in PowerShell, `unset
  VIRTUAL_ENV` in bash) to silence.
- **`pnpm` not on PATH inside child shells.** Use `corepack pnpm ...`
  everywhere. The Makefile already does this.
- **Next.js fonts fetch from Google Fonts at build time.** First `next
  build` on a fresh CI runner may retry. Not slice-blocking; if it bites
  consistently, vendor `.woff2` files via `next/font/local`.
- **Stale IDE diagnostics.** The harness sometimes reports
  "Import X unused" or "Could not find name Y" on intermediate edit
  snapshots. **Trust the CLI runs** (`ruff`, `pyright`) over IDE hints.
- **`pytest` background queueing on Windows.** If you queue several
  pytest runs in parallel via the harness, output files may stay empty.
  Run pytest **one at a time, foreground**, with `--tb=short -p
  no:cacheprovider`. The slice's full suite completes in ~2s.
- **`make clean` is POSIX-flavoured.** Runs through `uv run python -c
  "..."` so it works on Windows via Git Bash, WSL, MSYS, cmd, and
  PowerShell. Plain Windows-find won't help.

## 7. What's next

You're picking up **at the boundary between Slice 1 (done) and Slice 2
(GenUI catalog breadth)**. Open these in order:

1. [`docs/handoff/CONTEXT.md`](CONTEXT.md) — narrative of what
   shipped, what was deferred, what's open.
2. [`docs/handoff/PROCESS.md`](PROCESS.md) — how this codebase is
   built (slices, chunks, ADRs, the eight invariants, code-review
   pattern).
3. [`docs/handoff/HANDOFF_PROMPT.md`](HANDOFF_PROMPT.md) — the prompt
   to give your new coding agent.
4. [`CLAUDE.md`](../../CLAUDE.md) — the operating brief that's been
   driving everything.
5. [`docs/checklist.md`](../checklist.md) §1 (P1) — the work that
   remains.
6. [`.claude/memory/decisions.md`](../../.claude/memory/decisions.md) —
   every assumption / deviation recorded by the previous agent.

The next slice's headline deliverable is **GenUI catalog breadth**:
adding `LiteratureMatrix`, `ContradictionAlert`, `GapAnalysis`,
`InsightCard`, `KnowledgeGraphView` — and teaching the UI Agent to
pick components based on intent/mode. The plan is sketched in CONTEXT.md.
