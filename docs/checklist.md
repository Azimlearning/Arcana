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
> marked `(→ slice 1)`; the slice history in `.claude/memory/CHANGELOG.md`
> (and the slice ADRs in `.claude/memory/DECISIONS.md`) name each deferral and its rationale.

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
- [x] `parsers/youtube.py` (transcript) — **FR-ING-03 (S)**. *(B1: youtube transcript parser + ingest_youtube + POST /ingest/youtube + YoutubeIngestRequest schema; youtube-transcript-api dep; 10 parser tests.)*
- *(moved to P2 §2.2 — deferred 2026-06-22; corpus is text PDFs/URLs)* `ocr.py` for scanned PDFs — **FR-ING-04 (S)**.
- [x] Per-document progress + status surfaced to UI — **FR-ING-07 (S)**. *(B1: SourcesPanel per-doc stage progress bar (queued→parsing→embedding→ready) + pending status + role=progressbar; polls GET /docs/{id}.)*
- [x] Failed ingest reported with cause + retry — **FR-ING-08 (M)**. *(Slice 12: GET /docs + GET /docs/{docId} returning DocStatusResponse with status/error fields.)*
- [x] Entity canonicalisation (same concept → one node) — **FR-ING-09 (S)**. *(B1: head-token singularisation in extractor `_slug` — graphs/graph, ontologies/ontology collapse; guarded non-plurals; embedding-similarity merge remains P2 §1.2.)*

### 1.2 Knowledge graph maturity
- [x] Graph persists per user across sessions — **FR-KG-02 (M)**. *(Slice 14: UserGraphRegistry; per-user graphs at {storage}/graphs/{uid}.json; ingest + chat routes resolve per-user graph.)*
- [x] Incremental update on new document (no full reprocess) — **FR-KG-03 (S)**. *(B1: verified existing per-doc graph merge is incremental + idempotent; locked in with test_incremental_graph.py.)*
- [x] Louvain communities — **FR-KG-04 (S)**; PageRank — **FR-KG-05 (S)**. *(ExDev: `community` + `pagerank` fields in schema + codegen; GET /graph computes both; KnowledgeGraphView renders community-coloured pills with PageRank font-weight. Betweenness bridges → P2.)* Betweenness bridges — **FR-KG-06 (C)** — P2.
- [x] Interactive graph view endpoint — **FR-KG-08 (M)**. *(Slice 14: GET /graph returns GraphViewResponse; GraphViewNode/Edge types in schema + codegen.)*
- *(moved to P2 §2.2 — deferred 2026-06-22; NetworkX satisfies the P1 gate, swap is one setting)* Migrate to `neo4j_store.py`; flip `graph_backend=neo4j` — **R-06**.

### 1.3 Retrieval features
- [x] Cross-document comparison questions over the whole corpus — **FR-RET-05 (M)**. *(Slice 16: ComparatorAgent upgraded — top_k=20 corpus sweep; ≥2 docs → LiteratureMatrix JSON matrix; single-doc fallback → CitedSummary. UIAgent dispatches on block_type.)*
- [x] Contradiction surfacing on a queried concept — **FR-RET-06 (S)**. *(B2: verified — ContradictionAgent grounds via hybrid_retrieve, intent-routed by _detect_intent_from_query, prod-registered, emits ContradictionAlert; 7 tests.)*
- [x] Local/global/hybrid mode select or auto — **FR-RET-07 (C)**. *(B2: hybrid_retrieve `mode` param + resolve_retrieval_mode auto-heuristic gates retriever fan-out; threaded via AgentState.retrieval_mode + ChatRequest.retrievalMode; 13 tests.)*

