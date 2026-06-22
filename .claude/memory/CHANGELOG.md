# Arcana — Changelog

> Mandatory AI session log. Add an entry after **every** session where code changed, a slice closed, or a plan was modified. Newest first. Even a one-line fix gets a one-line entry — don't wait for a "big refresh."
>
> Split from the former `.claude/memory/decisions.md` on 2026-06-22. Point-in-time architectural decisions (ADRs) live in [`DECISIONS.md`](DECISIONS.md); this file is the session-by-session narrative. If a session both ships code and makes a load-bearing decision, log the session here and add the ADR to `DECISIONS.md`, cross-linking by date.

Entry format:
```
### YYYY-MM-DD — [short summary of session goal]
- **Changed:** what files/components were touched and why
- **Decided:** any architectural or design calls and the reasoning (or "see DECISIONS.md ADR-0NN")
- **Deviations:** anything that differed from the plan, and why
- **Known issues / next steps:** what was left open
```

---

### 2026-06-22 — Phase-1 finish plan B1–B4 shipped (602 backend tests green)
- **Changed:** Batched checklist §1.13 (B1–B5) executed across two commits (`76a4ffc`, `9b425f6`). **B1 Ingestion & Graph:** `api/ingestion/parsers/youtube.py` (new transcript parser) + `ingest_youtube()` in `api/ingestion/pipeline.py` + `POST /ingest/youtube` in `api/routes/ingest.py` + `YoutubeIngestRequest` schema, `youtube-transcript-api` added as a dependency — FR-ING-03; per-document stage progress bar in `web/components/shell/SourcesPanel.tsx` — FR-ING-07; entity canonicalisation via head-token singularisation in `api/ingestion/extractor.py::_slug` — FR-ING-09; incremental graph merge behaviour locked in with new `api/ingestion/tests/test_incremental_graph.py` — FR-KG-03. **B2 Retrieval & Agents:** local/global/hybrid/auto retrieval mode via `hybrid_retrieve(mode=)` + `resolve_retrieval_mode()`, threaded through `AgentState.retrieval_mode` and `ChatRequest.retrievalMode` — FR-RET-07; contradiction surfacing verified as already prod-registered (no code change needed) — FR-RET-06; intent-scoped tool injection via `registry.select_tools()` capped at `max_tools_per_prompt`, orchestrator records scoped tools in the trace — FR-AGT-05; partial-result streaming via `Orchestrator.astream_run()` driving the LangGraph via `astream`, `progress` SSE frames emitted from `api/routes/chat.py` before blocks — FR-AGT-07; new tier-4 `api/agents/tier4/web_search.py` (`WebSearchAgent`) querying Semantic Scholar/arXiv → `SourceList`, new `websearch` intent wired in `api/agents/graph.py` and dispatched by the UI Agent, registered in `api/main.py::build_orchestrator()`. **B3 Learning/Accounts/Analytics:** `PomodoroPlan` schema + `StudyPlannerAgent` sizing logic + `web/components/genui/StudyPlanner.tsx` render — FR-LRN-09; user highlights/notes folded back into the graph via `ingest_highlight()` (reuses the extractor + merge path) + `POST /highlights` in new `api/routes/highlights.py` + `HighlightRequest`/`HighlightResponse` schema — FR-USR-05; generic `ActivityEvent` + `append_event()` added to `api/analytics/event_store.py`, fired from all three ingest routes (PDF/URL/YouTube) — FR-ANL/§20. **B4 Export & Interop:** stdlib-only generators, no new dependencies — hand-built single-page PDF (xref-accurate) and a zip/OOXML DOCX writer in new `api/export/document.py` — FR-EXP-01/02; BibTeX/RIS generation in new `api/export/bibliography.py` — FR-EXP-08; new `GET /export/report` and `GET /export/bibliography` routes. Net effect on the agent roster: 20 → **21** (the new `web_search` tier-4 agent). 602 backend tests green (up from 541 at the last refresh), ruff clean, codegen clean, web typecheck + lint clean.
- **Decided:** see DECISIONS.md ADR-013 (ML Engines deferred P1→P2), ADR-014 (remaining heavy/optional P1 items deferred to P2 except YouTube ingest), ADR-015 (Web Search agent built in P1, resolving a checklist self-contradiction), ADR-016 (export uses stdlib generators, not reportlab/python-docx).
- **Deviations:** Checklist §1.5 had contradicted itself on whether the Web Search agent was P1 or P2 (one line said P2, a list elsewhere placed it under P1 §1.5) — resolved in favour of P1 by author decision (ADR-015), since the work was already scoped and the agent count threshold benefits from it.
- **Known issues / next steps:** **B5 — NFR verification & Benchmark** (checklist §1.13) is the only batch left: §1.11 perf/scale/reliability/cost targets need to be measured and recorded, and §1.12's hybrid-vs-flat benchmark needs an actual run with real API keys. The user study itself (§1.12) is an author-side task, not gated by code. A second commit (`9b425f6`) updated `docs/arcana_prd.md` §12A and `docs/checklist.md` directly (author-authored doc edits, not this memory-keeper's scope) plus added `.claude/skills/resume/SKILL.md`.

