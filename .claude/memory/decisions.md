# Arcana — Decisions Log

> Lightweight ADR-style record of choices made during the build. The point isn't documentation theatre — it's that Claude Code sessions don't carry memory between runs, and the spec has open questions (Q-03 to Q-10) that may get resolved by *assumption* mid-build. Capturing those assumptions here keeps future sessions, the supervisor review, and the FYP defence on the same page.
>
> **When to write here:**
> - You hit an open question (Q-03..Q-10) without an answer and pick a path to keep moving.
> - You make a choice not explicitly in the PRD (a library, an algorithm constant, a UX detail).
> - You discover a spec contradiction and resolve it.
> - You opt out of a rule with a stated reason (e.g. `# pragma: allowlist secret`).
>
> **Format:** one short entry per decision. Date, the question, the decision, why, and what would force a revisit.

---

## Template

<!-- The block below is a FORMAT EXAMPLE, not a real ADR. Real entries are
     under "## Entries" further down, newest first. Do not read the dated
     example here as the latest decision. -->

```markdown

### 2026-06-06 — Slice 2 complete: GenUI catalog breadth + UI Agent routing + DiscoveryAgent

- **Status:** DECIDED
- **Context:** Slice 2 goal was to (a) add 5 new UIBlock variants to the catalog, (b) teach the UI Agent to route by intent, (c) ship a DiscoveryAgent that produces GapAnalysis payloads.
- **Decision:**
  - Chunk 1 (Schema): 5 new UIBlock variants (LiteratureMatrix, ContradictionAlert, GapAnalysis, InsightCard, KnowledgeGraphView) added to packages/schema/ + codegen + TypeAdapter validator. UP007 fixed by emitting X|Y|Z syntax in codegen.
  - Chunk 2 (React): 5 new GenUI components with all four states (Empty/Loading/Partial/Error) + 5 registry rows.
  - Chunk 3 (UI Agent routing): UIAgent._route_to_block dispatches to GapAnalysis from discovery agent result; CitedSummary is fallback.
  - Chunk 4 (DiscoveryAgent): Tier-2 agent, hybrid_retrieve → LLM gap analysis → GapAnalysisData payload. Wired as "discovery" intent in graph.py.
  - InsightCard routing in UIAgent deferred (DiscoveryAgent produces only GapAnalysis in Slice 2).
  - Orchestrator direct-import refactor deferred (see separate ADR).
- **Why:** All chunks kept gates green throughout. Code-reviewer found 3 CRITICALs (Empty state, InsightCard dead code, Orchestrator imports) — all addressed before commit.
- **Revisit if:** Slice 3 needs InsightCard from a dedicated agent; that's the trigger to implement the InsightCard branch properly.

### 2026-06-06 — Orchestrator direct agent imports — deferred refactor

- **Status:** DECIDED (deferred)
- **Context:** `api/agents/orchestrator.py` imports `ResearchAgent`, `UIAgent`, `FactChecker`, `MemoryAgent` by class. This violates dependency direction (lateral agent→agent imports) and invariant #5. Slice 2 code-reviewer flagged this as CRITICAL-3.
- **Decision:** Defer until Slice 3. Slice 2 correctly wired `DiscoveryAgent` via `graph.py` registry without touching the Orchestrator constructor. The four existing direct imports remain as-is.
- **Why:** The refactor is non-trivial (changes `Orchestrator.__init__` signature + all test call sites). No new direct imports were added in Slice 2.
- **Revisit if:** Any new agent needs to be wired into the Orchestrator constructor. Target: Slice 3 preflight.

### YYYY-MM-DD — <short title>

- **Status:** ASSUMED | DECIDED | REVISITED
- **Context:** what was unclear or open. Reference FR/NFR/R/Q IDs.
- **Decision:** what we're doing.
- **Why:** the trade-off that tipped it.
- **Revisit if:** the condition that would force reconsidering.
```

---

## Entries

<!-- New entries go below this line, newest first. -->

### 2026-06-12 — Slice 20 complete: first-run/activation flow + §7.4 degradation

- **Status:** DECIDED
- **Context:** Slice 20 closed the first-run UX gap (empty-state seed questions) and the honest-degradation requirement (NFR-REL-01): when the pipeline returns a `CitedSummary` with no citations, the user should know the answer may not be grounded.
- **Decision:**
  - `GET /suggestions` — LLM-generated seed questions from corpus doc titles. Module-level `_cache` dict with `time.monotonic()` TTL (300 s) + doc_count invalidation so the cache refreshes when new docs are ingested. Falls back to `{"suggestions": []}` when no docs or LLM fails (never errors the user).
  - `POST /ingest/retry/{doc_id}` (FR-ING-08) — re-runs `ingest_pdf()` using bytes stored at `{doc_id}.bin` by `FilesystemDocStore`. Returns 409 if already ready; 404 if no stored bytes.
  - `CitedSummary.tsx` §7.4 degradation — amber italic note inline when `data.citations.length === 0 && meta.status === 'ready'`. No new schema needed; data was already present.
  - `SourcesPanel.tsx` — Retry + Dismiss buttons for failed docs; Retry sets status to `embedding` and calls the retry route, falls back to `failed` on exception.
- **Why:** All changes were additive — no schema change, no agent change. The cache invalidation condition (doc_count) was the key design decision: a pure TTL would show stale suggestions after ingest; a per-request LLM call would be too slow. The hybrid solved both.
- **Revisit if:** The suggestions endpoint should be personalized per-user (requires passing uid to `/suggestions`) or the TTL is too coarse for rapid-ingest workflows.

### 2026-06-12 — Slice 19 complete: tier-3 citation, visual, document agents