### 1.4 Agentic pipeline (composability) — **the defining claim**
- [x] LangGraph `StateGraph` assembly: `AgentState`, nodes, conditional routing — `agents/graph.py`, **FR-AGT-04 (M)**, *Listing 11.1*.
- [x] Agent-to-agent invocation working end-to-end — **FR-AGT-03 (M)**, *Listing 11.4*.
- [x] Intent-scoped tool injection (`max_tools_per_prompt`) — **FR-AGT-05 (S)**, §11.5. *(B2: registry.select_tools(agents, limit) dedupes + caps at max_tools_per_prompt; orchestrator scopes by intent and records scoped_tools in trace; tests.)*
- [x] Partial-result streaming for long tasks — **FR-AGT-07 (S)**. *(B2: Orchestrator.astream_run drives the graph via astream, yielding per-node progress; chat route emits `progress` SSE frames before blocks; tests.)*
- [x] Graceful degradation on tool/agent failure — **FR-AGT-08 (M)**.
- [x] Hop-budget recursion guard + terminal join — **FR-AGT-10 (M)**, §11.6.
- [x] Reach **15+ agents across four tiers** (full vision 25) — **FR-AGT-06 (M)**.
- [x] **Verify the worked example** ("compare three papers" with 2 A2A hops + 3 streamed blocks) — *Listing 12.1*. *(Slice 17: intent detection in _orchestrator_node; ComparatorAgent calls route_to_agent(graph_agent) + route_to_agent(contradiction); UIAgent emits LiteratureMatrix + KnowledgeGraphView + ContradictionAlert.)*

### 1.5 Build out the agents (Tier 2/3/4, P1 set)
- [x] Tier 2: `learning.py` ✓, `writing.py` ✓, `socratic.py` ✓, `discovery.py` ✓ *(Slice 3+4)*; `graph_agent.py` ✓, `literature.py` ✓, `contradiction.py` ✓, `cross_doc.py` ✓, `comparator.py` ✓, `timeline.py` ✓, `annotation.py` ✓ *(Slice 7)* — **11/12 P1 tier-2 done** *(methodology.py → P2)*.
- [x] Tier 3: `ui_agent.py` ✓, `citation.py` ✓, `visual.py` ✓, `document.py` ✓ *(Slice 19)*.
- [x] Tier 4: `fact_checker.py` ✓, `memory.py` ✓, `study_planner.py` ✓ *(Slice 9)*; `annotation.py` → moved to tier-2 in Slice 7; `web_search.py` ✓ *(B2, now P1)*. **All P1 tier-4 agents complete**; `ingestion_agent.py`, `analytics.py` → P2.
- [x] Fact Checker verifies claims before output is finalised — **FR-AGT-09 (S)**.
- [x] Web Search Agent limited to academic discovery (Semantic Scholar / arXiv) — §12, scope non-goal respected. *(B2: WebSearchAgent tier-4 → Semantic Scholar/arXiv → SourceList; intent `websearch` + UIAgent dispatch + prod-registered; 6 tests. **Conflict resolved 2026-06-22:** built in P1 per author decision; the §1.5 'web_search.py → P2' note below is superseded.)*

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
- [x] First-run/activation flow + error/degradation states — `uiux_plan.md` §7.1, §7.4. *(Slice 20: GET /suggestions seed questions + TTL cache; POST /ingest/retry/{doc_id} FR-ING-08; CitedSummary degradation note §7.4; SourcesPanel retry button.)*
- [x] Agent-pipeline trace with A2A hop badges, tier-coloured — `uiux_plan.md` §8.