### 2026-06-12 — Slice 20 complete: first-run/activation flow + §7.4 degradation
- **Changed:** `GET /suggestions` — LLM-generated seed questions from corpus doc titles, module-level `_cache` dict with `time.monotonic()` TTL (300s) + doc_count invalidation so the cache refreshes when new docs are ingested; falls back to `{"suggestions": []}` when no docs or LLM fails (never errors the user). `POST /ingest/retry/{doc_id}` (FR-ING-08) re-runs `ingest_pdf()` using bytes stored at `{doc_id}.bin` by `FilesystemDocStore`; 409 if already ready, 404 if no stored bytes. `CitedSummary.tsx` §7.4 degradation: amber italic note inline when `data.citations.length === 0 && meta.status === 'ready'` — no schema change, data was already present. `SourcesPanel.tsx` gained Retry + Dismiss buttons for failed docs.
- **Decided:** The cache invalidation condition (doc_count) was the key design call — a pure TTL would show stale suggestions after ingest, a per-request LLM call would be too slow. The hybrid (TTL + doc_count) solves both.
- **Deviations:** None.
- **Known issues / next steps:** `/suggestions` isn't personalized per-user yet (would need to pass `uid`). TTL may be too coarse for rapid-ingest workflows — revisit if that becomes a real workflow.

### 2026-06-12 — Slice 19 complete: tier-3 citation, visual, document agents
- **Changed:** `CitationAgent` (tier-3) — DocStore-backed citation formatting in APA/MLA/IEEE/Chicago/Harvard, auto-detects export vs per-doc intent from query keywords and title/url field presence, produces `CitationPreview` or `BibliographyExport`. `VisualAgent` (tier-3) — hybrid_retrieve → LLM → keyword detection ("concept map", "diagram", "compare") → `ConceptMap` (studio) or `ComparisonChart` (chat), panel target embedded in payload metadata. `DocumentAgent` (tier-3) — hybrid_retrieve → LLM → `CornellNotes`. All three wired in `api/agents/graph.py` with new intents "citation"/"visual"/"document", registered in `api/main.py::build_orchestrator()`, tier assignments added to `api/genui/trace.py`. UIAgent extended with routing slots 12–14. Agent count 17 → 20.
- **Decided:** All target block types already had schemas + renderers from Slice 13, so this was a pure agent-logic slice with no schema-first bottleneck. All three agents use only `DocStore`/`VectorStore` ABCs — no concrete backends, no direct agent imports.
- **Deviations:** None.
- **Known issues / next steps:** `CitationAgent` produces one bibliography entry per `doc_id`; multi-doc aggregation would need a `list_documents()` call scoped to the requesting user on the `DocStore` ABC.