- **Status:** DECIDED
- **Context:** Slice 19 added three new tier-3 output agents. All target block types (`CitationPreview`, `BibliographyExport`, `ConceptMap`, `ComparisonChart`, `CornellNotes`) had schemas + renderers already from Slice 13, so no schema change was needed.
- **Decision:**
  - `CitationAgent` (tier-3): DocStore-backed citation formatting in APA/MLA/IEEE/Chicago/Harvard. Auto-detects export vs per-doc intent from query keyword ("bibliography", "all", "references") and title/url field presence. Produces `CitationPreview` or `BibliographyExport`.
  - `VisualAgent` (tier-3): hybrid_retrieve → LLM → keyword detection ("concept map", "diagram", "compare") → `ConceptMap` (studio) or `ComparisonChart` (chat). Panel target embedded in payload metadata.
  - `DocumentAgent` (tier-3): hybrid_retrieve → LLM → `CornellNotes` structured document overview (cue/notes/summary).
  - All three wired in `api/agents/graph.py` with new intents "citation", "visual", "document". Registered in `api/main.py::build_orchestrator()`. `api/genui/trace.py` tier assignments added.
  - UIAgent extended with routing slots 12–14.
  - Agent count: 17 → 20.
- **Why:** Block-type pre-existence eliminated the schema-first bottleneck; the slice was purely agent logic. All three agents use only `DocStore`/`VectorStore` ABCs (no concrete backends) and call no other agent directly.
- **Revisit if:** CitationAgent needs multi-doc bibliography aggregation (currently produces one entry per doc_id). The DocStore ABC would need a `list_documents()` call scoped to the requesting user.

### 2026-06-12 — Slice 18 complete: agent pipeline trace strip

- **Status:** DECIDED
- **Context:** Slice 18 added the pipeline-trace SSE frame and the trace strip UI, satisfying `uiux_plan.md §8` and closing §1.6 trace surface.
- **Decision:**
  - SSE protocol: `event: trace` emitted after `event: ready`, before `event: block`. If missing, consumer falls through gracefully (no `onTrace` callback = silent pass).
  - `api/genui/trace.py` — `_AGENT_TIERS` + `_INTENT_PRIMARY` maps; `build_trace(state)` → `PipelineTrace` typed payload. Tier colours: T1=blue, T2=emerald, T3=violet, T4=amber.
  - `PipelineTrace.tsx` — pill row in `ChatPanel.tsx` above the scroll area; dismissible. A2A hops flagged with `is_hop=True` and a `↗` arrow; regular pipeline steps get `→`.
  - `uiStore.ts` — `trace` / `setTrace` / `clearTrace` slice. Cleared at turn start.
  - A2A hop attribution: `build_trace` walks `state.agent_results` in order; an agent that appears after a different agent of same or lower tier is flagged as a hop. ASSUMED: this heuristic is correct for the current 3-agent compare path (graph → contradiction → comparator); may need revision for deeper A2A chains.
- **Why:** Trace is "free" — it re-uses state that already existed in `AgentState.agent_results`; no agent logic changes needed. Emitting after `ready` ensures the primary content streams unblocked.
- **Revisit if:** Deeper A2A chains (4+ hops) make the hop-detection heuristic ambiguous. At that point `AgentState` should carry explicit `hop_chain: list[str]` field.

### 2026-06-12 — Slice 17 complete: intent detection + A2A hops + 3-block compare path

- **Status:** DECIDED
- **Context:** Slice 17 replaced the always-research fallback with a real intent classifier and demonstrated A2A hops for the "compare" intent.
- **Decision:**
  - `_detect_intent_from_query()` — 11-intent keyword classifier in `api/agents/graph.py`. Runs inside `_orchestrator_node` when `state.intent == ""`. Q-03 (full intent detection) remains deferred — keyword heuristic covers the demo set deterministically.
  - A2A hops — `ComparatorAgent.run()` calls `route_to_agent("graph_agent", ...)` + `route_to_agent("contradiction", ...)` within its body; both calls stay within hop budget. Demonstrates invariant #5 compliance for inter-agent communication.
  - 3-block compare path — `UIAgent` slots 0–14; compare intent triggers `LiteratureMatrix` + `ContradictionAlert` + `CitedSummary` terminal join.
  - `_MODE_TO_INTENT` map extended so all 5 modes have deterministic intent defaults.
- **Why:** The keyword classifier is fast, predictable, and testable — no LLM call needed for routing. This satisfies the intent-detection requirement for the FYP demo while deferring the ML-based approach (Q-03) to P2.
- **Revisit if:** Corpus queries don't match keyword patterns (e.g. long paraphrased questions). At that point, add an LLM-based intent classifier as a pre-routing step before `_detect_intent_from_query`.

### 2026-06-12 — Slice 16 complete: cross-document comparison matrix

- **Status:** DECIDED
- **Context:** FR-RET-05 requires cross-document evidence extraction for serendipitous connections. The existing `hybrid_retrieve` returns a merged result set with no per-document attribution.
- **Decision:**
  - `api/retrieval/cross_doc.py` — `cross_doc_retrieve(query, vector_store, graph_store, doc_ids)` retrieves independently per `doc_id`, then zips into `(doc_id, chunks)` pairs. Produces ranked `(doc_pair, evidence)` tuples.
  - `CrossDocAgent` extended to call `cross_doc_retrieve` for structured serendipitous connection detection instead of merged hybrid retrieve.
  - Per-doc top_k defaults to 5 (rather than global 8) to keep total latency bounded when many docs are present.
- **Why:** The key insight is that merged retrieval loses the document boundary — you can't tell which chunks came from which doc. Per-doc retrieval + zip preserves that boundary so `CrossDocAgent` can produce true cross-document comparisons.
- **Revisit if:** The corpus grows large enough that per-doc retrieval becomes noticeably slower than merged retrieval. At that point add a metadata filter in the vector query rather than splitting queries.

### 2026-06-12 — Slice 15 complete: persistent user profile