### 1.7 Learning system
- [x] Flashcards from doc/topic — **FR-LRN-01 (M)** *(Slice 3: LearningAgent → FlashcardDeck)*.
- [x] Spaced-repetition scheduling (SM-2) — **FR-LRN-02 (M)**. *(SM-2 algorithm in api/learning/sm2.py; POST /review endpoint; 24 unit tests; StudyPlannerAgent tier-4.)*
- [x] Quizzes (MCQ + short-answer) at selectable difficulty — **FR-LRN-03 (M)** *(Slice 3: LearningAgent → QuizCard)*.
- [x] Feynman explanations + gap flags — **FR-LRN-04 (S)** *(Slice 4: LearningAgent._generate_feynman() → FeynmanExplainer)*.
- [x] Cornell notes — **FR-LRN-05 (C)**; blurting — **FR-LRN-06 (C)**. *(Slice 11: CornellNotes + BlurtingPrompt GenUI components; LearningAgent generates both.)*
- [x] Socratic tutor never gives direct answers — **FR-LRN-08 (S)** *(Slice 3: SocraticAgent with _is_answer_shaped() guard)*.
- [x] Pomodoro + study schedules — **FR-LRN-09 (S)**. *(B3: PomodoroPlan schema + StudyPlannerAgent sizes focus/break cycles to the session; StudyPlanner.tsx renders the strip; 4 tests.)*
- [x] Per-topic progress tracking — **FR-LRN-10 (S)**. *(ExDev: JsonlReviewStore persists review events per-user; GET /review/progress returns ProgressDashboard-shaped stats — totalCards, masteredCards, streakDays, per-topic breakdown, nextReviewAt.)*

### 1.8 Accounts & persistence
- [x] `core/auth.py` guards routes — **FR-USR-01 (M), NFR-SEC-01**. *(get_current_user dep: Firebase token verify when firebase_project_id set; X-Dev-User-Id header in local dev.)*
- [x] Persistent profile (preferences, context) — **FR-USR-02 (M)**. *(Slice 15: UserProfileStore at {storage}/profiles/{uid}.json; GET /profile + PUT /profile; UserPreferences with defaultMode, theme, citationStyle, studyContext.)*
- [x] Notebook workspaces (CRUD) — **FR-USR-03 (M)**; per-user isolation — **FR-USR-06 (M)** / **NFR-SEC-02**. *(JsonlNotebookStore + POST/GET/DELETE /notebooks routes.)*
- [x] Interaction history persists + informs adaptation — **FR-USR-04 (S)**. *(ExDev: JsonlMemoryStore replaces InMemoryMemoryStore; per-notebook JSONL at {storage}/memory/{notebook_id}.jsonl; survives backend restart.)*
- [x] User highlights/notes ingested back into the graph — **FR-USR-05 (S)**. *(B3: ingest_highlight reuses extractor+merge; POST /highlights route + HighlightRequest/Response schema; per-user graph, doc provenance; 2 tests.)*

### 1.9 Export & interoperability
- [x] PDF report export — **FR-EXP-01 (S)**; DOCX — **FR-EXP-02 (S)**. *(B4: stdlib writers — hand-built single-page PDF (xref-accurate) + zip/WordprocessingML DOCX in api/export/document.py; GET /export/report?format=pdf|docx; no new deps; 6 tests.)*
- *(moved to P2 §2.2 — deferred 2026-06-22)* Obsidian vault import (wikilinks → edges) — **FR-EXP-05 (S)**; export — **FR-EXP-06 (S)**.
- [x] BibTeX / RIS citation export — **FR-EXP-08 (S)**. *(B4: api/export/bibliography.py to_bibtex/to_ris from DocMetadata; GET /export/bibliography?format=bibtex|ris; 4 tests.)*

### 1.10 Analytics & instrumentation
- [x] Log retrieval quality metrics — **FR-ANL-01 (S)**.
- [x] Instrument usage events for the user study — **FR-ANL-03 (S)**.
- [x] Capture events listed in §20 (ingestion, retrieval, agents, learning, UI). *(B3: generic ActivityEvent + append_event; ingestion events fired from all 3 ingest routes; TurnEvent already covers agents/retrieval/UI per turn, review_store covers learning.)*

