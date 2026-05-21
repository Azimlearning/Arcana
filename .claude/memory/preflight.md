# Preflight — before Claude Code starts

> One-page gate. Run through it once before kicking off the first real build session. If any box is unchecked, fix it before going further — these are the things research shows separate "demo that works" from "project that ships."

## Repo + tooling

- [ ] Monorepo scaffolded per `docs/project_file_structure.md` (`api/`, `web/`, `packages/schema/`, `eval/`, `infra/`, `docs/`).
- [ ] All five spec docs present under `docs/` and named exactly: `arcana_prd.md`, `project_file_structure.md`, `uiux_plan.md`, `checklist.md`, `env_generation_guide.md`.
- [ ] `CLAUDE.md` at repo root pointing at the five docs.
- [ ] `.claude/` operating layer present (this folder): `rules/`, `agents/`, `skills/`, `hooks/`, `memory/`, `settings.json`.
- [ ] Hook scripts executable (`chmod +x .claude/hooks/*.py`).
- [ ] `git init`, `.gitignore` excludes `.env`, `.env.local`, `node_modules/`, `.next/`, `__pycache__/`, `*.pyc`, any `service-account*.json`.
- [ ] `pnpm-lock.yaml` and `uv.lock` (or equivalent) generated and committed — reproducibility is a defence requirement.

## Config

- [ ] `infra/env/local.env.example` exists with every variable from `env_generation_guide.md` §1 documented and **empty**.
- [ ] `web/.env.local.example` exists with every `NEXT_PUBLIC_*` documented and empty.
- [ ] `api/.env` and `web/.env.local` populated locally (not committed) with the three minimum P0 keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `PINECONE_API_KEY` + index/region.
- [ ] Pinecone index dimension is **3072** with cosine metric. (Verify in console; mismatched dim wastes hours.)

## Quality harness

- [ ] Python tooling chosen and pinned: **uv** + **ruff** + **pyright** (or mypy). Configs in `pyproject.toml`.
- [ ] `pytest` + `pytest-asyncio` + `respx` (mock LLM/Pinecone calls) installed.
- [ ] Frontend tooling: **pnpm** + **Vitest** + one **Playwright** smoke test for the streaming render.
- [ ] **RAGAS** + **DeepEval** scaffolded in `eval/` (even if metrics aren't computing yet — get the pytest hook ready so the gate exists).
- [ ] **Langfuse** (or LangSmith) account/instance ready; env var slot reserved in settings.
- [ ] An LLM response cache for development (disk-based, keyed on prompt hash) wired into `LLMService` — Claude/embedding spend will otherwise bleed during ingestion runs.

## CI

- [ ] GitHub Actions workflow at `.github/workflows/ci.yml` running on push:
  - [ ] `ruff check`, `ruff format --check`
  - [ ] `pyright`
  - [ ] `pytest -q api/ eval/`
  - [ ] `pnpm --filter web lint`, `typecheck`, `test --run`
  - [ ] `pnpm --filter @arcana/schema codegen --check` — schema drift fails the build
  - [ ] (P1) RAGAS gate

## Walking skeleton mandate

- [ ] Read PRD §11A.5 ("read this first") and `.claude/skills/genui-component/SKILL.md` once.
- [ ] Tell Claude Code: **build P0 as a vertical slice end-to-end before building any second of anything**. One PDF → one chunk → one embedding → one hybrid call → one `CitedSummary` → one streamed block → one rendered component, with `route_to_agent` exercised once. Only then do we go wide.

## Open-question status

- [ ] PRD §25 open questions (Q-03 to Q-10) scanned. For each, either:
  - the answer is now known (write it into the PRD), or
  - the assumption to proceed with is recorded in `.claude/memory/decisions.md` as `ASSUMED:`.

## Subagent + hook smoke test

- [ ] `code-reviewer` subagent invokes (`Use the code-reviewer subagent on docs/`) and returns a structured report. ✅ = the agent loads.
- [ ] Try to write a file containing the literal `sk-ant-EXAMPLE123456789ABCDEFGHIJKLMNOPQRSTUV` — the `check_secrets` hook should block it with exit 2 and a clear stderr message. (Then put `# pragma: allowlist secret` to confirm the allowlist works.)
- [ ] Try to write a Python file under `api/retrieval/` that imports from `api.agents.research` — `check_imports` should block it.

## Final gate

- [ ] First commit on `main`: `chore: project scaffold + .claude operating layer — supports R-10, NFR-SEC-03, FR-AGT-04`.

When every box is checked, Claude Code can start. Tell it: *"Read `CLAUDE.md`, then read PRD §11A. Then build the P0 walking skeleton per `checklist.md` §0.9, top to bottom. Stop and ask before touching anything `code-reviewer` flags."*