- **Status:** DECIDED
- **Context:** FR-USR-02 requires a user profile (display_name, email, preferences, study_goals). Slice 9 added Firebase auth; the profile was not persisted.
- **Decision:**
  - `api/stores/user_profile_store.py` — `UserProfileStore`: per-user JSON files at `local_storage/profiles/{uid}.json`. Fields: `display_name`, `email`, `preferences: dict`, `study_goals: list[str]`.
  - `PUT /profile` uses PATCH semantics: only provided fields are updated (missing keys retain existing values).
  - `api/routes/profile.py` — `GET/PUT /profile`; auth-guarded; wired in `api/main.py`.
- **Why:** Same JSON-sidecar pattern as `FilesystemDocStore` and `UserGraphRegistry` — consistent, testable, and replaceable via ABC seam for Firestore swap.
- **Revisit if:** P1 §1.8 (Firestore persistence) lands. The swap is a one-line `Settings.profile_backend` change once the `UserProfileStore` ABC has a Firestore implementation.

### 2026-06-12 — Slice 14 complete: per-user graph persistence

- **Status:** DECIDED
- **Context:** FR-KG-02 requires per-user knowledge graphs. The existing `NetworkXGraphStore` was a single shared in-memory instance — all users wrote to the same graph.
- **Decision:**
  - `api/stores/user_graph_registry.py` — `UserGraphRegistry`: lazy-loads and in-memory-caches per-user `NetworkXGraphStore` instances from `local_storage/graphs/{uid}.json`. Exposes `get_or_create(uid)`, `save(uid)`, `save_all()` (called on `app.on_event("shutdown")`).
  - `POST /ingest` and `POST /ingest/url` resolve the requesting user's graph via `graph_registry.get_or_create(user.uid)` and save after completion.
  - `GET /graph` — returns the calling user's graph as `{nodes: [...], edges: [...]}` for `KnowledgeGraphView` live data.
  - `api/main.py` — `graph_registry` built at startup and injected into `IngestContext` and `GraphAgent` constructor.
- **Why:** Registry pattern (lazy-load + cache) keeps per-request overhead low. JSON serialization via NetworkX's `node_link_data` is sufficient for FYP scale (< 10K nodes per user). The seam (GraphStore ABC) is already in place for a Neo4j swap.
- **Revisit if:** A user's graph exceeds ~50K nodes (NetworkX JSON export starts to noticeably slow). At that point switch `graph_backend=neo4j` in Settings.

### 2026-06-12 — Slice 13 complete: 8 new P1 renderers (GenUI catalog 14→22)

- **Status:** DECIDED
- **Context:** After Slice 11 (14 components), 10 catalog entries in `uiux_plan.md §4` still had no schema variant, renderer, or producing agent. The tier-3 agents planned for Slice 19 (citation, visual, document) could not be built without their target block types. A bulk schema + renderer pass unblocks them.
- **Decision:**
  - 8 new `UIBlock` variants added to `packages/schema/src/blocks.ts` + payload types in `payloads.ts`. Codegen re-run → `api/genui/_generated.py` updated. Variants: `ConceptMap`, `ComparisonChart`, `CitationPreview`, `BibliographyExport`, `Timeline`, `WritingPrompt`, `AnnotationView`, `PipelineTraceBlock`.
  - 8 TSX renderers in `web/components/genui/` with all four states (Empty/Loading/Partial/Error).
  - 8 registry rows added to `web/components/genui/registry.tsx`.
  - `api/genui/validate.py` TypeAdapter updated to cover all 22 variants.
  - `number → float` fix applied in codegen for `confidence` fields; `int` retained for counts.
  - Producing agents for the new variants deliberately left for Slice 19 — this is a schema + renderer unblocking pass, not a full agent slice.
- **Why:** Schema-first ordering: renderers must exist before producing agents can be written (otherwise validate.py will reject the payload in tests). Batching all 8 into one slice was cheaper than 8 separate genui-component skill runs — the schema / registry / validate.py changes are highly parallel.
- **Revisit if:** A producing agent for `Timeline` or `WritingPrompt` is needed — these have renderers but no tier-2 agent output path yet. Timeline → extend TimelineAgent; WritingPrompt → extend WritingAgent.

### 2026-06-10 — Slice 12 scope: URL ingestion + document status API
- Status: DECIDED
- Decision: (1) api/ingestion/parsers/web.py using httpx+bs4 (both already installed);
  page numbers simulated as ~1500-char logical sections. (2) DocStore.update_status()
  extended with optional extra_update dict to persist error causes. (3) New routes:
  POST /ingest/url (JSON body), GET /docs (list), GET /docs/{doc_id} (status+error).
- Out of scope this slice: DOCX parser (FR-ING-03), OCR (FR-ING-04), YouTube (FR-ING-03),
  trafilatura (not installed — bs4 is sufficient for MVP).
- doc_id strategy for URLs: "url_" + sha256(url)[:16] — stable, same URL = same doc_id.

### 2026-06-10 — StudyPlannerAgent exemption from hybrid_retrieve (invariant #1)
- Status: ASSUMED
- Decision: StudyPlannerAgent (Tier-4) is exempt from calling hybrid_retrieve because it performs
  pure deterministic scheduling — no content generation, no LLM call, no synthesis. It only
  re-filters Flashcard objects that were already grounded by LearningAgent earlier in the same turn.
  Calling hybrid_retrieve(top_k=1) would add latency/cost with zero semantic benefit and would
  require wiring three retriever dependencies into a utility agent whose contract is stateless
  post-processing.