### 2026-06-12 — Slice 18 complete: agent pipeline trace strip
- **Changed:** New SSE `event: trace` emitted after `event: ready`, before `event: block` (falls through gracefully if the consumer has no `onTrace` callback). `api/genui/trace.py` — `_AGENT_TIERS` + `_INTENT_PRIMARY` maps, `build_trace(state)` → `PipelineTrace` payload, tier colours T1=blue/T2=emerald/T3=violet/T4=amber. `PipelineTrace.tsx` — dismissible pill row above `ChatPanel.tsx`'s scroll area; A2A hops flagged with `is_hop=True` and a `↗` arrow, regular steps get `→`. `uiStore.ts` gained `trace`/`setTrace`/`clearTrace`, cleared at turn start.
- **Decided:** Trace is "free" — it reuses `AgentState.agent_results`, which already existed; no agent logic changes needed. Emitting after `ready` ensures primary content streams unblocked. A2A hop attribution uses a heuristic (an agent appearing after a different agent of same-or-lower tier is flagged as a hop) — ASSUMED correct for the current 3-agent compare path.
- **Deviations:** None.
- **Known issues / next steps:** Deeper A2A chains (4+ hops) will make the hop-detection heuristic ambiguous — at that point `AgentState` needs an explicit `hop_chain: list[str]` field.

### 2026-06-12 — Slice 17 complete: intent detection + A2A hops + 3-block compare path
- **Changed:** `_detect_intent_from_query()` — 11-intent keyword classifier in `api/agents/graph.py`, runs inside `_orchestrator_node` when `state.intent == ""`. A2A hops: `ComparatorAgent.run()` calls `route_to_agent("graph_agent", ...)` and `route_to_agent("contradiction", ...)` within its body, both within hop budget. 3-block compare path: UIAgent slots 0–14, compare intent triggers `LiteratureMatrix` + `ContradictionAlert` + `CitedSummary` terminal join. `_MODE_TO_INTENT` extended so all 5 modes have deterministic intent defaults.
- **Decided:** Keyword classifier chosen over an LLM-based router — fast, predictable, testable, no extra LLM call. Satisfies intent-detection for the FYP demo while deferring the ML-based approach (Q-03) to P2.
- **Deviations:** None.
- **Known issues / next steps:** Long paraphrased queries that don't match keyword patterns will misroute — add an LLM-based intent classifier as a pre-routing step before `_detect_intent_from_query` if that becomes a real failure mode.

### 2026-06-12 — Slice 16 complete: cross-document comparison matrix
- **Changed:** `api/retrieval/cross_doc.py` — `cross_doc_retrieve(query, vector_store, graph_store, doc_ids)` retrieves independently per `doc_id`, then zips into `(doc_id, chunks)` pairs, producing ranked `(doc_pair, evidence)` tuples. `CrossDocAgent` extended to call it instead of merged hybrid retrieve. Per-doc `top_k` defaults to 5 (vs global 8) to bound latency with many docs present.
- **Decided:** Merged retrieval loses the document boundary — you can't tell which chunks came from which doc. Per-doc retrieval + zip preserves that boundary so `CrossDocAgent` can produce genuine cross-document comparisons.
- **Deviations:** None.
- **Known issues / next steps:** If the corpus grows large enough that per-doc retrieval is noticeably slower than merged retrieval, add a metadata filter in the vector query instead of splitting queries.

### 2026-06-12 — Slice 15 complete: persistent user profile
- **Changed:** `api/stores/user_profile_store.py` — `UserProfileStore`, per-user JSON files at `local_storage/profiles/{uid}.json` (`display_name`, `email`, `preferences: dict`, `study_goals: list[str]`). `PUT /profile` uses PATCH semantics (only provided fields updated). `api/routes/profile.py` — `GET/PUT /profile`, auth-guarded, wired in `api/main.py`.
- **Decided:** Same JSON-sidecar pattern as `FilesystemDocStore` and `UserGraphRegistry` for consistency and a clean ABC seam for a later Firestore swap.
- **Deviations:** None.
- **Known issues / next steps:** Swap to Firestore is a one-line `Settings.profile_backend` change once `UserProfileStore` has a Firestore implementation (P1 §1.8).

