# Arcana — Build Checklist

> Phased, actionable build plan derived from `arcana_prd.md` and laid out against `project_file_structure.md`. UI/frontend tasks follow `uiux_plan.md` (the design authority). Referenced from `CLAUDE.md`.
>
> **How to use:** work top-to-bottom within a phase. Each item links to the requirement(s) it satisfies — reference them in commits (`feat(retrieval): RRF fusion — closes FR-RET-04`). Don't start P1 work that depends on a P0 foundation before that foundation is green. A phase is "done" when its release gate at the bottom passes.
>
> **Phases:** **P0** = FYP 1 Proof of Concept · **P1** = FYP 2 MVP (graded) · **P2** = post-FYP roadmap.

---

## Phase 0 — Project Setup & Foundations

> **Status (2026-05-22):** P0 walking skeleton merged on `ExDev` branch
> (commit `267b035`). Boxes below reflect what actually shipped vs. what
> was honestly deferred. Items deferred to slice 1 (agent maturity) are
> marked `(→ slice 1)`; the slice ADRs in `.claude/memory/decisions.md`
> name each deferral and its rationale.

### 0.1 Repository & tooling
- [x] Initialise the monorepo per `project_file_structure.md` (`api/`, `web/`, `packages/schema/`, `eval/`, `infra/`, `docs/`).
- [x] Add `CLAUDE.md` (master index) pointing at `docs/arcana_prd.md`, `docs/project_file_structure.md`, `docs/checklist.md`, `docs/uiux_plan.md`, `docs/env_generation_guide.md`.
- [x] `.env.example` with every variable documented; `.gitignore` excludes `.env`, `node_modules`, `.next`, `__pycache__`.
- [x] Root `Makefile`/`justfile`: `up`, `test`, `lint`, `ingest-demo`, `bench`.
- [x] Backend scaffold: FastAPI `main.py` (app factory + lifespan), `pyproject.toml` with pinned deps.
- [x] Frontend scaffold: Next.js 14 App Router + Tailwind + Vercel AI SDK; path alias `@/schema`. *(Tailwind + Next 14 shipped; Vercel AI SDK deferred — slice uses raw fetch+ReadableStream SSE consumer because EventSource is GET-only.)*
- [x] CI: lint + type-check both apps on push. *(.github/workflows/ci.yml — backend job + schema-and-frontend job.)*

### 0.2 Core foundation (`api/core/`)
- [x] `settings.py`: typed `Settings(BaseSettings)` — *Listing 9.2*. *(`local`/`study`/`prod-design` profiles selectable via `ENV` env var; one canonical `.env` file.)*
- [x] `logging.py`: structured JSON logging with request + agent trace ids.
- [x] `errors.py`: error envelope, exception handlers, `AllProvidersFailed`.
- [x] `budget.py`: `TokenBudget` + `charge_hop()` — §11.6.
- [x] **No secret literals anywhere** — `.claude/hooks/check_secrets.py` blocks at write time.

