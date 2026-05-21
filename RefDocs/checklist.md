# Arcana — Build Checklist

> Phased, actionable build plan derived from `arcana_prd.md` and laid out against `project_file_structure.md`. Referenced from `CLAUDE.md`.
>
> **How to use:** work top-to-bottom within a phase. Each item links to the requirement(s) it satisfies — reference them in commits (`feat(retrieval): RRF fusion — closes FR-RET-04`). Don't start P1 work that depends on a P0 foundation before that foundation is green. A phase is "done" when its release gate at the bottom passes.
>
> **Phases:** **P0** = FYP 1 Proof of Concept · **P1** = FYP 2 MVP (graded) · **P2** = post-FYP roadmap.

---

## Phase 0 — Project Setup & Foundations

### 0.1 Repository & tooling
- [ ] Initialise the monorepo per `project_file_structure.md` (`api/`, `web/`, `packages/schema/`, `eval/`, `infra/`, `docs/`).
- [ ] Add `CLAUDE.md` pointing at `docs/arcana_prd.md`, `docs/project_file_structure.md`, `docs/checklist.md`.
- [ ] `.env.example` with every variable documented; `.gitignore` excludes `.env`, `node_modules`, `.next`, `__pycache__`.
- [ ] Root `Makefile`/`justfile`: `up`, `test`, `lint`, `ingest-demo`, `bench`.
- [ ] Backend scaffold: FastAPI `main.py` (app factory + lifespan), `pyproject.toml` with pinned deps.
- [ ] Frontend scaffold: Next.js 14 App Router + Tailwind + Vercel AI SDK; path alias `@/schema`.
- [ ] CI: lint + type-check both apps on push.

### 0.2 Core foundation (`api/core/`)
- [ ] `settings.py`: typed `Settings(BaseSettings)` with `local`/`study`/`prod-design` profiles — *Listing 9.2*.
- [ ] `logging.py`: structured JSON logging with request + agent trace ids.
- [ ] `errors.py`: error envelope, exception handlers, `AllProvidersFailed`.
- [ ] `budget.py`: `TokenBudget` + `charge_hop()` (used in P1, build the seam now) — §11.6.
- [ ] **No secret literals anywhere** — verify via grep in CI — **NFR-SEC-03**.

### 0.3 Shared schema (`packages/schema/`)
- [ ] `entities.ts`: Document, Chunk, GraphNode, GraphEdge, Notebook, UserProfile, ReviewState — §19.1.
- [ ] `blocks.ts`: `UIBlock` union + `BlockMeta` (start with P0 variants) — *Listing 13.1*.
- [ ] `payloads.ts`: `CitedSummaryData` first — §16.1.
- [ ] `api.ts`: `ChatRequest`, `IngestRequest`, `AgentResult`.
- [ ] `codegen/to_python.ts`: emit Pydantic models into `api/`; wire into the build.

### 0.4 LLM service (`api/llm/`)
- [ ] `service.py`: `LLMService.complete(messages, tools, model)` — *Listing 10.2*.
- [ ] `providers/anthropic.py` (Claude primary) + `providers/openrouter.py` (fallback) — **NFR-REL-02**.
- [ ] `prompts/`: versioned templates (extraction, synthesis).

### 0.5 Storage abstractions (`api/stores/`)
- [ ] `graph_store.py`: `GraphStore` ABC — `upsert_node/edge`, `expand`, `shortest_path`, `communities`, `pagerank` — *Listing 10.3*, **FR-KG-07**.
- [ ] `networkx_store.py`: in-process `NetworkXGraphStore`.
- [ ] `vector_store.py`: `VectorStore` ABC + Pinecone impl (3072-dim) — **FR-RET-01**.
- [ ] `doc_store.py`: `DocStore` (Firestore metadata + object storage stub for local).

### 0.6 Ingestion pipeline (`api/ingestion/`) — **P0 critical path**
- [ ] `parsers/pdf.py` (PyMuPDF) + `parsers/docx.py` — **FR-ING-01**.
- [ ] `chunker.py`: semantic + fixed-window — **FR-ING-05**.
- [ ] `embedder.py`: `text-embedding-3-large` client — **FR-ING-05**.
- [ ] `extractor.py`: LLM entity/relationship extraction → typed Triples — **FR-ING-06**.
- [ ] `pipeline.py`: parse → chunk → embed → upsert vectors → extract → build graph.
- [ ] Build the Concept/Person/Document/Topic graph with typed edges — **FR-KG-01**.