### 2026-06-12 — Slice 14 complete: per-user graph persistence
- **Changed:** `api/stores/user_graph_registry.py` — `UserGraphRegistry` lazy-loads and in-memory-caches per-user `NetworkXGraphStore` instances from `local_storage/graphs/{uid}.json`; `get_or_create(uid)`, `save(uid)`, `save_all()` (called on `app.on_event("shutdown")`). `POST /ingest` and `POST /ingest/url` resolve the requesting user's graph via the registry and save after completion. `GET /graph` returns the calling user's graph as `{nodes, edges}` for `KnowledgeGraphView`. `graph_registry` built at startup in `api/main.py`, injected into `IngestContext` and `GraphAgent`.
- **Decided:** Registry pattern (lazy-load + cache) keeps per-request overhead low; JSON serialization via NetworkX's `node_link_data` is sufficient at FYP scale (<10K nodes/user). The `GraphStore` ABC seam is already in place for a future Neo4j swap.
- **Deviations:** None.
- **Known issues / next steps:** If a user's graph exceeds ~50K nodes, NetworkX JSON export will noticeably slow — switch `graph_backend=neo4j` in Settings at that point.

### 2026-06-12 — Slice 13 complete: 8 new P1 renderers (GenUI catalog 14→22)
- **Changed:** 8 new `UIBlock` variants (`ConceptMap`, `ComparisonChart`, `CitationPreview`, `BibliographyExport`, `Timeline`, `WritingPrompt`, `AnnotationView`, `PipelineTraceBlock`) added to `packages/schema/src/blocks.ts` + payloads, codegen re-run, 8 TSX renderers with all four states, 8 registry rows, `api/genui/validate.py` TypeAdapter updated to cover all 22 variants. `number → float` fix applied in codegen for `confidence` fields (`int` retained for counts).
- **Decided:** Schema-first ordering: renderers must exist before producing agents (otherwise `validate.py` rejects the payload in tests). Batched all 8 into one slice rather than 8 separate `genui-component` skill runs — the schema/registry/validate.py changes are highly parallel. Producing agents for the new variants deliberately deferred to Slice 19 — this was a schema + renderer unblocking pass, not a full agent slice.
- **Deviations:** None.
- **Known issues / next steps:** `Timeline` and `WritingPrompt` have renderers but no tier-2 agent output path yet — extend `TimelineAgent`/`WritingAgent` when needed.

### 2026-06-10 — Slice 12 scope: URL ingestion + document status API
- **Changed:** `api/ingestion/parsers/web.py` using httpx+bs4, page numbers simulated as ~1500-char logical sections. `DocStore.update_status()` extended with an optional `extra_update` dict to persist error causes. New routes: `POST /ingest/url` (JSON body), `GET /docs` (list), `GET /docs/{doc_id}` (status+error). doc_id strategy for URLs: `"url_" + sha256(url)[:16]` — stable, same URL = same doc_id.
- **Decided:** bs4 judged sufficient for MVP web parsing; trafilatura not installed.
- **Deviations:** None.
- **Known issues / next steps:** Out of scope this slice: DOCX parser (FR-ING-03), OCR (FR-ING-04), YouTube (FR-ING-03).

### 2026-06-10 — Slice 11 scope: three new GenUI catalog components
- **Changed:** Three new components — `StudyPlanner` (studio panel, emitted by tier-4 `StudyPlannerAgent`, SM-2 due-card queue/overdue count/next-session date, closes FR-LRN-09/10 partial), `BlurtingPrompt` (chat panel, emitted by `LearningAgent`, free-recall prompt + grounding passage revealed after blurt, closes FR-LRN-06), `CornellNotes` (studio panel, emitted by `LearningAgent`, cue/notes/summary, closes FR-LRN-05). Chunk order: schema → renderers → registry/validate.py → producing agents → review.
- **Decided:** All three close open Must/Should/Could learning FRs using zero new agent registrations — walking-skeleton mandate satisfied (each has a clear producing agent before the renderer exists). Catalog: 11/24 → 14/24.
- **Deviations:** None.
- **Known issues / next steps:** Out of scope: the other 10 unbuilt catalog components, web/DOCX parser (FR-ING-02), `@tool` decorators.

