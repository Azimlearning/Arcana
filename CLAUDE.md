# CLAUDE.md — Operating Instructions for the Arcana Coding Agent

> **You are the implementing engineer for Arcana.** This file is your standing brief and the **master index** over the five project documents. Read it at the start of every working session and obey it over your own defaults. It does not contain the spec — it tells you where each document lives, the order in which they have authority, the invariants you may never break, and the sequence in which to build.
>
> **Project:** Arcana — a graph-native, multi-agent research and learning platform (FastAPI + Next.js 14 monorepo). Final Year Project. The build is phased: **P0** = FYP 1 Proof of Concept · **P1** = FYP 2 MVP (the graded build) · **P2** = post-FYP roadmap.

---

## 1. Order of authority — which document wins

When two sources disagree, the higher one wins. Never silently resolve a conflict; surface it (see §8).

1. **`docs/arcana_prd.md` — the specification.** *What* to build and *to what standard*. Every requirement has a stable ID (`FR-…`, `NFR-…`), a MoSCoW priority (`M/S/C/W`), and a phase (`P0/P1/P2`). Its code listings are **contracts of shape** (signatures, schemas, data flow), not final code — honour the shape, don't copy verbatim.
2. **`docs/project_file_structure.md` — the map.** *Where* every file goes. Its directory boundaries are architectural boundaries. Do not invent paths; place files exactly where this map says.
3. **`docs/checklist.md` — the sequence.** *In what order* to build, top-to-bottom within a phase, each item traced to the FR/NFR it satisfies. This is your worklist.
4. **`docs/uiux_plan.md` — the design authority.** *How the interface looks and behaves.* Exact design tokens, the full 24-component catalog (panel + phase per component), the five modes and their proportions, the four mandatory interface states, the key flows, the agent-trace surface, and accessibility rules. Authoritative for everything under `web/`; it elaborates PRD §13–§15 without overriding the PRD's intent. Reference implementation: `arcana_mockup_v3.html`.
5. **`docs/env_generation_guide.md` — credentials & config.** Which keys exist, what each does, which profile needs them, and the security rules around them.

This file (`CLAUDE.md`) is the **master index** and tells you *how to operate*: conventions, invariants, definition of done.

> **Read before acting:** the PRD's "How to read this document" note and **§11A System Operation Guide** (the mental model), plus `project_file_structure.md` §0 golden rules. Before any frontend work, read `uiux_plan.md` §§1–6. If you have not read §11A this session, read it before writing any agent.

---

## 2. The one-paragraph mental model

A user message enters the **Orchestrator**, which detects *intent* (what work is needed → which agents run) and *mode* (what the workspace should look like → how the UI Agent lays it out). Agents execute as nodes in a **LangGraph state graph** over one shared **`AgentState`**. Any agent can pull in another mid-task via `route_to_agent` — that is composability. Agents never return prose; they deposit **typed `UIBlock`s** into shared state. The **UI Agent** runs last, picks components, assigns panels, and the blocks **stream to the browser over SSE**. Three guards (hop budget, token budget, per-tool try/except) keep the graph from looping, overspending, or crashing. That is the entire system. (PRD §11A.1.)

---

## 3. Hard invariants — never violate these

These are non-negotiable system properties (PRD §11A.3). If an implementation choice breaks one, it is wrong no matter how convenient.

1. **Grounding before generation.** No user-facing claim exists without retrieved evidence and a traceable citation. Provenance must survive all the way to exports. (FR-RET-08.)
2. **The UI is data, never code.** Agents emit typed `UIBlock`s only — never HTML, never executable strings. The server validates every block and **fails closed** before streaming. (FR-UI-03, NFR-SEC-04, R-10.)
3. **One agent owns presentation.** Only the **UI Agent** selects and lays out components. Every other agent produces *data*. (FR-UI-04.)
4. **Agents contribute to shared state.** Everything an agent produces lands in `AgentState` (`agent_results`, `ui_blocks`, …). Agents do not pass private arguments directly to one another — the graph must stay debuggable and replayable.
5. **Composability is uniform.** Calling another agent is just another tool call (`route_to_agent`). No special-case wiring between specific agents; any agent can call any agent, subject to the hop budget. (FR-AGT-03.)
6. **The loop always terminates at the UI Agent.** Even on partial failure or budget exhaustion, the graph routes to the UI Agent so the user always gets an honest, rendered response. (FR-AGT-08, FR-AGT-10.)
7. **Storage is always behind an abstraction.** Agents call `GraphStore` / `VectorStore` / `DocStore` — never a concrete backend. This is what makes NetworkX → Neo4j a one-line config change. (FR-KG-07, R-06.)
8. **No secret literals anywhere.** All config flows through `api/core/settings.py`. Verified by grep in CI. (NFR-SEC-03.)

---

## 4. Architectural rules (from `project_file_structure.md`)