### 0.7 Hybrid retrieval (`api/retrieval/`) — **the FYP's core evidence**
- [ ] `vector.py` (dense) — **FR-RET-01**.
- [ ] `bm25.py` (keyword) — **FR-RET-02**.
- [ ] `graph.py` (multi-hop traversal via GraphStore) — **FR-RET-03**.
- [ ] `fusion.py`: `reciprocal_rank_fusion(rankings, k=60)` — **FR-RET-04**, *Listing 10.4*.
- [ ] `hybrid.py`: `hybrid_retrieve()` running all three under `asyncio.gather` → RRF → top_k.
- [ ] Source attribution traceable to documents on every result — **FR-RET-08**.

### 0.8 Three core agents (`api/agents/`)
- [ ] `base.py`: `BaseAgent`, `@tool` decorator (schema from type hints), registry, `route_to_agent` — §11.3–11.4.
- [ ] `orchestrator.py`: intent/mode detect → plan → route — **FR-AGT-01**, *Listing 11.2*.
- [ ] `tier2/research.py`: `hybrid_retrieve`, `summarise_with_grounding`, `cite_sources` — §12 Research.
- [ ] `tier2/graph_agent.py`: `graph_expand`, `shortest_path`, analytics — §12 Graph.
- [ ] Each agent exposes typed tool calls — **FR-AGT-02**.

### 0.9 PoC demo + FYP 1 deliverables
- [ ] Minimal `POST /chat` returning a `CitedSummary` over the demo corpus.
- [ ] `eval/`: assemble fixed corpus + draft `questions.yaml`; stub `run_benchmark.py`.
- [ ] Working hybrid-retrieval **comparison demo** (hybrid vs flat) — proves the premise.
- [ ] FYP 1 report + system design written.

### ✅ Phase 0 release gate
- [ ] PDF/DOCX ingest → graph built → hybrid retrieval returns grounded, cited answers end-to-end.
- [ ] GraphStore abstraction in place with NetworkX backend (Neo4j swap is one setting).
- [ ] Orchestrator + Research + Graph agents demonstrably running.
- [ ] All **P0 Must (M)** FRs implemented: FR-ING-01/05/06, FR-KG-01/07, FR-RET-01/02/03/04/08, FR-AGT-01/02, FR-UI-01.

---

## Phase 1 — FYP 2 MVP (graded build)

### 1.1 Expand ingestion
- [ ] `parsers/web.py` — **FR-ING-02 (M)**.
- [ ] `parsers/youtube.py` (transcript) — **FR-ING-03 (S)**.
- [ ] `ocr.py` for scanned PDFs — **FR-ING-04 (S)**.
- [ ] Per-document progress + status surfaced to UI — **FR-ING-07 (S)**.
- [ ] Failed ingest reported with cause + retry — **FR-ING-08 (M)**.
- [ ] Entity canonicalisation (same concept → one node) — **FR-ING-09 (S)**.

### 1.2 Knowledge graph maturity
- [ ] Graph persists per user across sessions — **FR-KG-02 (M)**.
- [ ] Incremental update on new document (no full reprocess) — **FR-KG-03 (S)**.
- [ ] Louvain communities — **FR-KG-04 (S)**; PageRank — **FR-KG-05 (S)**; betweenness bridges — **FR-KG-06 (C)**.
- [ ] Interactive graph view endpoint — **FR-KG-08 (M)**.
- [ ] Migrate to `neo4j_store.py`; flip `graph_backend=neo4j` — **R-06**; verify no regressions vs NetworkX.

### 1.3 Retrieval features
- [ ] Cross-document comparison questions over the whole corpus — **FR-RET-05 (M)**.
- [ ] Contradiction surfacing on a queried concept — **FR-RET-06 (S)**.
- [ ] Local/global/hybrid mode select or auto — **FR-RET-07 (C)**.