### 2026-06-08 — Slice 7 scope: 15+ agents — FR-AGT-06
- **Changed:** Added 7 new agents (8 → 15 total): `GraphAgent` (tier 2, queries `GraphStore` neighborhood → `KnowledgeGraphView`, intent "graph"), `LiteratureAgent` (papers × dimensions matrix → `LiteratureMatrix`, intent "literature"), `ContradictionAgent` (cross-source disagreement detection → `ContradictionAlert`, intent "contradiction"), `CrossDocAgent` (serendipitous connections → `InsightCard`, intent "cross_doc"), `ComparatorAgent` (comparison synthesis → `CitedSummary`, intent "compare"), `TimelineAgent` (chronological synthesis → `CitedSummary`, intent "timeline"), `AnnotationAgent` (claim-extraction/gap framing → `GapAnalysis`, intent "annotate"). `GraphEdge` store↔wire type distinction clarified: store uses `src/dst/type`, wire uses `source/target/relation`; `GraphAgent` synthesizes wire edges as `{source, target, relation="RELATED_TO"}` (ASSUMED — real edge-type lookup deferred pending a `GraphStore.get_edges_around()` method). `DiscoveryAgent` can now also produce `InsightCard` when its payload has `block_type="InsightCard"`.
- **Decided:** 4 dormant UIBlocks (`LiteratureMatrix`, `ContradictionAlert`, `InsightCard`, `KnowledgeGraphView`) activated with zero schema changes — they were pre-defined in Slice 2. The compare/timeline/annotate trio reuses existing `UIBlock` types (new prompts, not new schemas) to minimise the diff while crossing the ≥15-agent threshold.
- **Deviations:** `_MODE_TO_INTENT` left unchanged — new intents reachable only via explicit `state.intent` or `route_to_agent`, no mode maps to them yet (by design, not an oversight).
- **Known issues / next steps:** Once `GraphStore` ABC gains `get_edges_around(node_id, hops)`, `GraphAgent` should switch to typed edge relations instead of synthetic `RELATED_TO`.

### 2026-06-08 — Slice 6 complete: adaptive 3-panel shell — FR-UI-01/05, FR-UI-07
- **Changed:** `PanelLayout` type + `MODE_LAYOUT` record in `uiStore.ts` (research 20/45/35; study 8/45/47; writing 20/80/0; socratic 18/40/42; exploration 0/25/75); `selectActiveLayout` returns `layoutOverride ?? MODE_LAYOUT[activeMode]`; `setActiveMode` clears the override on mode switch. `Shell.tsx`'s hardcoded grid replaced with a flex row driven by `selectActiveLayout`; collapsed panels get `flex-grow:0; overflow:hidden; aria-hidden; inert`. New `PanelResizer.tsx` — 4px drag handle + arrow-key nudge, ARIA splitter attributes. 21 frontend tests (was 11); 335 backend tests remain green.
- **Decided:** `flex-grow` isn't CSS-animatable, so transition classes were removed rather than left as dead code; width-transition animation deferred to a follow-up using CSS grid fr-tracks.
- **Deviations:** None — all code-reviewer CRITICALs (React namespace import, flex-unit drift) and WARNINGs (dead transition classes, missing ARIA, keyboard focus into collapsed panels) were addressed before commit.
- **Known issues / next steps:** Width-transition animation needs a migration to `grid-template-columns: Xfr 4px Xfr 4px Xfr`, which IS animatable.