- Deferred: Add reviewedCount field to StudyPlannerData (packages/schema/src/payloads.ts) once
  the frontend session-tracking flow is implemented. Progress bar removed from StudyPlanner.tsx
  until that field exists (WARNING #3 from Slice-11 code review).
- Note: state.retrieved_ctx is intentionally not extended by this agent. The traceability gap
  is acceptable because the agent emits no new knowledge claims — all cards originated from
  LearningAgent which DID extend retrieved_ctx. Surface this at FYP-2 checkpoint for reviewer
  sign-off.

### 2026-06-10 — Slice 11 scope: three new GenUI catalog components

- **Status:** DECIDED
- **Context:** Slice 10 closed with user-study infrastructure. The highest-impact optional code work (per HANDOFF_PROMPT.md §6) is expanding the GenUI catalog (currently 11/24). FR-UI-02 (Must) requires 24 components; the learning system (FR-LRN-05/06/09/10) has several open Should/Could items that map directly to unbuilt catalog components. All three chosen components use already-registered agents, eliminating the main.py production-registration trap.
- **Decision:** Build three new GenUI components: `StudyPlanner`, `BlurtingPrompt`, `CornellNotes`.
  - `StudyPlanner` (studio panel) — emitted by `StudyPlannerAgent` (tier-4, already registered via `extra_agents`). Shows the SM-2 due-card queue, overdue count, and next-session date. Closes FR-LRN-09/10 partial.
  - `BlurtingPrompt` (chat panel) — emitted by `LearningAgent` (tier-2, registered). Free-recall prompt + grounding passage revealed after blurt. Closes FR-LRN-06.
  - `CornellNotes` (studio panel) — emitted by `LearningAgent`. Cue/notes/summary structured format. Closes FR-LRN-05.
  - Chunk order (schema-first invariant): (1) schema — 3 payload interfaces + 3 UIBlock variants + codegen; (2) renderers — 3 TSX files with all four states; (3) registry + validate.py; (4) producing agents — extend StudyPlannerAgent + LearningAgent output paths, add UIAgent routing; (5) final review + close.
  - Out of scope this slice: the other 10 unbuilt catalog components, web/DOCX parser (FR-ING-02), @tool decorators.
- **Why:** All three components close open Must/Should/Could learning FRs using zero new agent registrations. Walking-skeleton mandate satisfied: each has a clear producing agent before the renderer exists. Brings catalog from 11/24 to 14/24.
- **Revisit if:** Supervisor requests specific other components (e.g. `ConceptMap`, `Timeline`) — add as Slice 12 using the same genui-component pattern.

### 2026-06-08 — Slice 7 scope: 15+ agents — FR-AGT-06

- **Status:** DECIDED
- **Context:** FR-AGT-06 requires ≥15 agents registered and callable via `route_to_agent`. Currently 8 are registered (research, learning, socratic, discovery, writing, ui_agent, fact_checker, memory). Four dormant UIBlocks have complete schemas + renderers but no producing agents: `LiteratureMatrix`, `ContradictionAlert`, `InsightCard`, `KnowledgeGraphView`.
- **Decision:** Add 7 new agents → 15 total:
  1. `GraphAgent` (tier 2) — queries GraphStore entity neighborhood; produces `KnowledgeGraphView`. Intent: "graph".
  2. `LiteratureAgent` (tier 2) — hybrid_retrieve → LLM structures papers × dimensions matrix; produces `LiteratureMatrix`. Intent: "literature".
  3. `ContradictionAgent` (tier 2) — hybrid_retrieve → LLM detects cross-source disagreements; produces `ContradictionAlert`. Intent: "contradiction".
  4. `CrossDocAgent` (tier 2) — hybrid_retrieve → LLM finds serendipitous cross-document connections; produces `InsightCard`. Intent: "cross_doc".
  5. `ComparatorAgent` (tier 2) — comparison-framed synthesis; produces `CitedSummary`. Intent: "compare".
  6. `TimelineAgent` (tier 2) — chronological synthesis; produces `CitedSummary`. Intent: "timeline".
  7. `AnnotationAgent` (tier 2) — claim-extraction and gap framing; produces `GapAnalysis`. Intent: "annotate".
  - `_MODE_TO_INTENT` unchanged — new intents are reachable only via explicit `state.intent` (future intent classifier) or `route_to_agent` from tests/other agents. No mode currently maps to them.
  - `GraphEdge` store↔wire type distinction: store uses `src/dst/type`, wire uses `source/target/relation`. `GraphAgent` synthesizes wire edges as `{source, target, relation="RELATED_TO"}` from the `expand()` neighborhood (ASSUMED: real edge-type lookup deferred to when GraphStore ABC gains a `get_edges_around()` method).
  - InsightCard deferred routing in `UIAgent._build_from_discovery()` also enabled: DiscoveryAgent can now produce InsightCard if its payload has `block_type="InsightCard"`.
- **Why:** 4 dormant UIBlocks activated with zero schema changes (they were pre-defined in Slice 2). Supporting trio (compare/timeline/annotate) reuses existing UIBlock types — new prompts, not new schemas. This minimises the diff while crossing the ≥15 threshold.
- **Revisit if:** GraphStore ABC gains a `get_edges_around(node_id, hops)` method — then `GraphAgent` can produce typed edge relations instead of synthetic RELATED_TO.

### 2026-06-08 — Slice 6 complete: adaptive 3-panel shell — FR-UI-01/05, FR-UI-07

- **Status:** DECIDED
- **Context:** Slice 6 goal was (a) per-mode panel width/visibility (FR-UI-01/05) and (b) manual drag override (FR-UI-07 layout half).
- **Decision:**
  - `PanelLayout` type + `MODE_LAYOUT` record added to `uiStore.ts` (research 20/45/35; study 8/45/47; writing 20/80/0; socratic 18/40/42; exploration 0/25/75). `selectActiveLayout` selector returns `layoutOverride ?? MODE_LAYOUT[activeMode]`. `setActiveMode` clears override so mode switches reset to the mode's default layout.
  - `Shell.tsx` hardcoded grid replaced with flex row driven by `selectActiveLayout`. Collapsed panels (studio in Writing, sources in Exploration) use `flex-grow:0; overflow:hidden; aria-hidden; inert` so they are invisible to keyboard and screen readers.
  - `PanelResizer.tsx` (new): 4px drag handle + arrow-key nudge, writes `setLayoutOverride`. Drag math back-calculates sources/studio from the actual chat floor to keep the flex-sum conserved. ARIA splitter attributes (`aria-valuenow/min/max`) added.
  - `flex-grow` is not CSS-animatable (spec); transition classes removed; width-transition deferred to a follow-up slice using CSS grid fr-tracks or explicit width approach.
  - 21 frontend tests (was 11 before Slice 6); all 335 backend tests remain green.
- **Why:** All code-reviewer CRITICALs (React namespace import, flex-unit drift) and WARNINGs (dead transition classes, missing ARIA, keyboard focus into collapsed panels) addressed before commit.
- **Revisit if:** Width transition animation is needed — then migrate Shell to `grid-template-columns: Xfr 4px Xfr 4px Xfr` which IS animatable.

### 2026-06-08 — Slice 6 scope: adaptive 3-panel shell — frontend layout map

- **Status:** DECIDED
- **Context:** Slice 6 goal: make the three shell panels resize/hide per mode (FR-UI-01/05) and add a manual-drag override (FR-UI-07 layout half). `uiux_plan.md` §3 states the UI Agent ultimately computes layout per turn; a static frontend map is the pragmatic first cut. Two options: (A) frontend `mode → layout` map in `uiStore` — no schema change; (B) `LayoutHint` over the wire from the UI Agent — schema-first change touching codegen + validator + streamer + UIAgent + stream.ts.
- **Decision:** Option A — frontend map. `PanelLayout` type and `MODE_LAYOUT` record in `uiStore.ts`. `selectActiveLayout` selector returns `layoutOverride ?? MODE_LAYOUT[activeMode]`. `setActiveMode` clears the override so mode switches always snap to the default for the new mode. `PanelResizer.tsx` writes drag results to `setLayoutOverride`. Chunk order: (1) uiStore + tests, (2) Shell.tsx flex layout + transitions, (3) PanelResizer.tsx drag handle. Agent-driven layout (`LayoutHint` on the wire) explicitly deferred — logged here so Slice 7+ can pick it up cleanly.
- **Why:** Walking-skeleton mandate — don't build the second of anything until the first is green. A wire-level LayoutHint requires a non-trivial schema-first change (6+ files) while the runtime behaviour is still purely mode-dependent; the frontend map produces identical UX with a fraction of the diff.
- **Revisit if:** The UI Agent gains per-turn layout intelligence (e.g. expanding Studio when a KnowledgeGraphView streams in) — at that point the LayoutHint wire approach is the right upgrade.

### 2026-06-07 — Slice 4 complete: Writing mode — WritingAgent + DraftEditor + FeynmanExplainer production

- **Status:** DECIDED
- **Context:** Slice 4 goals: (a) Writing mode intent routing (active_mode → intent mapping), (b) WritingAgent tier-2 agent producing DraftEditor payloads, (c) DraftEditor UIBlock (schema + React + registry), (d) FeynmanExplainer production in LearningAgent, (e) register Slice 3+4 tier-2 agents in api/main.py.
- **Decision:**
  - Preflight: `_MODE_TO_INTENT` map in `graph.py:_orchestrator_node` routes "writing" active_mode to writing intent. `_WIRED_INTENTS` updated.
  - Schema: `DraftSection + DraftEditorData + DraftEditor` added to `packages/schema/src/payloads.ts` + `blocks.ts`. Codegen regenerated.
  - WritingAgent: Tier-2 agent, hybrid_retrieve (top_k=8) → build_draft_prompt → _parse_draft_response → DraftEditor payload.
  - LearningAgent: Added `_generate_feynman()`, keyword detection ("feynman", "eli5", "explain simply", "simple terms", "like i'm"), `_parse_feynman_response()`.
  - UIAgent: `_build_from_writing()` added; priority order learning > socratic > writing > discovery > research > error. `_error` flag in payload → `meta.status="error"` so DraftEditor renders ErrorState correctly.
  - DraftEditor.tsx: Error state check moved before empty-sections check so LLM failures render ErrorState, not EmptyState. key={section.heading} (not index).
  - CRITICAL fix: `Orchestrator.__init__` accepts `extra_agents: list[BaseAgent] | None`; `api/main.py` constructs and registers all Slice 3+4 tier-2 agents (LearningAgent, SocraticAgent, DiscoveryAgent, WritingAgent).
  - `@tool` decorator gap: WritingAgent, LearningAgent, SocraticAgent expose no `@tool`-decorated methods (pre-existing pattern). Deferred to Slice 5 — `route_to_agent` calls `agent.run()` directly; tool registry is empty for these agents.
- **Why:** All gates green. Code-reviewer found 1 CRITICAL (agents not registered in main.py), 3 WARNINGs — CRITICAL + WARNING-1 (error state) + WARNING-3 (FR-WRT-01) addressed before commit.
- **Revisit if:** Slice 5 adds @tool decorators, multi-turn session management, or the full intent classifier.

### 2026-06-07 — FR-WRT-01 is an assumed identifier (not yet in arcana_prd.md)

- **Status:** ASSUMED
- **Context:** `api/agents/tier2/writing.py` and related files referenced `FR-WRT-01` as a functional requirement ID. Code-reviewer confirmed this ID does not exist in `docs/arcana_prd.md`. Writing mode is described in PRD §12.5 (Writing Agent) and the Epic D section, but no `FR-WRT-*` tag series exists.
- **Decision:** Remove `FR-WRT-01` from code comments; use "PRD §12.5 Writing Agent" as the reference. Log here so the FYP supervisor can formally number the writing requirements if needed.
- **Why:** The CLAUDE.md definition of done requires commit messages and docstrings to reference real FR/NFR IDs. Invented IDs break the traceability system.
- **Revisit if:** `docs/arcana_prd.md` is updated to formally number writing requirements as `FR-WRT-01..N`.

### 2026-06-07 — WritingAgent @tool decorators deferred

- **Status:** ASSUMED
- **Context:** `agent-composability.md` checklist requires tools declared via `@tool` decorators on each agent. WritingAgent (Slice 4), LearningAgent, SocraticAgent (Slice 3) all expose zero `@tool`-decorated methods. `route_to_agent` currently calls `agent.run()` directly, so the tool registry is empty for these agents and they are invisible to LLM-driven tool dispatch.
- **Decision:** Defer `@tool` decoration to Slice 5 (multi-agent tool dispatch / evaluation). The runtime behaviour is correct; the structural gap is non-breaking for P1 graded work.
- **Why:** Adding `@tool` decorators requires restructuring three agents simultaneously (schema inference from type hints, tool registration, run() forwarding). Doing it mid-Slice 4 would widen the diff and risk test churn with no P1 functional gain.
- **Revisit if:** Slice 5 wires LLM-driven tool dispatch or the evaluation benchmark requires per-agent tool specs.

### 2026-06-06 — SocraticAgent reads state.ui_blocks (Tier 3 output slot)

- **Status:** ASSUMED
- **Context:** `_extract_prior_turns()` in `api/agents/tier2/socratic.py` reads `state.ui_blocks` to reconstruct prior Socratic turns for conversation continuity. `state.ui_blocks` is the UI Agent's output slot (Tier 3), and Tier 2 agents should only read from `state.retrieved_ctx` and `state.agent_results`. This is a seam violation (code-reviewer WARNING-7).
- **Decision:** Defer the fix to Slice 5 (multi-turn session management). In P1, prior turns should flow through the ChatRequest history payload rather than via the UI output slot. For now the behaviour is correct — prior turns are reconstructed correctly — but the coupling is architecturally fragile.
- **Why:** Fixing it properly requires the frontend to send session history in `ChatRequest` and `AgentState` to carry a `history` field. That work belongs to the accounts/session slice (§1.8), not Slice 3.
- **Revisit if:** §1.8 (accounts & sessions) or multi-turn Socratic continuity becomes a test requirement.

### 2026-06-06 — Intent routing unreachable from chat route (study/socratic intents)

- **Status:** ASSUMED
- **Context:** `api/agents/graph.py` wires `study` and `socratic` intents as LangGraph conditional edges. However, `api/routes/chat.py` constructs `AgentState` with `intent=""` (default), and the orchestrator fallback `state.intent or _DEFAULT_INTENT` always returns `"research"`. LearningAgent and SocraticAgent are registered and wired, but the full chat pipeline cannot route to them without an explicit `state.intent` set upstream.
- **Decision:** Add a `decisions.md` entry (this one). As a minimal bridge, `active_mode` → `intent` mapping can be added to the orchestrator node in Slice 4 (`"study"` mode → `"study"` intent, `"socratic"` mode → `"socratic"` intent) so agents are reachable without a full intent-detection pass.
- **Why:** Full intent detection (Q-03) is a P1 work item (§1.3). Agents are testable in isolation; end-to-end routing is the Phase 1 deliverable. Shipping the agents without the router is consistent with the walking-skeleton mandate.
- **Revisit if:** Slice 4 adds active_mode → intent mapping OR the full intent classifier (§1.3) lands.

### 2026-06-06 — FeynmanExplainer: schema + renderer registered, no producing agent yet

- **Status:** ASSUMED
- **Context:** `FeynmanExplainer` is defined in the schema (`packages/schema/src/blocks.ts`), has a renderer (`web/components/genui/FeynmanExplainer.tsx`), and is registered in the registry. However, no backend agent produces a `FeynmanExplainer` payload. The UIAgent's `_build_from_learning` branch for FeynmanExplainer was removed (code-reviewer CRITICAL-3) to avoid dead wiring. The FeynmanExplainer frontend component remains live (schema and renderer are correct), waiting for its producing agent.
- **Decision:** Defer FeynmanExplainer production to Slice 4 (Writing/Explain mode). The schema and renderer are intentionally registered now — they are correct and will be used. No agent produces them yet.
- **Why:** Adding FeynmanExplainer to `LearningAgent` in Slice 3 would require a new prompt, parse path, and tests — that's a distinct agent concern better grouped with the Writing/Explain mode work in Slice 4.
- **Revisit if:** Slice 4 Writing mode starts; that slice should implement `_generate_feynman()` in LearningAgent (or a dedicated FeynmanAgent) and restore the UIAgent routing branch.

### 2026-06-06 — Slice 3 complete: Study mode — LearningAgent + SocraticAgent + 4 GenUI components

- **Status:** DECIDED
- **Context:** Slice 3 goal was to add Study mode: 4 new UIBlock variants, 4 React components, LearningAgent (flashcards + quiz), SocraticAgent (never-answer Socratic dialogue), and UI Agent routing for study/socratic intents.
- **Decision:**
  - Preflight: Orchestrator direct-import violation (Slice 2 ADR debt) resolved — constructor params typed as `BaseAgent`.
  - Chunk 1 (Schema): 4 new UIBlock variants (FlashcardDeck, QuizCard, SocraticDialog, FeynmanExplainer) added to `packages/schema/` + codegen updated (`number → float`, PEP 604 union syntax).
  - Chunk 2 (React): 4 new GenUI components with all four states + 4 registry rows (registry now covers all 10 UIBlock variants).
  - Chunk 3 (LearningAgent): Tier-2 agent, hybrid_retrieve → LLM → FlashcardDeck | QuizCard payloads. Intent keyword heuristic for quiz vs flashcard (documented as temp — see WARNING-S1 from code-reviewer).
  - Chunk 4 (SocraticAgent): Tier-2 agent with never-answer contract (`_is_answer_shaped()` guard, 2-attempt regeneration, safe fallback question).
  - Chunk 5 (UI Agent + graph): study/socratic intent nodes wired in `graph.py`; UIAgent priority routing updated (learning > socratic > discovery > research > error).
  - Post-review fixes: blocks.py import facade updated (CRITICAL-1); 5 new validate tests (CRITICAL-2); FeynmanExplainer dead branch removed from UIAgent (CRITICAL-3); bg-accent/8 → bg-accent/10 token fix (WARNING-6); deferred decisions logged (WARNING-4, WARNING-7).
- **Why:** All chunks kept gates green throughout. Code-reviewer found 3 CRITICALs and 4 WARNINGs — all addressed before commit.
- **Revisit if:** Slice 4 (Writing/Explain mode) implements FeynmanExplainer production and active_mode → intent mapping.

### 2026-06-06 — Slice 2 scope: GenUI catalog breadth + UI Agent intent routing

- **Status:** DECIDED
- **Context:** Slice 1 closed the agent-maturity seam (LangGraph + entity extraction + real GraphRetriever + Fact Checker + Memory Agent). The remaining P1 work requires more GenUI components before any new tier-2 agents can emit useful output. FR-UI-02 (24-component catalog), FR-UI-04 (UI Agent selects by intent/mode/history), and FR-AGT-06 (15+ agents) are all P1 Must.
- **Decision:** Five-chunk slice: (1) Schema — 5 new UIBlock variants (LiteratureMatrix, ContradictionAlert, GapAnalysis, InsightCard, KnowledgeGraphView); (2) React components — 5 TSX files with all four states + registry rows; (3) UI Agent intent→component routing to replace the always-CitedSummary hard-code (FR-UI-04); (4) DiscoveryAgent (tier-2) — produces GapAnalysis and InsightCard payloads; (5) Design tokens already wired in tailwind.config.ts (no new work needed).
- **Why:** Components before agents — an agent that emits a GapAnalysis payload needs its renderer to exist or the pipeline will never produce a visible result. Schema-first ordering is the wire-contract invariant (#2). Routing the UI Agent before adding DiscoveryAgent ensures the first non-CitedSummary block type is immediately rendered correctly.
- **Revisit if:** The interactive D3 KnowledgeGraphView is added (out of scope for this slice; the payload shape is locked so the agent side won't change).

### 2026-06-06 — `number` stays mapped to `int` in codegen; float fields avoided in Slice 2

- **Status:** DECIDED
- **Context:** The codegen comment says "Track when adding the first non-int field." Slice 2 payload design could use `number` for confidence/weight scores but those would be mis-typed as `int` in Pydantic.
- **Decision:** Design all Slice 2 payloads to avoid float fields. The `number → int` mapping is unchanged. Update the codegen to `float` when the first genuinely-fractional field is needed.
- **Why:** Changing `number → float` globally is a safe but unnecessary change right now. Deferring keeps the diff minimal.
- **Revisit if:** A payload field semantically requires a float.



### 2026-05-22 — Slice 1 DONE: agent maturity landed

- **Status:** DECIDED
- **Context:** All five chunks of slice 1 (LangGraph + entity extraction + real GraphRetriever + Fact Checker + Memory Agent) are green. Backend 263 passed (P0: 200, slice 1: +63). Ruff + pyright clean. Multi-turn memory continuity test locks the contract. Error-status blocks excluded from memory writeback (W1). Prompt versions stamped on extraction + fact-check + graph scoring for R-02 benchmark reproducibility (W4). Unknown-intent routing falls back to default with a warning log (W3).
- **Decision:** Phase 0 release gate (`docs/checklist.md` §0) is now satisfied as far as code goes: PDF ingest → graph built → 3-source hybrid retrieval → grounded cited answers; Orchestrator + Research + Graph (extraction+retrieval) + Fact Checker + Memory Agent all demonstrably running. Remaining gate items (FYP 1 report, hybrid-vs-flat benchmark) are P1 §1.12 / author tasks, not code.
- **Why:** The walking-skeleton mandate was "narrow first, breadth later." Slice 1 closes the agent-graph seam so every later tier-2 agent (Writing, Study, Socratic, …) drops into a path that already enforces hop budgets, fact-checks claims, remembers history, and traverses the entity graph.
- **Revisit if:** Never. Slice closed; next slice opens its own thread (slice 2 = wider GenUI catalog + UI-Agent intent-driven component selection).

### 2026-05-22 — Slice 1 scope: agent maturity (LangGraph + extraction + graph retriever + Fact Checker + Memory Agent)

- **Status:** DECIDED
- **Context:** P0 skeleton wired research → ui_agent as a direct call and shipped GraphRetriever as `return []`. Both were ADR'd deferrals so we could prove the wire contract before adding breadth. Slice 1 closes those gaps in dependency order: LangGraph first (every other agent registers as a node), then entity extraction (the GraphRetriever needs a populated graph), then GraphRetriever traversal logic, then Fact Checker (verifies the now-grounded synthesis), then Memory Agent (gates the LangGraph entry).
- **Decision:** Five-chunk slice with `langgraph` as the only new heavy dep. Pydantic `AgentState` is kept (langgraph 0.2+ supports BaseModel state); each existing agent gets a thin `make_node(agent)` wrapper that adapts `BaseAgent.run` to the langgraph node signature `(state) -> dict`.
- **Why:** Doing breadth (other tier-2 agents) before LangGraph would mean every new agent ships its own ad-hoc orchestration that gets ripped out later. Doing GraphRetriever before extraction would leave it returning empty for another slice. Order is forced by the dependency direction.
- **Revisit if:** LangGraph's BaseModel-state API regresses (pin a known-good version), OR entity-extraction LLM cost blows the per-PDF budget (slice 1 ADR will record actual measured cost; if it crosses a threshold we switch the extraction pass to a cheaper provider).

### 2026-05-22 — P0 walking-skeleton slice DONE

- **Status:** DECIDED
- **Context:** The walking-skeleton slice (subsystems 1–10) covered the end-to-end vertical path: drop a PDF → ingest → hybrid retrieve → research-agent synth → ui-agent emits CitedSummary → server-validates fail-closed → SSE-streams → web registry renders all four states. Ten subsystems, 200 backend tests + 7 frontend tests, all four gates (ruff / pyright / pytest / vitest) green, codegen drift detector wired into CI.
- **Decision:** Declare the P0 skeleton complete. Next slice (P1 first cut) starts with: LangGraph `StateGraph` assembly (FR-AGT-04), entity extraction → graph build → real `GraphRetriever`, Fact Checker (FR-AGT-09), Memory Agent.
- **Why:** The skeleton's job was to de-risk the schema codegen, the SSE wire contract, the dependency-direction enforcement, and the seven-layer dependency chain — all proven by the gates passing. Going wide before the seam was load-bearing would have been faster but fragile; going narrow first means every later component drops into a path that already works.
- **Revisit if:** Never. Slice is closed; the next slice opens its own thread.

### 2026-05-21 — Python `pyproject.toml` lives at repo root (not `api/`)

- **Status:** DECIDED
- **Context:** `docs/project_file_structure.md` §1 places `pyproject.toml` at `api/pyproject.toml`. But the dependency-direction hook (`.claude/hooks/check_imports.py`) detects layer membership by matching `api.<layer>.*` import prefixes — meaning the codebase has to use `from api.core.settings import ...`, not `from core.settings import ...`. For `api.*` imports to resolve via setuptools' `packages.find`, the package root (where pyproject lives) must sit **above** `api/`, not inside it.
- **Decision:** Place `pyproject.toml` and `.python-version` at the repo root. Top-level Python packages are `api` (and `eval/` once it lands). Imports throughout use the `api.<layer>.<module>` form the hook enforces.
- **Why:** The hook is the mechanism behind invariant #5 (composability) and invariant #7 (storage abstractions). Breaking the hook to satisfy a structural-doc preference would gut the enforcement layer. Updating the doc is cheap; rewriting the hook to also recognise bare `from core.…` imports is fragile.
- **Revisit if:** A second Python project lands (e.g. `eval/` grows its own deps) and we genuinely need separate package roots.

### 2026-05-21 — Walking-skeleton slice deferrals (StateGraph, Memory Agent, Fact Checker)

- **Status:** ASSUMED
- **Context:** PRD §11A.2 mandates a canonical lifecycle (Memory Agent first, hybrid retrieve, specialists, Fact Checker before any user-facing claim, terminal UI Agent) and FR-AGT-04 requires the LangGraph `StateGraph` assembly in `api/agents/graph.py`. The user's walking-skeleton brief explicitly defers all of these: orchestrator → research → ui_agent runs as a direct async call, Memory Agent and Fact Checker are absent.
- **Decision:** Build the slice without `agents/graph.py`, Memory Agent, or Fact Checker. The `CitedSummary` produced by this slice is grounded (hybrid retrieve participates) but **not fact-checked** — citation-accuracy invariant target (≥90%, FR-AGT-09) is *deferred*, not satisfied.
- **Why:** Walking-skeleton mandate (PRD §11A "build P0 as a vertical slice end-to-end before going wide"). FR-AGT-04 + Memory Agent + Fact Checker are P1 in `docs/checklist.md` §1.4–§1.5, so deferring matches the checklist.
- **Revisit if:** Subsystem 7 (agents) is green and we begin the second slice — the next slice MUST add `agents/graph.py` (FR-AGT-04) and the Fact Checker before any user-facing demo or evaluation run.

### 2026-05-21 — `DocStore` is a local-filesystem stub for the slice

- **Status:** ASSUMED
- **Context:** PRD locks Firebase Firestore + Storage for `DocStore`. The slice does not have accounts, multi-user isolation, or persisted metadata as in-scope concerns, and `docs/env_generation_guide.md` §2.6 explicitly permits a "P0 shortcut" stubbing auth + local metadata until P1 §1.8.
- **Decision:** Implement `DocStore` as a thin filesystem-backed module (`api/stores/doc_store.py`) that writes raw files under `infra/local_storage/` and metadata as JSON sidecars. The `DocStore` ABC is the seam; the Firestore impl arrives in a later slice.
- **Why:** Permitted by env guide §2.6; removes Firebase credential dependency for the slice; preserves the storage-abstraction invariant (#7) because agents still see only `DocStore`.
- **Revisit if:** P1 §1.8 (accounts & persistence) begins.

### 2026-05-21 — Spec docs moved to `docs/`

- **Status:** DECIDED
- **Context:** Repo shipped with the 5 spec docs at root, but `CLAUDE.md`, `.claude/memory/preflight.md`, and `docs/project_file_structure.md` §0 all reference them under `docs/`. Three authority files in agreement; the filesystem disagreed.
- **Decision:** Moved `arcana_prd.md`, `project_file_structure.md`, `uiux_plan.md`, `checklist.md`, and (newly supplied) `env_generation_guide.md` into `docs/`. `RefDocs/` (older snapshots) left untouched; not authoritative.
- **Why:** When authority and filesystem disagree, follow authority — it's the less-coupled change (one move vs. editing 3+ docs and the operating layer).
- **Revisit if:** Never. Locked.

### 2026-05-21 — `.claude/` operating layer scaffolded

- **Status:** DECIDED
- **Context:** No mechanism enforced the eight invariants and the architectural rules — they lived only in spec prose.
- **Decision:** Created `.claude/` with a trimmed `CLAUDE.md`, path-scoped rule files, three subagents (schema-guardian, code-reviewer, qa-runner), four Skills, and three hooks (secret-literal block, dependency-direction block, post-write format + check).
- **Why:** Spec invariants enforced in review only are spec invariants honoured maybe. Hooks turn them into mechanism.
- **Revisit if:** Claude Code hook/agent schema changes (track release notes); new invariants emerge from PRD updates.
