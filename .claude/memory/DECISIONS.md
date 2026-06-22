# Arcana — Decisions Log (ADRs)

> Lightweight ADR-style record of point-in-time architectural and design decisions — distinct from [`CHANGELOG.md`](CHANGELOG.md), which logs sessions. The point isn't documentation theatre — Claude Code sessions don't carry memory between runs, and the spec has open questions (Q-03 to Q-10) that may get resolved by *assumption* mid-build. Capturing those assumptions here keeps future sessions, the supervisor review, and the FYP defence on the same page.
>
> Split from the former `.claude/memory/decisions.md` on 2026-06-22. Session-level "what shipped" narratives moved to `CHANGELOG.md`; this file keeps only the entries that are a single decision + rationale + revisit trigger.
>
> **When to write here:**
> - You hit an open question (Q-03..Q-10) without an answer and pick a path to keep moving.
> - You make a choice not explicitly in the PRD (a library, an algorithm constant, a UX detail).
> - You discover a spec contradiction and resolve it.
> - You opt out of a rule with a stated reason (e.g. `# pragma: allowlist secret`).
>
> **Format:** `### ADR-NNN — <title>` then **Status** (ASSUMED | DECIDED | REVISITED), **Context**, **Decision**, **Why**, **Rejected** (if applicable), **Revisit if**. Numbered ascending, chronological. Don't renumber a superseded ADR — add a new one and cross-reference it as `(supersedes ADR-0NN)`.

---

### ADR-001 — `.claude/` operating layer scaffolded
- **Status:** DECIDED
- **Context:** No mechanism enforced the eight invariants and the architectural rules — they lived only in spec prose.
- **Decision:** Created `.claude/` with a trimmed `CLAUDE.md`, path-scoped rule files, three subagents (schema-guardian, code-reviewer, qa-runner), four Skills, and three hooks (secret-literal block, dependency-direction block, post-write format + check).
- **Why:** Spec invariants enforced in review only are spec invariants honoured maybe. Hooks turn them into mechanism.
- **Revisit if:** Claude Code's hook/agent schema changes (track release notes); new invariants emerge from PRD updates.

### ADR-002 — Spec docs moved to `docs/`
- **Status:** DECIDED
- **Context:** Repo shipped with the 5 spec docs at root, but `CLAUDE.md`, `.claude/memory/preflight.md`, and `docs/project_file_structure.md` §0 all referenced them under `docs/`. Three authority files agreed; the filesystem disagreed.
- **Decision:** Moved `arcana_prd.md`, `project_file_structure.md`, `uiux_plan.md`, `checklist.md`, and `env_generation_guide.md` into `docs/`. `RefDocs/` (older snapshots) left untouched, not authoritative.
- **Why:** When authority and filesystem disagree, follow authority — it's the less-coupled change (one move vs. editing 3+ docs and the operating layer).
- **Revisit if:** Never. Locked.