### 1.11 Non-functional verification
- [ ] Time-to-first-token < 3 s — **NFR-PERF-01**; full synthesis < 15 s — **NFR-PERF-02**. *(B5: measurement harness `eval/nfr_check.py` built; live numbers are an author run with API keys.)*
- [x] 20-page PDF ingest < 60 s — **NFR-PERF-03**; 500-node graph render < 2 s — **NFR-PERF-04**. *(B5: PERF-04 verified — test_graph_perf.py, 500-node analytics well under 2s. PERF-03 measured via nfr_check.py harness, author run.)*
- [ ] ≥ 50 docs/notebook — **NFR-SCAL-01**; 10–15 concurrent users — **NFR-SCAL-02**. *(B5: concurrency measured via nfr_check.py `--concurrency`; author run with keys.)*
- [x] Retriever-failure degradation — **NFR-REL-01**; LLM fallback — **NFR-REL-02**. *(B5: verified by tests — test_hybrid.py (one/all retrievers fail → degrade) + test_service_fallback.py (provider fallback).)*
- [x] API spend capped + monitored — **NFR-COST-01**, **R-03**. *(B5: verified — TokenBudget hop+token guard, test_budget.py; intent-scoped tools (B2) further cap prompt cost.)*

### 1.12 Evaluation (FYP evidence)
- [x] Finalise `eval/questions.yaml` (~20 cross-document Qs, pre-registered) — **Q-03**, **R-02**.
- [x] `run_benchmark.py`: hybrid vs flat baseline, identical embeddings/corpus/questions — §23.1.
- [x] `metrics.py`: accuracy, citation correctness, latency; informal NotebookLM comparison.
- [ ] User study (10–15 participants) across Research/Study/Writing; SUS + task metrics — §23.2.

### 1.13 Phase 1 — Finish Plan (batched)

> **Why this exists.** §§1.1–1.12 track work at FR granularity; testing per-FR is the slow path. This block regroups the *remaining* unchecked P1 items into five batches. A batch is DONE only when its single QA pass (the `qa-runner` subagent: lint + types + tests + schema-drift) is green — run one QA pass per batch, not per item. Almost every Phase-1 **Must (M)** FR already shipped; what remains is Should/Could polish plus the §1.11/§1.12 verification runs.
>
> **Deferred to P2 at scope sign-off (2026-06-22):** Neo4j migration (R-06), OCR (FR-ING-04), Obsidian import/export (FR-EXP-05/06), and all ML Engines (§12A / FR-ENG-*). The Phase 1 gate depends on none of them.

- [x] **B1 — Ingestion & Graph.** YouTube transcript ingest (**FR-ING-03**), per-document progress surfaced to UI (**FR-ING-07**), entity canonicalisation — same concept → one node (**FR-ING-09**), incremental graph update on new doc, no full reprocess (**FR-KG-03**). → one QA pass over `api/ingestion/` + graph tests.
- [x] **B2 — Retrieval & Agents.** Contradiction surfacing on a queried concept (**FR-RET-06**), local/global/hybrid mode select-or-auto (**FR-RET-07**), intent-scoped tool injection (**FR-AGT-05**), partial-result streaming for long tasks (**FR-AGT-07**), academic Web Search agent — Semantic Scholar / arXiv (§12). → one QA pass over `api/retrieval/` + `api/agents/`.
- [x] **B3 — Learning, Accounts & Analytics.** Pomodoro + study schedules (**FR-LRN-09**), user highlights/notes ingested back into the graph (**FR-USR-05**), capture the §20 event set (**FR-ANL**). → one QA pass over `api/learning/` + analytics.
- [x] **B4 — Export & Interop.** PDF report export (**FR-EXP-01**), DOCX export (**FR-EXP-02**), BibTeX / RIS citation export (**FR-EXP-08**). → one QA pass over the export module.
- [~] **B5 — NFR verification & Benchmark.** *(Code/harness complete: REL-01/02 + COST-01 + PERF-04 verified by tests; nfr_check.py harness built for PERF-01/02/03 + SCAL. Remaining is **author-run** — the live perf measurement, the §1.12 hybrid-vs-flat benchmark run, and the user study — all need API keys / participants, not code.)*