### 2026-06-08 — Slice 6 scope: adaptive 3-panel shell — frontend layout map
- **Changed:** Chose a frontend `mode → layout` map in `uiStore` (Option A) over a wire-level `LayoutHint` from the UI Agent (Option B, which would touch codegen + validator + streamer + UIAgent + `stream.ts`). Chunk order: uiStore + tests → `Shell.tsx` flex layout → `PanelResizer.tsx`.
- **Decided:** Walking-skeleton mandate — a wire-level `LayoutHint` is a 6+-file schema-first change while runtime behaviour is still purely mode-dependent; the frontend map gives identical UX for a fraction of the diff.
- **Deviations:** None.
- **Known issues / next steps:** Once the UI Agent gains per-turn layout intelligence (e.g. expanding Studio when a `KnowledgeGraphView` streams in), upgrade to the wire-level `LayoutHint`.

### 2026-06-07 — Slice 4 complete: Writing mode — WritingAgent + DraftEditor + FeynmanExplainer production
- **Changed:** `_MODE_TO_INTENT` routes "writing" active_mode → writing intent. `DraftSection + DraftEditorData + DraftEditor` added to schema + codegen. `WritingAgent` (tier-2): hybrid_retrieve (top_k=8) → build_draft_prompt → `_parse_draft_response` → `DraftEditor` payload. `LearningAgent` gained `_generate_feynman()` + keyword detection ("feynman", "eli5", "explain simply", ...) + `_parse_feynman_response()`. `UIAgent._build_from_writing()` added, priority order learning > socratic > writing > discovery > research > error; `_error` flag maps to `meta.status="error"`. `DraftEditor.tsx` error-state check moved before the empty-sections check so LLM failures render ErrorState not EmptyState; `key={section.heading}` not index. CRITICAL fix: `Orchestrator.__init__` now accepts `extra_agents: list[BaseAgent] | None`; `api/main.py` registers all Slice 3+4 tier-2 agents.
- **Decided:** All gates green; code-reviewer found 1 CRITICAL (agents not registered in main.py) + 3 WARNINGs — CRITICAL + WARNING-1 (error state) + WARNING-3 (FR-WRT-01, see DECISIONS.md) addressed before commit.
- **Deviations:** None.
- **Known issues / next steps:** `@tool` decorator gap on WritingAgent/LearningAgent/SocraticAgent deferred to Slice 5 (see DECISIONS.md). Multi-turn session management and the full intent classifier also deferred to Slice 5.

### 2026-06-06 — Slice 3 complete: Study mode — LearningAgent + SocraticAgent + 4 GenUI components
- **Changed:** 4 new `UIBlock` variants (`FlashcardDeck`, `QuizCard`, `SocraticDialog`, `FeynmanExplainer`) + codegen (`number → float`, PEP 604 union syntax). 4 new GenUI components with all four states + 4 registry rows (registry now covers all 10 variants). `LearningAgent` (tier-2): hybrid_retrieve → LLM → `FlashcardDeck`/`QuizCard`, with a temporary keyword heuristic for quiz vs flashcard. `SocraticAgent` (tier-2): never-answer contract via `_is_answer_shaped()` guard, 2-attempt regeneration, safe fallback question. study/socratic intent nodes wired in `graph.py`; UIAgent priority updated (learning > socratic > discovery > research > error).
- **Decided:** Preflight fix: resolved the Slice 2 ADR debt where `Orchestrator` constructor params were typed concretely instead of as `BaseAgent`. Post-review fixes: blocks.py import facade updated, 5 new validate tests added, FeynmanExplainer dead branch removed from UIAgent, `bg-accent/8` → `bg-accent/10` token fix.
- **Deviations:** None — code-reviewer found 3 CRITICALs + 4 WARNINGs, all addressed before commit.
- **Known issues / next steps:** Slice 4 to implement FeynmanExplainer production and active_mode → intent mapping (see DECISIONS.md for both as open ADRs at the time).