### 0.3 Shared schema (`packages/schema/`)
- [x] `entities.ts`: Document, Chunk, IngestStatus *(slice scope — GraphNode, GraphEdge, Notebook, UserProfile, ReviewState arrive when first used; → slice 1 adds GraphNode/Edge, slice 7 adds Notebook/UserProfile)*.
- [x] `blocks.ts`: `UIBlock` union (CitedSummary only) + `BlockMeta` — *Listing 13.1*.
- [x] `payloads.ts`: `CitedSummaryData` first — §16.1.
- [x] `api.ts`: `ChatRequest` + `ChatMessage`. *(IngestRequest + AgentResult — slice doesn't expose ingest via HTTP; → slice 8.)*
- [x] `codegen/to_python.ts`: emit Pydantic into `api/genui/_generated.py`; `codegen:check` drift gate wired in CI.

### 0.4 LLM service (`api/llm/`)
- [x] `service.py`: `LLMService.complete(messages, tools, model)` — *Listing 10.2*.
- [x] `providers/anthropic.py` (Claude primary, real httpx impl) + `providers/openrouter.py` (P0 stub that always raises so fallback path tests pass) — **NFR-REL-02**.
- [x] `prompts/`: `synthesis.py` shipped. *(`extraction.py` lands with → slice 1.)*

### 0.5 Storage abstractions (`api/stores/`)
- [x] `graph_store.py`: `GraphStore` ABC — `upsert_node/edge`, `expand`, `shortest_path`, `communities`, `pagerank` — *Listing 10.3*, **FR-KG-07**.
- [x] `networkx_store.py`: in-process `NetworkXGraphStore` with JSON node-link persistence (not pickle — security ADR).
- [x] `vector_store.py`: `VectorStore` ABC + `PineconeVectorStore` (REST via httpx, 3072-dim) — **FR-RET-01**.
- [x] `doc_store.py`: `DocStore` ABC + `FilesystemDocStore` slice-time impl with strict allowlist doc-id validation. *(Firestore impl → slice 7.)*
- [x] `chunk_store.py` + `jsonl_chunk_store.py` — durable text-of-chunks store for BM25 (not in original checklist; added because Pinecone can't enumerate the corpus).

### 0.6 Ingestion pipeline (`api/ingestion/`) — **P0 critical path**
- [x] `parsers/pdf.py` (PyMuPDF) — **FR-ING-01**. *(`parsers/docx.py` → slice 8 with FR-ING-02..04.)*
- [x] `chunker.py`: paragraph→sentence→hard-cut boundary preference with min-chunk-size floor — **FR-ING-05**.
- [x] **`embedder.py`** is now `api/embeddings/service.py` (split into its own peer module per user direction) — **FR-ING-05**.
- [x] `extractor.py`: LLM entity/relationship extraction → typed Triples — **FR-ING-06** *(→ slice 1)*.
- [x] `pipeline.py`: parse → chunk → embed → upsert vectors → chunk store. *(Entity extraction + graph build → slice 1.)*
- [x] Build the Concept/Person/Document/Topic graph with typed edges — **FR-KG-01** *(→ slice 1)*.

### 0.7 Hybrid retrieval (`api/retrieval/`) — **the FYP's core evidence**
- [x] `vector.py` (dense) — **FR-RET-01**. Fail-loud on missing metadata.
- [x] `bm25.py` (keyword, ASCII-locked tokenizer for benchmark reproducibility) — **FR-RET-02**.
- [x] `graph.py` (multi-hop traversal via GraphStore) — **FR-RET-03** *(slice 0 returns `[]`; → slice 1 wires real traversal)*.
- [x] `fusion.py`: `reciprocal_rank_fusion(rankings, k=60)` — **FR-RET-04**, *Listing 10.4*.
- [x] `hybrid.py`: `hybrid_retrieve()` running all three under `asyncio.gather` → RRF → top_k. NFR-REL-01 degradation tested.
- [x] Source attribution traceable to documents on every result — **FR-RET-08**.

### 0.8 Three core agents (`api/agents/`)
- [x] `base.py`: `BaseAgent`, `@tool` decorator (schema from type hints), registry, `route_to_agent` — §11.3–11.4.
- [x] `orchestrator.py`: direct-call slice-shape (research → ui_agent). *(Real intent/mode detect + plan → slice 1 with LangGraph StateGraph.)*
- [x] `tier2/research.py`: `hybrid_retrieve`, `summarise_with_grounding`, `cite_sources` (citation parser lives here) — §12 Research.
- [x] `tier2/graph_agent.py`: `graph_expand`, `shortest_path`, analytics — §12 Graph *(→ slice 1)*.
- [x] Each agent exposes typed tool calls — **FR-AGT-02**.
- [x] `tier3/ui_agent.py` (only agent that picks components) — **FR-UI-04**.

### 0.9 PoC demo + FYP 1 deliverables
- [x] Minimal `POST /chat` returning a `CitedSummary` over the demo corpus — fail-closed validation + SSE stream.
- [x] `eval/`: corpus directory + draft `questions.yaml` (3 placeholders) + stub `run_benchmark.py`.
- [ ] Working hybrid-retrieval **comparison demo** (hybrid vs flat) — *(P1 §1.12 — eval benchmark; planned as a late P1 slice.)*
- [ ] FYP 1 report + system design written — *(author task, not code.)*

### ✅ Phase 0 release gate
- [x] PDF/DOCX ingest → graph built → hybrid retrieval returns grounded, cited answers end-to-end — **PDF + graph populated via slice 1 entity extraction**. DOCX → P1 §1.1.
- [x] GraphStore abstraction in place with NetworkX backend (Neo4j swap is one setting).
- [x] Orchestrator + Research + Graph agents demonstrably running — **slice 1 closes the GraphRetriever stub; entity extraction is the Graph Agent's read path**.
- [x] All **P0 Must (M)** FRs implemented: FR-ING-01/05 ✓, FR-ING-06 ✓ (slice 1), FR-KG-01 ✓ (slice 1), FR-KG-07 ✓, FR-RET-01/02/03/04/08 ✓, FR-AGT-01/02 ✓, FR-UI-01 ✓.

> Phase 0 release gate **CLOSED** by slice 1 (commits `267b035` skeleton + slice-1 commit). Remaining bullets under §0.9 (FYP 1 report) and the formal hybrid-vs-flat benchmark are P1 §1.12 / author-side tasks, not code.

---

## Phase 1 — FYP 2 MVP (graded build)

### 1.1 Expand ingestion
- [x] `parsers/web.py` — **FR-ING-02 (M)**. *(Slice 12: httpx + BeautifulSoup HTML extractor; POST /ingest/url; doc-id derived from URL.)*
- [ ] `parsers/youtube.py` (transcript) — **FR-ING-03 (S)**.
- [ ] `ocr.py` for scanned PDFs — **FR-ING-04 (S)**.
- [ ] Per-document progress + status surfaced to UI — **FR-ING-07 (S)**.
- [x] Failed ingest reported with cause + retry — **FR-ING-08 (M)**. *(Slice 12: GET /docs + GET /docs/{docId} returning DocStatusResponse with status/error fields.)*
- [ ] Entity canonicalisation (same concept → one node) — **FR-ING-09 (S)**.

### 1.2 Knowledge graph maturity
- [x] Graph persists per user across sessions — **FR-KG-02 (M)**. *(Slice 14: UserGraphRegistry; per-user graphs at {storage}/graphs/{uid}.json; ingest + chat routes resolve per-user graph.)*
- [ ] Incremental update on new document (no full reprocess) — **FR-KG-03 (S)**.
- [ ] Louvain communities — **FR-KG-04 (S)**; PageRank — **FR-KG-05 (S)**; betweenness bridges — **FR-KG-06 (C)**.
- [x] Interactive graph view endpoint — **FR-KG-08 (M)**. *(Slice 14: GET /graph returns GraphViewResponse; GraphViewNode/Edge types in schema + codegen.)*
- [ ] Migrate to `neo4j_store.py`; flip `graph_backend=neo4j` — **R-06**; verify no regressions vs NetworkX.

### 1.3 Retrieval features
- [x] Cross-document comparison questions over the whole corpus — **FR-RET-05 (M)**. *(Slice 16: ComparatorAgent upgraded — top_k=20 corpus sweep; ≥2 docs → LiteratureMatrix JSON matrix; single-doc fallback → CitedSummary. UIAgent dispatches on block_type.)*
- [ ] Contradiction surfacing on a queried concept — **FR-RET-06 (S)**.
- [ ] Local/global/hybrid mode select or auto — **FR-RET-07 (C)**.

### 1.4 Agentic pipeline (composability) — **the defining claim**
- [x] LangGraph `StateGraph` assembly: `AgentState`, nodes, conditional routing — `agents/graph.py`, **FR-AGT-04 (M)**, *Listing 11.1*.
- [x] Agent-to-agent invocation working end-to-end — **FR-AGT-03 (M)**, *Listing 11.4*.
- [ ] Intent-scoped tool injection (`max_tools_per_prompt`) — **FR-AGT-05 (S)**, §11.5.
- [ ] Partial-result streaming for long tasks — **FR-AGT-07 (S)**.
- [x] Graceful degradation on tool/agent failure — **FR-AGT-08 (M)**.
- [x] Hop-budget recursion guard + terminal join — **FR-AGT-10 (M)**, §11.6.
- [x] Reach **15+ agents across four tiers** (full vision 25) — **FR-AGT-06 (M)**.
- [x] **Verify the worked example** ("compare three papers" with 2 A2A hops + 3 streamed blocks) — *Listing 12.1*. *(Slice 17: intent detection in _orchestrator_node; ComparatorAgent calls route_to_agent(graph_agent) + route_to_agent(contradiction); UIAgent emits LiteratureMatrix + KnowledgeGraphView + ContradictionAlert.)*

### 1.5 Build out the agents (Tier 2/3/4, P1 set)
- [x] Tier 2: `learning.py` ✓, `writing.py` ✓, `socratic.py` ✓, `discovery.py` ✓ *(Slice 3+4)*; `graph_agent.py` ✓, `literature.py` ✓, `contradiction.py` ✓, `cross_doc.py` ✓, `comparator.py` ✓, `timeline.py` ✓, `annotation.py` ✓ *(Slice 7)* — **11/12 P1 tier-2 done** *(methodology.py → P2)*.
- [ ] Tier 3: `ui_agent.py` ✓, `citation.py`, `visual.py`, `document.py`.
- [ ] Tier 4: `fact_checker.py` ✓, `memory.py` ✓, `study_planner.py` ✓ *(Slice 9)*; `annotation.py` → moved to tier-2 in Slice 7; `ingestion_agent.py`, `web_search.py`, `analytics.py` → P2.
- [x] Fact Checker verifies claims before output is finalised — **FR-AGT-09 (S)**.
- [ ] Web Search Agent limited to academic discovery (Semantic Scholar / arXiv) — §12, scope non-goal respected.

### 1.6 Generative UI (`web/` + `api/genui/`)
> Build to `uiux_plan.md` (the design authority): exact tokens, full catalog (panel + phase per component), modes, the four states, flows, and the agent trace.
- [x] Wire design tokens into `web/tailwind.config.ts` + `globals.css` (colour, type, space, radius, motion) — `uiux_plan.md` §2.
- [x] `api/genui/blocks.py` (import shapes from `packages/schema`) + `validate.py` (fail closed) — **NFR-SEC-04**, **R-10**.
- [x] `api/genui/streamer.py` SSE; `POST /chat` streams typed blocks — *Listing 10.1*.
- [x] `web/lib/stream.ts`: SSE → `UIBlock[]` consumer — §13.2.
- [x] `web/components/genui/registry.ts` + `renderBlock()` — *Listing 14.2*, **NFR-MNT-02**.
- [x] Agents emit declarative typed components, never raw HTML/text — **FR-UI-03 (M)**.
- [x] Build the **24-component catalog** (P0+P1 complete) — **FR-UI-02 (M)**, §13.3, `uiux_plan.md` §5. *(22/22 P0+P1 components done: CitedSummary, LiteratureMatrix, ContradictionAlert, GapAnalysis, InsightCard, KnowledgeGraphView, FlashcardDeck, QuizCard, SocraticDialog, FeynmanExplainer, DraftEditor, StudyPlanner, BlurtingPrompt, CornellNotes, SourceList, CitationPreview, BibliographyExport, ConceptMap, ComparisonChart, Timeline, DataTable, ProgressDashboard. Remaining 2 — PlagiarismReport, AudioSummary — are P2.)*
- [x] Every component implements Empty/Loading/Partial/Error via `BlockStates.tsx` — **NFR-USE-02**, **FR-UI-09 (S)**, `uiux_plan.md` §6. *(All 22 P0+P1 components implement all four states.)*
- [x] `ui_agent.py` selects components from intent/mode/history — **FR-UI-04 (M)**, *Listing 13.2*.
- [x] 3-panel adaptive shell; panel widths + visibility adapt — **FR-UI-01/05 (M)**. *(Slice 6: MODE_LAYOUT map in uiStore; Shell flex row + PanelResizer; Writing hides Studio, Exploration hides Sources.)*
- [x] Ship **≥ 3 modes** (Research, Writing, Study); demonstrate 5 — **FR-UI-06 (M)**, §13.5, `uiux_plan.md` §4. *(Slice 5: 5-mode switcher → `activeMode` on the wire → `_MODE_TO_INTENT` routing. research/study/writing/socratic/exploration all reachable.)*
- [x] Manual layout/mode override recorded in `uiStore` and respected — **FR-UI-07 (S)**. *(Slice 5: mode override — switcher writes `uiStore.activeMode`. Slice 6: PanelResizer drag writes `layoutOverride`; override wins for the session, cleared on mode switch.)* 
- [ ] First-run/activation flow + error/degradation states (not in mockup yet) — `uiux_plan.md` §7.1, §7.4.
- [x] Agent-pipeline trace with A2A hop badges, tier-coloured — `uiux_plan.md` §8.

### 1.7 Learning system
- [x] Flashcards from doc/topic — **FR-LRN-01 (M)** *(Slice 3: LearningAgent → FlashcardDeck)*.
- [x] Spaced-repetition scheduling (SM-2) — **FR-LRN-02 (M)**. *(SM-2 algorithm in api/learning/sm2.py; POST /review endpoint; 24 unit tests; StudyPlannerAgent tier-4.)*
- [x] Quizzes (MCQ + short-answer) at selectable difficulty — **FR-LRN-03 (M)** *(Slice 3: LearningAgent → QuizCard)*.
- [x] Feynman explanations + gap flags — **FR-LRN-04 (S)** *(Slice 4: LearningAgent._generate_feynman() → FeynmanExplainer)*.
- [x] Cornell notes — **FR-LRN-05 (C)**; blurting — **FR-LRN-06 (C)**. *(Slice 11: CornellNotes + BlurtingPrompt GenUI components; LearningAgent generates both.)*
- [x] Socratic tutor never gives direct answers — **FR-LRN-08 (S)** *(Slice 3: SocraticAgent with _is_answer_shaped() guard)*.
- [ ] Pomodoro + study schedules — **FR-LRN-09 (C)**; per-topic progress tracking — **FR-LRN-10 (S)**.

### 1.8 Accounts & persistence
- [x] `core/auth.py` guards routes — **FR-USR-01 (M), NFR-SEC-01**. *(get_current_user dep: Firebase token verify when firebase_project_id set; X-Dev-User-Id header in local dev.)*
- [x] Persistent profile (preferences, context) — **FR-USR-02 (M)**. *(Slice 15: UserProfileStore at {storage}/profiles/{uid}.json; GET /profile + PUT /profile; UserPreferences with defaultMode, theme, citationStyle, studyContext.)*
- [x] Notebook workspaces (CRUD) — **FR-USR-03 (M)**; per-user isolation — **FR-USR-06 (M)** / **NFR-SEC-02**. *(JsonlNotebookStore + POST/GET/DELETE /notebooks routes.)*
- [ ] Interaction history persists + informs adaptation — **FR-USR-04 (S)**.
- [ ] User highlights/notes ingested back into the graph — **FR-USR-05 (S)**.

### 1.9 Export & interoperability
- [ ] PDF report export — **FR-EXP-01 (S)**; DOCX — **FR-EXP-02 (S)**.
- [ ] Obsidian vault import (wikilinks → edges) — **FR-EXP-05 (S)**; export — **FR-EXP-06 (S)**.
- [ ] BibTeX / RIS citation export — **FR-EXP-08 (S)**.

### 1.10 Analytics & instrumentation
- [x] Log retrieval quality metrics — **FR-ANL-01 (S)**.
- [x] Instrument usage events for the user study — **FR-ANL-03 (S)**.
- [ ] Capture events listed in §20 (ingestion, retrieval, agents, learning, UI).

### 1.11 Non-functional verification
- [ ] Time-to-first-token < 3 s — **NFR-PERF-01**; full synthesis < 15 s — **NFR-PERF-02**.
- [ ] 20-page PDF ingest < 60 s — **NFR-PERF-03**; 500-node graph render < 2 s — **NFR-PERF-04**.
- [ ] ≥ 50 docs/notebook — **NFR-SCAL-01**; 10–15 concurrent users — **NFR-SCAL-02**.
- [ ] Retriever-failure degradation — **NFR-REL-01**; LLM fallback — **NFR-REL-02**.
- [ ] API spend capped + monitored — **NFR-COST-01**, **R-03**.

### 1.12 Evaluation (FYP evidence)
- [x] Finalise `eval/questions.yaml` (~20 cross-document Qs, pre-registered) — **Q-03**, **R-02**.
- [x] `run_benchmark.py`: hybrid vs flat baseline, identical embeddings/corpus/questions — §23.1.
- [x] `metrics.py`: accuracy, citation correctness, latency; informal NotebookLM comparison.
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