### 1.4 Agentic pipeline (composability) — **the defining claim**
- [ ] LangGraph `StateGraph` assembly: `AgentState`, nodes, conditional routing — `agents/graph.py`, **FR-AGT-04 (M)**, *Listing 11.1*.
- [ ] Agent-to-agent invocation working end-to-end — **FR-AGT-03 (M)**, *Listing 11.4*.
- [ ] Intent-scoped tool injection (`max_tools_per_prompt`) — **FR-AGT-05 (S)**, §11.5.
- [ ] Partial-result streaming for long tasks — **FR-AGT-07 (S)**.
- [ ] Graceful degradation on tool/agent failure — **FR-AGT-08 (M)**.
- [ ] Hop-budget recursion guard + terminal join — **FR-AGT-10 (M)**, §11.6.
- [ ] Reach **15+ agents across four tiers** (full vision 25) — **FR-AGT-06 (M)**.
- [ ] **Verify the worked example** ("compare three papers" with 2 A2A hops + 3 streamed blocks) — *Listing 12.1*.

### 1.5 Build out the agents (Tier 2/3/4, P1 set)
- [ ] Tier 2: `learning.py`, `writing.py`, `socratic.py`, `discovery.py`.
- [ ] Tier 3: `ui_agent.py`, `citation.py`, `visual.py`, `document.py`.
- [ ] Tier 4: `fact_checker.py`, `annotation.py`, `memory.py`, `ingestion_agent.py`, `web_search.py`, `study_planner.py`, `analytics.py`.
- [ ] Fact Checker verifies claims before output is finalised — **FR-AGT-09 (S)**.
- [ ] Web Search Agent limited to academic discovery (Semantic Scholar / arXiv) — §12, scope non-goal respected.

### 1.6 Generative UI (`web/` + `api/genui/`)
- [ ] `api/genui/blocks.py` (import shapes from `packages/schema`) + `validate.py` (fail closed) — **NFR-SEC-04**, **R-10**.
- [ ] `api/genui/streamer.py` SSE; `POST /chat` streams typed blocks — *Listing 10.1*.
- [ ] `web/lib/stream.ts`: SSE → `UIBlock[]` consumer — §13.2.
- [ ] `web/components/genui/registry.ts` + `renderBlock()` — *Listing 14.2*, **NFR-MNT-02**.
- [ ] Agents emit declarative typed components, never raw HTML/text — **FR-UI-03 (M)**.
- [ ] Build the **24-component catalog** (one file each) — **FR-UI-02 (M)**, §13.3.
- [ ] Every component implements Empty/Loading/Partial/Error via `BlockStates.tsx` — **NFR-USE-02**, **FR-UI-09 (S)**.
- [ ] `ui_agent.py` selects components from intent/mode/history — **FR-UI-04 (M)**, *Listing 13.2*.
- [ ] 3-panel adaptive shell; panel widths + visibility adapt — **FR-UI-01/05 (M)**.
- [ ] Ship **≥ 3 modes** (Research, Writing, Study); demonstrate 5 — **FR-UI-06 (M)**, §13.5.
- [ ] Manual layout/mode override recorded in `uiStore` and respected — **FR-UI-07 (S)**.

### 1.7 Learning system
- [ ] Flashcards from doc/topic — **FR-LRN-01 (M)**.
- [ ] Spaced-repetition scheduling (FSRS/SM-2 — decide via **Q-04**) — **FR-LRN-02 (M)**.
- [ ] Quizzes (MCQ + short-answer) at selectable difficulty — **FR-LRN-03 (M)**.
- [ ] Feynman explanations + gap flags — **FR-LRN-04 (S)**; Cornell notes — **FR-LRN-05 (C)**; blurting — **FR-LRN-06 (C)**.
- [ ] Socratic tutor never gives direct answers — **FR-LRN-08 (S)**.
- [ ] Pomodoro + study schedules — **FR-LRN-09 (C)**; per-topic progress tracking — **FR-LRN-10 (S)**.

### 1.8 Accounts & persistence
- [ ] Firebase email + Google OAuth — **FR-USR-01 (M)**; `core/auth.py` guards all routes — **NFR-SEC-01**.
- [ ] Persistent profile (preferences, context) — **FR-USR-02 (M)**.
- [ ] Notebook workspaces (CRUD) — **FR-USR-03 (M)**; per-user isolation — **FR-USR-06 (M)** / **NFR-SEC-02**.
- [ ] Interaction history persists + informs adaptation — **FR-USR-04 (S)**.
- [ ] User highlights/notes ingested back into the graph — **FR-USR-05 (S)**.