- **Shared types live in `packages/schema/` first.** A type that crosses the wire (`UIBlock` variant, payload, API shape) is defined here once, then imported by both `api/` (via codegen → Pydantic) and `web/` (TypeScript). Never define a wire type in only one place. (R-10.)
- **Backend dependency direction is one-way:** `routes/ → agents/ → retrieval/ + stores/ → llm/`. Lower layers never import upper layers.
- **The frontend never hand-`switch`es on block type.** Rendering goes through `web/components/genui/registry.ts` → `renderBlock()`.
- **Keep the four "graph" files straight:** `agents/graph.py` = LangGraph execution graph · `agents/tier2/graph_agent.py` = the knowledge-Graph Agent · `stores/graph_store.py` = persistence · `retrieval/graph.py` = traversal retriever.
- **Adding a GenUI component is a fixed three-step change:** (1) add its `data` interface to `packages/schema/payloads.ts` and a variant to the `UIBlock` union in `blocks.ts`; (2) create `web/components/genui/<Name>.tsx`; (3) add one line to `registry.ts`. Nothing else should change. (NFR-MNT-02.)
- **Every catalog component implements all four states** — Empty / Loading / Partial / Error — via `BlockStates.tsx`. A component that can't render a skeleton fails NFR-USE-02 / FR-UI-09. Build components to `uiux_plan.md` §5–§6 (catalog, panels, phases, state behaviour) and tokens to §2.

---

## 5. Build sequence

Work **`checklist.md`** top-to-bottom. Do not start P1 work that depends on a P0 foundation before that foundation's release gate is green.

- **P0 (FYP 1 PoC) — the core evidence.** Monorepo + `core/` foundation + shared schema → LLM service with fallback → storage abstractions (NetworkX backend) → ingestion pipeline → **hybrid retrieval (vector + BM25 + graph + RRF)** → Orchestrator + Research + Graph agents → a `POST /chat` returning a cited summary, and the **hybrid-vs-flat comparison demo** that proves the premise.
- **P1 (FYP 2 MVP) — the graded build.** Expand ingestion; mature the knowledge graph and migrate to Neo4j behind the abstraction; the full **LangGraph agentic pipeline** with A2A invocation (reach **15+ agents**); Generative UI (24-component catalog, ≥3 modes, live streaming); the learning system; accounts/persistence; export; analytics; the **benchmark** (hybrid vs flat) and the **10–15 participant user study**.
- **P2 — post-FYP roadmap.** Complete the agent suite toward **25**, additional exports, collaboration, mobile, multi-language.

Build agents **in phase order**. A P2 agent may exist as a stub that raises `NotImplementedError`; the registry and routing must tolerate absent P2 agents gracefully.

---

## 6. Per-task definition of done

A task is not done until **all** of these hold (mirrors `checklist.md` cross-cutting DoD):

- [ ] Cross-wire types live in `packages/schema/` and are imported by both sides — never duplicated.
- [ ] Dependency direction respected (`routes → agents → retrieval/stores → llm`); no upward imports.
- [ ] Agents touch storage only via `GraphStore` / `VectorStore` / `DocStore`.
- [ ] New GenUI component = schema variant + `<Name>.tsx` + one `registry.ts` line + all four states.
- [ ] Every block validated server-side before streaming (fail closed).
- [ ] No secrets in source; all config via `Settings`.
- [ ] Lint + type-check pass on both apps.
- [ ] The commit references the FR/NFR/R/Q ID it addresses.

---

## 7. Conventions

- **Commits / PRs reference the requirement ID:** `feat(retrieval): RRF fusion — closes FR-RET-04`. Keep IDs in sync across the PRD, checklist, and file-structure docs — if you move a module or change a boundary, update the map *and* the PRD in the same change.
- **Config & secrets:** follow `env_generation_guide.md`. Secrets are environment-injected and never committed; only `.env.example` / `infra/env/*.example` (empty placeholders) are tracked. Run on the `local` profile (NetworkX, auth stubbable, three required keys: Anthropic, OpenAI embeddings, Pinecone). Keep the Pinecone index at **3072-dim** to match `text-embedding-3-large` — this must not change, or the benchmark comparison stops being like-for-like (R-02).
- **Phasing the spec honestly:** the platform vision is **25 agents**; the FYP delivers **15+** (FR-AGT-06 reads "15+ (full vision: 25)"). Don't quietly claim all 25 are built — track the gap as Q-01/Q-02.
- **Tech stack is locked** by the PRD (FastAPI, LangGraph, Next.js 14 App Router, Tailwind, Vercel AI SDK, Pinecone, NetworkX→Neo4j, Firebase). Don't substitute libraries without updating the PRD.

---

## 8. When you are blocked or find a conflict

- **An open question blocks you (Q-03–Q-10):** these are unresolved decisions in PRD §25 (e.g. benchmark question set, FSRS vs SM-2, hosting, budget values). If a task depends on one, implement behind a setting or interface so the decision can be swapped later, and flag it — don't guess silently.
- **Two documents disagree:** stop and surface it, citing both IDs/sections. Apply the order of authority in §1; the PRD wins on *what*, the file-structure map wins on *where*. Do not pick the more convenient reading.
- **A requirement seems wrong or risky:** note the FR/NFR/R ID and your concern in the PR; the human resolves it and updates the PRD. The PRD is the source of truth — change the spec, then the code, never the reverse.

---

*Master index over `docs/arcana_prd.md` (spec), `docs/project_file_structure.md` (map), `docs/checklist.md` (sequence), `docs/uiux_plan.md` (design authority), and `docs/env_generation_guide.md` (config). The PRD is the spec, the file-structure is the map, the checklist is the sequence, the UI/UX plan is the look-and-behaviour — and this file is how you operate.*