### ADR-003 — `DocStore` is a local-filesystem stub for the slice
- **Status:** ASSUMED
- **Context:** PRD locks Firebase Firestore + Storage for `DocStore`. The walking-skeleton slice has no accounts, multi-user isolation, or persisted metadata in scope, and `docs/env_generation_guide.md` §2.6 explicitly permits a "P0 shortcut" stubbing auth + local metadata until P1 §1.8.
- **Decision:** Implement `DocStore` as a thin filesystem-backed module (`api/stores/doc_store.py`) writing raw files under `infra/local_storage/` plus JSON sidecar metadata. The `DocStore` ABC is the seam; the Firestore impl arrives later.
- **Why:** Permitted by env guide §2.6; removes the Firebase credential dependency for the slice; preserves the storage-abstraction invariant (#7) because agents still see only `DocStore`.
- **Revisit if:** P1 §1.8 (accounts & persistence) begins. (Resolved partially by Slice 14/15 — see CHANGELOG 2026-06-12 — which added `UserGraphRegistry` and `UserProfileStore` on the same pattern; Firestore swap itself is still open.)

### ADR-004 — Walking-skeleton slice deferrals (StateGraph, Memory Agent, Fact Checker)
- **Status:** ASSUMED (resolved — see CHANGELOG 2026-05-22 "Slice 1 DONE")
- **Context:** PRD §11A.2 mandates a canonical lifecycle (Memory Agent first, hybrid retrieve, specialists, Fact Checker before any user-facing claim, terminal UI Agent) and FR-AGT-04 requires the LangGraph `StateGraph` assembly. The walking-skeleton brief explicitly deferred all of these: orchestrator → research → ui_agent ran as a direct async call, Memory Agent and Fact Checker absent.
- **Decision:** Build the P0 slice without `agents/graph.py`, Memory Agent, or Fact Checker. The `CitedSummary` produced is grounded (hybrid retrieve participates) but **not fact-checked** — the citation-accuracy invariant target (≥90%, FR-AGT-09) was deferred, not satisfied.
- **Why:** Walking-skeleton mandate (PRD §11A — vertical slice end-to-end before going wide). FR-AGT-04 + Memory Agent + Fact Checker are P1 in `docs/checklist.md` §1.4–§1.5.
- **Revisit if:** N/A — resolved in Slice 1.

### ADR-005 — Python `pyproject.toml` lives at repo root (not `api/`)
- **Status:** DECIDED
- **Context:** `docs/project_file_structure.md` §1 places `pyproject.toml` at `api/pyproject.toml`. But the dependency-direction hook (`.claude/hooks/check_imports.py`) detects layer membership by matching `api.<layer>.*` import prefixes, requiring `from api.core.settings import ...` rather than `from core.settings import ...`. For `api.*` imports to resolve via setuptools' `packages.find`, the package root must sit **above** `api/`.
- **Decision:** Place `pyproject.toml` and `.python-version` at the repo root. Top-level Python packages are `api` (and `eval/`). Imports throughout use the `api.<layer>.<module>` form the hook enforces.
- **Why:** The hook is the enforcement mechanism behind invariants #5 and #7. Breaking the hook to satisfy a structural-doc preference would gut the enforcement layer; updating the doc is the cheap side of the trade.
- **Revisit if:** A second Python project lands (e.g. `eval/` grows its own deps) and genuinely needs a separate package root.

### ADR-006 — `number` stays mapped to `int` in codegen; float fields avoided in Slice 2
- **Status:** DECIDED (superseded in part by Slice 13 — see CHANGELOG 2026-06-12)
- **Context:** The codegen comment said "track when adding the first non-int field." Slice 2 payload design could have used `number` for confidence/weight scores, which would mis-type as `int` in Pydantic.
- **Decision:** Design all Slice 2 payloads to avoid float fields; keep the `number → int` mapping unchanged for that slice.
- **Why:** Changing `number → float` globally was a safe but unnecessary change at the time; deferring kept the diff minimal.
- **Revisit if:** A payload field semantically requires a float. (Resolved: Slice 13 added the `number → float` fix for `confidence` fields, `int` retained for counts.)

### ADR-007 — Intent routing unreachable from chat route (study/socratic intents)
- **Status:** ASSUMED (resolved — see CHANGELOG 2026-06-07 "Slice 4")
- **Context:** `api/agents/graph.py` wired `study` and `socratic` intents as LangGraph conditional edges, but `api/routes/chat.py` constructed `AgentState` with `intent=""` and the orchestrator fallback always returned `"research"`. LearningAgent and SocraticAgent were registered and wired but unreachable from the full chat pipeline without an explicit `state.intent` set upstream.
- **Decision:** As a minimal bridge, add `active_mode → intent` mapping in the orchestrator node ("study" mode → "study" intent, "socratic" mode → "socratic" intent) so agents are reachable without a full intent-detection pass.
- **Why:** Full intent detection (Q-03) is a P1 work item (§1.3); shipping agents testable-in-isolation without the router first is consistent with the walking-skeleton mandate.
- **Revisit if:** N/A — resolved in Slice 4; superseded by the full keyword classifier in Slice 17 (CHANGELOG 2026-06-12).

### ADR-008 — FeynmanExplainer: schema + renderer registered, no producing agent yet
- **Status:** ASSUMED (resolved — see CHANGELOG 2026-06-07 "Slice 4")
- **Context:** `FeynmanExplainer` had a schema, a renderer, and a registry row, but no backend agent produced it — the UIAgent's `_build_from_learning` branch was removed (code-reviewer CRITICAL) to avoid dead wiring.
- **Decision:** Defer FeynmanExplainer production to Slice 4 (Writing/Explain mode). Schema and renderer registered now (correct, will be used); no agent produces them yet.
- **Why:** Adding it to `LearningAgent` in Slice 3 would need a new prompt, parse path, and tests — better grouped with Writing/Explain mode work in Slice 4.
- **Revisit if:** N/A — resolved; `LearningAgent._generate_feynman()` landed in Slice 4.

### ADR-009 — SocraticAgent reads `state.ui_blocks` (Tier-3 output slot) — known seam violation
- **Status:** ASSUMED (still open)
- **Context:** `_extract_prior_turns()` in `api/agents/tier2/socratic.py` reads `state.ui_blocks` (the UI Agent's Tier-3 output slot) to reconstruct prior Socratic turns. Tier-2 agents should only read from `state.retrieved_ctx` and `state.agent_results` — this is a seam violation (code-reviewer WARNING).
- **Decision:** Defer the fix to the multi-turn session management slice. Prior turns should flow through the `ChatRequest` history payload rather than via the UI output slot. Current behaviour is functionally correct but architecturally fragile.
- **Why:** Fixing it properly requires the frontend to send session history in `ChatRequest` and `AgentState` to carry a `history` field — that work belongs to the accounts/session slice (§1.8), not the Study-mode slice it was found in.
- **Revisit if:** §1.8 (accounts & sessions) lands, or multi-turn Socratic continuity becomes a test requirement. **Still open as of 2026-06-22** — check `api/agents/tier2/socratic.py::_extract_prior_turns` before extending Socratic mode further.

### ADR-010 — WritingAgent `@tool` decorators deferred
- **Status:** ASSUMED (partially open)
- **Context:** `agent-composability.md` requires tools declared via `@tool` decorators per agent. WritingAgent, LearningAgent, SocraticAgent expose zero `@tool`-decorated methods; `route_to_agent` calls `agent.run()` directly, so these agents are invisible to LLM-driven tool dispatch.
- **Decision:** Defer `@tool` decoration. Runtime behaviour is correct; the structural gap is non-breaking for P1 graded work.
- **Why:** Adding `@tool` decorators requires restructuring three agents simultaneously (schema inference from type hints, tool registration, `run()` forwarding) — doing it mid-slice would widen the diff with no P1 functional gain.
- **Revisit if:** LLM-driven tool dispatch is wired, or the evaluation benchmark requires per-agent tool specs. **Still open as of 2026-06-22** — verify against the current agent roster before assuming this is closed.

### ADR-011 — FR-WRT-01 is an assumed identifier (not in `arcana_prd.md`)
- **Status:** ASSUMED
- **Context:** `api/agents/tier2/writing.py` and related files referenced `FR-WRT-01`. Code-reviewer confirmed this ID does not exist in `docs/arcana_prd.md` — Writing mode is described in PRD §12.5 (Writing Agent) and Epic D, but no `FR-WRT-*` series exists.
- **Decision:** Remove `FR-WRT-01` from code comments; use "PRD §12.5 Writing Agent" as the reference instead.
- **Why:** The CLAUDE.md definition of done requires commit messages and docstrings to cite real FR/NFR IDs — invented IDs break traceability.
- **Revisit if:** `docs/arcana_prd.md` is updated to formally number writing requirements as `FR-WRT-01..N`.

### ADR-012 — StudyPlannerAgent exemption from `hybrid_retrieve` (invariant #1)
- **Status:** ASSUMED
- **Context:** `StudyPlannerAgent` (Tier-4) performs pure deterministic scheduling — no content generation, no LLM call, no synthesis. It only re-filters `Flashcard` objects already grounded by `LearningAgent` earlier in the same turn.
- **Decision:** Exempt `StudyPlannerAgent` from invariant #1 (ground before generating). Calling `hybrid_retrieve(top_k=1)` would add latency/cost with zero semantic benefit and require wiring three retriever dependencies into a stateless post-processing utility agent.
- **Why:** The agent emits no new knowledge claims — all cards originated from `LearningAgent`, which DID extend `retrieved_ctx`. `state.retrieved_ctx` is intentionally not extended by this agent; the traceability gap is acceptable for that reason.
- **Rejected:** Wiring `VectorStore`/`GraphStore`/`DocStore` into `StudyPlannerAgent` just to satisfy the letter of invariant #1 with no behavioural benefit.
- **Revisit if:** Surface at FYP-2 checkpoint for reviewer sign-off — this is a deliberate, documented exemption, not an oversight, but it should be defensible to a grader cold-reading invariant #1. Also: add `reviewedCount` to `StudyPlannerData` once frontend session-tracking lands (progress bar removed from `StudyPlanner.tsx` pending that field).

### ADR-013 — All three ML Engines (Re-Rank / Mastery / Document Classifier) deferred P1 → P2
- **Status:** DECIDED
- **Context:** `docs/arcana_prd.md` originally scoped the Re-Rank Engine as a P1 dependency (the other two Engines were already P2-leaning). Phase-1 has no trained-model infrastructure built, and training/serving one mid-FYP risked the release gate.
- **Decision:** Re-phase all three ML Engines (Re-Rank, Mastery, Document Classifier) and `FR-ENG-01..07` to P2 in `docs/arcana_prd.md` §12A, with a scope note that Phase-1's release gate (§24) no longer depends on any trained model — the §23.1 hybrid-vs-flat graph ablation stands alone as the retrieval-quality evidence. `Q-11` updated to record this as an author decision pending supervisor sign-off.
- **Why:** Removes a hard, schedule-risky dependency (data collection + training + serving) from the graded P1 submission without weakening the retrieval-quality claim, which the ablation alone already supports.
- **Rejected:** Building a minimal Re-Rank model just to satisfy the original P1 scoping — judged not worth the schedule risk for a component the release gate doesn't strictly need.
- **Revisit if:** Supervisor sign-off requires an Engine pulled forward into the graded build (tracked as the open half of Q-11).

### ADR-014 — Remaining heavy/optional Phase-1 items deferred to P2 (Neo4j, OCR, Obsidian); YouTube ingest kept in P1
- **Status:** DECIDED
- **Context:** Checklist §1.13's batched finish plan had to draw a line between "ships with P1" and "P2 scope" for several remaining open items: the Neo4j `GraphStore` migration (R-06), OCR ingestion (FR-ING-04), Obsidian import/export (FR-EXP-05/06), and YouTube transcript ingest (FR-ING-03).
- **Decision:** Neo4j migration, OCR, and Obsidian import/export pushed to a new Phase-2 checklist section. YouTube transcript ingest stayed in P1 and was built in batch B1 (`api/ingestion/parsers/youtube.py`).
- **Why:** YouTube ingest was already low-cost (a `youtube-transcript-api` call, no OCR/vision pipeline, no new infra) and rounds out the ingestion story for the demo. Neo4j/OCR/Obsidian each require new infrastructure or service integration with no FYP-grading payoff proportional to the effort.
- **Revisit if:** P2 planning begins — these three are already the seed list for the next checklist phase.

### ADR-015 — Web Search agent built in P1 (resolves a checklist self-contradiction)
- **Status:** DECIDED
- **Context:** `docs/checklist.md` §1.5 contained two contradictory lines: one placed `web_search.py` under a P2 "→ P2" annotation, another listed Web Search as a P1 §1.5 item. The PRD's non-goal note (§12) scopes Web Search narrowly to academic discovery (Semantic Scholar / arXiv), not general web search.
- **Decision:** Build the Web Search agent in P1, scoped exactly to the PRD's academic-discovery non-goal boundary. New tier-4 `WebSearchAgent` (`api/agents/tier4/web_search.py`) queries Semantic Scholar and arXiv only, emits `SourceList`, reachable via a new `websearch` intent.
- **Why:** The CLAUDE.md doc-conflict protocol WAS followed: the contradiction was surfaced to the author as an explicit question (not resolved silently), and the author chose P1. Building it kept the agent roster growing toward the 25-agent target while staying inside the PRD's actual scope boundary (academic-only discovery, never general web search).
- **Revisit if:** Supervisor review prefers Web Search deferred to P2. The underlying checklist §1.5 contradiction is already resolved (the stale '→ P2' note is marked superseded; §1.5 + §1.13 now agree on P1).

### ADR-016 — Export uses hand-built stdlib generators, not reportlab/python-docx
- **Status:** DECIDED
- **Context:** Batch B4 needed PDF and DOCX report export (FR-EXP-01/02) plus BibTeX/RIS bibliography export (FR-EXP-08). The obvious libraries (`reportlab` for PDF, `python-docx` for DOCX) could not be installed in this environment's venv.
- **Decision:** Hand-build both generators against the file formats directly: a minimal xref-accurate single-page PDF writer and a zip/OOXML (WordprocessingML) DOCX writer, both in `api/export/document.py`, with no new dependencies. BibTeX/RIS in `api/export/bibliography.py` is plain string templating — no library was ever a candidate there.
- **Why:** The venv constraint was a hard blocker, not a preference; stdlib-only output is also fully unit-testable (byte-level assertions on the zip/xref structure) without needing to shell out to a renderer. Aligns with the project's general bias toward avoiding extra infrastructure where a free/zero-dependency path suffices.
- **Rejected:** Skipping DOCX/PDF export until the venv constraint is lifted — rejected because FR-EXP-01/02 were explicit P1 checklist items and the stdlib path was viable within the batch.
- **Revisit if:** A richer export format (multi-page PDF with proper pagination, styled DOCX with images) is required — at that point reconsider installing `reportlab`/`python-docx` in an environment that permits it, rather than extending the hand-built writers further.