### 1.9 Export & interoperability
- [ ] PDF report export — **FR-EXP-01 (S)**; DOCX — **FR-EXP-02 (S)**.
- [ ] Obsidian vault import (wikilinks → edges) — **FR-EXP-05 (S)**; export — **FR-EXP-06 (S)**.
- [ ] BibTeX / RIS citation export — **FR-EXP-08 (S)**.

### 1.10 Analytics & instrumentation
- [ ] Log retrieval quality metrics — **FR-ANL-01 (S)**.
- [ ] Instrument usage events for the user study — **FR-ANL-03 (S)**.
- [ ] Capture events listed in §20 (ingestion, retrieval, agents, learning, UI).

### 1.11 Non-functional verification
- [ ] Time-to-first-token < 3 s — **NFR-PERF-01**; full synthesis < 15 s — **NFR-PERF-02**.
- [ ] 20-page PDF ingest < 60 s — **NFR-PERF-03**; 500-node graph render < 2 s — **NFR-PERF-04**.
- [ ] ≥ 50 docs/notebook — **NFR-SCAL-01**; 10–15 concurrent users — **NFR-SCAL-02**.
- [ ] Retriever-failure degradation — **NFR-REL-01**; LLM fallback — **NFR-REL-02**.
- [ ] API spend capped + monitored — **NFR-COST-01**, **R-03**.

### 1.12 Evaluation (FYP evidence)
- [ ] Finalise `eval/questions.yaml` (~20 cross-document Qs, pre-registered) — **Q-03**, **R-02**.
- [ ] `run_benchmark.py`: hybrid vs flat baseline, identical embeddings/corpus/questions — §23.1.
- [ ] `metrics.py`: accuracy, citation correctness, latency; informal NotebookLM comparison.
- [ ] User study (10–15 participants) across Research/Study/Writing; SUS + task metrics — §23.2.

### ✅ Phase 1 release gate (§24)
- [ ] All P0 + P1 **Must (M)** FRs implemented and demonstrable.
- [ ] Full hybrid retrieval runs end-to-end on a real multi-document corpus.
- [ ] ≥ 15 agents with demonstrated agent-to-agent invocation.
- [ ] GenUI runs with ≥ 3 modes and live component streaming.
- [ ] Learning module generates flashcards + schedules via spaced repetition.
- [ ] Benchmark complete: **statistically significant gain over flat-RAG baseline** (primary metric).
- [ ] User study complete: ≥ 10 participants, **SUS ≥ 70**.
- [ ] No known defect blocks the core Research / Study / Writing journeys.
- [ ] FYP 2 report documents architecture, results, limitations.

---

## Phase 2 — Post-FYP Roadmap

- [ ] Complete the agent suite to **25**: `methodology.py`, `debate.py`, `audio.py`, `plagiarism.py`, `grammar_style.py`, `paraphrase.py`, `export_agent.py`.
- [ ] PPTX slide export — **FR-EXP-03 (C)**; audio summaries / podcast — **FR-EXP-04 (C)** / Audio Agent.
- [ ] Anki deck export — **FR-EXP-07 (C)**; Google Drive sync — **FR-EXP-09 (C)**.
- [ ] Interleaved practice sets — **FR-LRN-07 (C)**; complexity adapts to reading level — **FR-UI-08 (C)**.
- [ ] Study-effectiveness dashboard — **FR-ANL-02 (C)**.
- [ ] Real-time collaboration / shared notebooks; native mobile app; multi-language; deeper Obsidian/Anki.

---

## Cross-cutting definition of done (every task)
- [ ] Cross-wire types live in `packages/schema/` and are imported by both sides (never duplicated).
- [ ] Dependency direction respected: `routes → agents → retrieval/stores → llm` (no upward imports).
- [ ] Agents touch storage only via `GraphStore`/`VectorStore`/`DocStore` — never a concrete backend.
- [ ] New GenUI component = schema variant + `<Name>.tsx` + one `registry.ts` line + all four states.
- [ ] Every block validated server-side before streaming (fail closed).
- [ ] No secrets in source; config via `Settings`.
- [ ] Commit references the FR/NFR/R/Q ID it addresses.

---

*Companion to `arcana_prd.md` and `project_file_structure.md`. Keep IDs in sync with the PRD.*