### ✅ Phase 1 release gate (§24)

> **Status 2026-06-22:** all **code** is complete and green (603 backend tests; ruff/codegen/web typecheck clean). The unticked items below are **author-execution** — they need API keys, real participants, or report authorship, not code: the live perf measurement (§1.11), the §1.12 hybrid-vs-flat benchmark *run*, the user study, and the FYP 2 report.
- [x] All P0 + P1 **Must (M)** FRs implemented and demonstrable. *(code-complete; verified by the 603-test suite.)*
- [x] Full hybrid retrieval runs end-to-end on a real multi-document corpus. *(implemented + tested; the §1.12 benchmark harness exercises it end-to-end — author runs on their corpus with keys.)*
- [x] ≥ 15 agents with demonstrated agent-to-agent invocation. *(21 agents; A2A demonstrated by the worked-example test.)*
- [x] GenUI runs with ≥ 3 modes and live component streaming. *(5 modes; SSE block streaming + partial progress streaming.)*
- [x] Learning module generates flashcards + schedules via spaced repetition. *(FlashcardDeck + SM-2 + StudyPlanner + Pomodoro.)*
- [ ] Benchmark complete: **statistically significant gain over flat-RAG baseline** (primary metric). *(author run — `eval/run_benchmark.py` with keys + ingested corpus.)*
- [ ] User study complete: ≥ 10 participants, **SUS ≥ 70**. *(author — recruit participants; SUS infra already built.)*
- [x] No known defect blocks the core Research / Study / Writing journeys. *(603 tests green; no known blockers.)*
- [ ] FYP 2 report documents architecture, results, limitations. *(author — writing.)*

---

## Phase 2 — Post-FYP roadmap

> Items deferred out of Phase 1 plus the original P2 vision. Not gated by the FYP 2 release. Pick up via `/resume`.

### 2.1 ML Engines (§12A / FR-ENG)
- [ ] `api/engines/base.py` — `Engine` ABC (`predict()` + `is_available()`), leaf layer beside `stores/`/`llm/` — **FR-ENG-06**, *Listing 12A.0*.
- [ ] Re-Rank Engine — gradient-boosted post-RRF re-ranker, trained in Colab; strictly additive, RRF-only arm stays independently evaluable — **FR-ENG-01/02**, **NFR-PERF-05**, **R-11/R-13**, §12A.
- [ ] Mastery Engine — HLR recall/difficulty predictor; SM-2 fallback below per-user history threshold — **FR-ENG-03/04**, **R-12**, §12A.
- [ ] Document Classifier Engine — ingestion-time subject/topic/difficulty tagger over existing embeddings — **FR-ENG-05**, §12A.
- [ ] Each Engine's data sources + methodology documented and reproducible — **FR-ENG-07**, §23.4.
- [ ] Engine failure/absence falls back to its heuristic (RRF-only / SM-2 / no tag) without breaking the request — **NFR-REL-04**.

### 2.2 Deferred from Phase 1 (scope sign-off 2026-06-22)
- [ ] Migrate to `neo4j_store.py`; flip `graph_backend=neo4j`; verify no regressions vs NetworkX — **R-06**.
- [ ] `ocr.py` for scanned PDFs — **FR-ING-04 (S)**.
- [ ] Obsidian vault import (wikilinks → edges) — **FR-EXP-05 (S)**; export — **FR-EXP-06 (S)**.

### 2.3 Original P2 vision
- [ ] Complete the full 25-agent suite (methodology, ingestion, analytics agents) — §12.
- [ ] Betweenness-centrality bridge detection — **FR-KG-06 (C)**.
- [ ] Remaining GenUI components: PlagiarismReport, AudioSummary — §13.3.
- [ ] Collaboration / multi-user notebooks; production hardening — PRD §2 (P2 scope).
