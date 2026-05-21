# Arcana — Operating Brief

> The five spec docs are the source of truth. This file is short on purpose: keep it that way. Project-specific rules live in `.claude/rules/*.md` and load by path glob. Repeatable recipes live in `.claude/skills/*/SKILL.md` and load on demand.

## Order of authority (when docs conflict, surface it — don't resolve silently)

1. `docs/arcana_prd.md` — **what** and **why**. Owns FRs, NFRs, risks, the System Operation Guide (§11A).
2. `docs/project_file_structure.md` — **where**. Owns the repo map and the golden boundary rules.
3. `docs/uiux_plan.md` — **how it looks and feels**. Owns design tokens, modes, the 24-component catalog, state taxonomy.
4. `docs/checklist.md` — **when** (the sequence). Owns phases (P0/P1/P2) and release gates.
5. `docs/env_generation_guide.md` — **config**. Owns env vars and credentials.

If two docs disagree, stop and ask. Don't pick one and move on.

## Mental model (read PRD §11A before any non-trivial change)

User message → Orchestrator detects intent + mode → routes to specialists → specialists retrieve grounded evidence and call each other through `route_to_agent` within hop + token budgets → Fact Checker verifies claims → UI Agent picks typed components from intent/mode/history → blocks stream over SSE → frontend validates and renders via the component registry.

Every turn terminates at the UI Agent. Every block crosses the wire as a typed `UIBlock` defined in `packages/schema/`. Nothing else.

## The eight hard invariants (these are mechanism, not aspiration)

1. **Ground before generating.** No synthesis without hybrid retrieval evidence first (FR-RET-04, R-02).
2. **UI is data, never code.** Agents emit typed `UIBlock` payloads — never raw HTML or text (FR-UI-03).
3. **Only the UI Agent picks components.** No other agent decides what the user sees (FR-UI-04).
4. **Every agent contributes to shared state.** Append, don't overwrite. AgentState is the single ledger (§11.2).
5. **Uniform composability.** Agents call each other only through `route_to_agent`. Never import another agent module directly (§11.4).
6. **Always terminate at the UI Agent.** No path returns to the user without a UIBlock (§11.6).
7. **Storage behind abstractions.** Touch `GraphStore`, `VectorStore`, `DocStore` only — never a concrete backend (FR-KG-07, R-06).
8. **No secret literals.** Config flows through `Settings`; secrets via env. Verified in CI and a pre-commit hook (NFR-SEC-03).

Triggering an invariant check or fix? Load the matching `.claude/rules/*.md` for detail.

## Architectural rules (load the rule file when working in the matching path)

- `packages/schema/**` → `rules/schema-first.md` (types live here once; codegen emits Python; never duplicate)
- `api/**` → `rules/dependency-direction.md` (`routes → agents → retrieval/stores → llm`; no upward imports)
- `api/agents/**` → `rules/agent-composability.md` (route_to_agent only; no direct imports between agents)
- `web/components/genui/**` → `rules/genui-component.md` (registry-only rendering; all four states; tokens from `uiux_plan.md`)
- `api/**` and `web/**` → `rules/no-secret-literals.md` (Settings or env; nothing else)

## Repeatable recipes — invoke a Skill instead of improvising

- Adding a GenUI component → run `genui-component` skill
- Adding an agent → run `new-agent` skill
- Adding a retriever → run `new-retriever` skill
- Changing anything that crosses the wire → run `schema-first-change` skill

These Skills encode the exact step order from the PRD and file structure. Following them keeps the wire contract and dependency direction intact automatically.

## Build sequence

- **P0 (FYP 1 PoC):** ingest → graph → hybrid retrieval → Orchestrator + Research + Graph agents → one `CitedSummary` end-to-end. See `checklist.md` §0.
- **P1 (FYP 2 MVP, graded):** full 15+ agent graph, 24-component GenUI, ≥3 modes, learning system, accounts, benchmark vs flat-RAG, user study. See `checklist.md` §1.
- **P2 (post-FYP):** complete the 25 agents, exports, collaboration. See `checklist.md` §2.

**Never build the second of anything until the first is green end-to-end.** One PDF → one chunk → one embedding → one hybrid call → one `CitedSummary` → one streamed block → one rendered component. The walking skeleton de-risks the schema codegen, the SSE contract, and the LangGraph terminal join before any of them is load-bearing.

## Definition of done (every task)

- Types live in `packages/schema/` and are imported by both sides — never duplicated.
- Dependency direction respected; agents talk to storage only through abstractions.
- New components: schema variant + `<Name>.tsx` + one `registry.ts` line + all four states (Empty / Loading / Partial / Error).
- Every block validated server-side before streaming (fail closed).
- No secrets in source.
- Commit message references the FR / NFR / R / Q ID it addresses (e.g. `feat(retrieval): RRF fusion — closes FR-RET-04`).
- Nothing is DONE until the `qa-runner` subagent reports green.

## When blocked

- **Open question (Q-03 to Q-10):** check PRD §25. If unresolved, write your assumption to `.claude/memory/decisions.md`, mark it `ASSUMED:`, proceed, surface at next checkpoint.
- **Doc conflict:** stop. Don't pick. Quote both passages and ask.
- **Ambiguous spec:** prefer the safer / less-coupled option. Log the choice in `decisions.md`.

## Subagents (delegate, keep main context clean)

- `schema-guardian` — verifies the wire contract before changes ship. Read-only.
- `code-reviewer` — checks the eight invariants and the architectural rules before commit.
- `qa-runner` — runs lint, types, tests, RAGAS gate. Nothing is DONE until this is green.

Invoke explicitly: `Use the code-reviewer subagent on this diff.`

---

*Companion brief to `docs/arcana_prd.md`, `docs/project_file_structure.md`, `docs/uiux_plan.md`, `docs/checklist.md`, `docs/env_generation_guide.md`.*