### 2026-06-06 — Slice 2 scope: GenUI catalog breadth + UI Agent intent routing
- **Changed:** Five-chunk slice: (1) schema — 5 new `UIBlock` variants (`LiteratureMatrix`, `ContradictionAlert`, `GapAnalysis`, `InsightCard`, `KnowledgeGraphView`); (2) 5 React components with all four states + registry rows; (3) UI Agent intent→component routing replacing the always-`CitedSummary` hard-code (FR-UI-04); (4) `DiscoveryAgent` (tier-2) producing `GapAnalysis`/`InsightCard`; (5) design tokens already wired in `tailwind.config.ts`, no new work.
- **Decided:** Components-before-agents ordering — an agent emitting a payload needs its renderer to exist first (schema-first ordering, invariant #2). Routing the UI Agent before adding `DiscoveryAgent` ensures the first non-`CitedSummary` block type renders correctly immediately.
- **Deviations:** None.
- **Known issues / next steps:** Interactive D3 `KnowledgeGraphView` out of scope — payload shape is locked so a future agent-side change isn't expected.

### 2026-05-22 — Slice 1 DONE: agent maturity landed
- **Changed:** LangGraph `StateGraph` assembly, entity extraction, real `GraphRetriever`, Fact Checker, Memory Agent — all five chunks green. Backend 263 passed (P0: 200, slice 1: +63). Multi-turn memory continuity test locks the contract. Error-status blocks excluded from memory writeback. Prompt versions stamped on extraction/fact-check/graph scoring for R-02 benchmark reproducibility. Unknown-intent routing falls back to default with a warning log.
- **Decided:** Phase 0 release gate (`docs/checklist.md` §0) declared satisfied as far as code goes: PDF ingest → graph built → 3-source hybrid retrieval → grounded cited answers, with Orchestrator + Research + Graph + Fact Checker + Memory Agent all demonstrably running.
- **Deviations:** None.
- **Known issues / next steps:** Remaining gate items (FYP 1 report, hybrid-vs-flat benchmark) are P1 §1.12 / author tasks, not code. Slice closed permanently — next slice opens its own thread.

### 2026-05-22 — Slice 1 scope: agent maturity (LangGraph + extraction + graph retriever + Fact Checker + Memory Agent)
- **Changed:** Five-chunk slice with `langgraph` as the only new heavy dependency. Pydantic `AgentState` kept (langgraph 0.2+ supports BaseModel state); each existing agent gets a thin `make_node(agent)` wrapper adapting `BaseAgent.run` to the langgraph node signature `(state) -> dict`.
- **Decided:** Forced dependency order: LangGraph first (every other agent registers as a node), then entity extraction (GraphRetriever needs a populated graph), then GraphRetriever traversal, then Fact Checker (verifies now-grounded synthesis), then Memory Agent (gates the LangGraph entry). Doing breadth (other tier-2 agents) before LangGraph would mean every new agent ships ad-hoc orchestration that gets ripped out later.
- **Deviations:** None.
- **Known issues / next steps:** Pin a known-good `langgraph` version if its BaseModel-state API regresses. Watch entity-extraction LLM cost per PDF against budget; switch extraction to a cheaper provider if it crosses a threshold.

### 2026-05-22 — P0 walking-skeleton slice DONE
- **Changed:** End-to-end vertical path: drop a PDF → ingest → hybrid retrieve → research-agent synth → ui-agent emits `CitedSummary` → server-validates fail-closed → SSE-streams → web registry renders all four states. Ten subsystems, 200 backend tests + 7 frontend tests, all four gates (ruff/pyright/pytest/vitest) green, codegen drift detector wired into CI.
- **Decided:** P0 skeleton declared complete. Next slice starts with: LangGraph `StateGraph` assembly (FR-AGT-04), entity extraction → graph build → real `GraphRetriever`, Fact Checker (FR-AGT-09), Memory Agent.
- **Deviations:** None.
- **Known issues / next steps:** Skeleton's job (de-risking schema codegen, SSE wire contract, dependency-direction enforcement, the seven-layer dependency chain) is done — going wide starts now. Slice closed permanently.
