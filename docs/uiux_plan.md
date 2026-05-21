# Arcana — UI/UX Plan

> The design authority for Arcana's interface. Consolidates the GenUI protocol, design system, modes, component catalog, interface states, and flows into one place so the frontend can be built without cross-referencing five PRD sections. Companion to `arcana_prd.md` (§13 GenUI, §14 Frontend & Design System, §15 UX Flows), `project_file_structure.md` (`web/`), and `checklist.md` (§1.6 Generative UI). Referenced from `CLAUDE.md`.
>
> **Order of authority:** the PRD remains the spec. Where this plan adds detail (exact token values, per-component state notes), it elaborates the PRD without contradicting it. If a value here ever conflicts with the PRD, the PRD wins on intent and this file is corrected. The interactive reference is `arcana_mockup_v3.html` — it demonstrates the design language and 11 of the 24 components in motion.

---

## 1. Design philosophy

Arcana is a **calm, scholarly tool**, not a flashy AI product. The interface should feel like good academic stationery — paper-like surfaces, restrained colour, generous whitespace, legible typographic hierarchy. The novelty is behavioural (the interface reshapes itself per task), not decorative.

Five principles govern every screen (PRD §14.5):

1. **Stable mental model, dynamic content.** The three-panel frame is a constant; only the contents and proportions adapt. The user is never dropped into a wholly unfamiliar screen.
2. **Structure before content.** Streamed components appear as skeletons immediately, so the page has shape within a second. Perceived performance beats raw latency (NFR-PERF-01).
3. **Provenance is always one click away.** Every citation resolves to the exact source passage. Trust is a first-class goal inherited from VERA AI.
4. **Calm density.** Hierarchy and whitespace over chrome. Colour is reserved for meaning, never decoration.
5. **Laptop-first, responsive-aware.** The primary target is a laptop browser; the shell degrades to a single-column stack on narrow viewports. Mobile is not a graded deliverable.

---

## 2. Design tokens

A small, deliberate set so the interface reads as one tool. These are the values used in the reference mockup; mirror them in `web/tailwind.config.ts` and `web/app/globals.css` as CSS custom properties. (Reconciles and makes concrete PRD §14.4.)

### 2.1 Colour

| Token | Value | Use |
| --- | --- | --- |
| `--paper` | `#faf8f4` | App canvas (warm near-white, paper-like) |
| `--card` | `#ffffff` | Card / panel surfaces |
| `--ink` | `#23211c` | Primary text |
| `--ink-soft` | `#6b6657` | Secondary text |
| `--ink-softer` | `#9c9686` | Tertiary / placeholder text |
| `--line` | `#e2ddd2` | Borders, dividers (subtle slate-warm) |
| `--accent` | `#2f5fa8` | Primary action, links, focus |

**Semantic colour encodes state, not decoration.** Each has a paired tint background for chips/cells:

| Meaning | Fg token | Bg token | Used for |
| --- | --- | --- | --- |
| Grounded / verified | `--green` `#3d7a52` | `--green-bg` `#eaf3ec` | Verified citations, "grounded" badges |
| Unverified / caution | `--amber` `#9a6b18` | `--amber-bg` `#f7efdc` | Claims awaiting fact-check |
| Contradiction / error | `--red` `#a8423a` | `--red-bg` `#f7e8e6` | Source disagreement, errors |
| Reasoning / meta | `--violet` `#6a4ea8` | `--violet-bg` `#f0ecf7` | Agent-tier accents, concept links |

> **Agent-tier accents** (used in the agent trace and component headers): Tier 1 Orchestration → accent blue · Tier 2 Core Intelligence → green · Tier 3 Output → violet · Tier 4 Quality/Meta → amber. Keep these consistent between the trace UI and any tier-coloured component chrome.

### 2.2 Typography

| Token | Family | Use |
| --- | --- | --- |
| `--sans` | Inter | UI chrome, controls, labels |
| `--serif` | Source Serif 4 | Long-form reading (summaries, drafts, dialog) |
| `--display` | Fraunces | Display headings, mode titles, empty-state hero |
| `--mono` | JetBrains Mono | Citations, code, tool-call signatures, IDs |

**Type scale:** 12 / 14 / 16 / 20 / 28 / 36 px on a 1.25 ratio. Body reading text is Source Serif at 16px; UI labels are Inter at 12–14px.

### 2.3 Space, shape, motion

| Group | Values |
| --- | --- |
| Spacing | 4-px base grid: 4, 8, 12, 16, 24, 32, 48 |
| Radius | `--r-ctl` 6px (controls) · `--r-card` 10px (cards) · `--r-panel` 14px (panels) |
| Shadow | `--shadow-sm` (hairline) · `--shadow` (resting card) · `--shadow-pop` (raised / menu / dialog) |
| Motion | 120–200 ms panel/width transitions; component hydrate fades ~150 ms; **respects `prefers-reduced-motion`** (disable width animation and shimmer, snap to final state) |

---

## 3. The adaptive three-panel shell

The shell is the constant frame. Three panels, left to right:

| Panel | Role | `web/components/shell/` |
| --- | --- | --- |
| **Sources** | Ingested documents, per-item ingestion status, the `SourceList` | `SourcesPanel.tsx` |
| **Chat** | Message input + the streamed-block column (the conversational spine) | `ChatPanel.tsx` |
| **Studio** | Graph / review / canvas — the working surface that expands per mode | `StudioPanel.tsx` |

Supporting shell pieces: `ModeIndicator.tsx` (shows the active mode and lets the user override it — FR-UI-07) and `PanelResizer.tsx` (manual resize → records an override in `uiStore`).

**How layout is decided.** The **UI Agent** computes panel widths and visibility per turn from intent + mode + history (PRD §13.4). The shell (`notebooks/[id]/layout.tsx`) reads widths from `uiStore` and applies the agent's choice **unless the user has set an override**, in which case the override wins for the rest of the session (FR-UI-07). Adaptation never fights the user.

**Width transitions animate** (120–200 ms) so the reshape is legible — the user sees the workspace change shape rather than teleport. Under `prefers-reduced-motion`, snap instead.

---

## 4. The five demonstrated modes

Modes are **samples from a continuous design space**, not a fixed menu (PRD §13.4). The UI Agent can blend them or compose a one-off task view ("thesis-defence rehearsal", "systematic-review screening") with no new code. These five are what the FYP demonstrates; ship **≥ 3** (Research, Study, Writing) and demonstrate all five (FR-UI-06).

| Mode | Sources | Chat | Studio | Primary components |
| --- | --- | --- | --- | --- |
| **Research** | papers list (~20%) | dense (~45%) | clustered graph (~35%) | `CitedSummary`, `LiteratureMatrix`, `ContradictionAlert` |
| **Study** | collapsed strip | cards (~45%) | SR review + planner (expanded) | `FlashcardDeck`, `QuizCard`, `BlurtingPrompt` |
| **Writing** | sources | maximised draft space | hidden | `DraftEditor`, `CitationPreview`, `PlagiarismReport` |
| **Socratic** | sources | dialog | concept-relationship graph | `SocraticDialog`, `FeynmanExplainer`, `ConceptMap` |
| **Exploration** | hidden | narrow | full-canvas interactive graph | `InsightCard`, `GapAnalysis` |

**Intent vs mode (the distinction that makes GenUI work, PRD §11A.4):**
- **Intent** = "what work needs doing?" → drives *which agents run*.
- **Mode** = "what should the workspace look like?" → drives *the UI Agent's component selection and layout*.
- The *same* research reasoning renders as a `CitedSummary` in Research, a `FlashcardDeck` in Study, or a `DraftEditor` in Writing — identical agents, different presentation (PRD §13.6). Build agents to produce **data**; let the UI Agent decide **form**.

---

## 5. The 24-component catalog

The catalog is the vocabulary of the interface. Each entry is one typed React component in `web/components/genui/<Name>.tsx`, registered with a single line in `registry.ts`. The component receives a typed `data` payload (defined in `packages/schema/payloads.ts`) plus `meta` (target panel, order, complexity). **The renderer never hand-switches on type** — it looks the type up in the registry (PRD §14.2, NFR-MNT-02).

| Component | Purpose | Produced by | Panel | Phase |
| --- | --- | --- | --- | --- |
| `CitedSummary` | Grounded answer with inline source citations | Research | chat | P0 |
| `LiteratureMatrix` | Papers × dimensions comparison grid | Research | studio/chat | P1 |
| `ContradictionAlert` | Flags where sources disagree on a concept | Research / Graph | chat | P1 |
| `GapAnalysis` | What the corpus does not cover | Research | studio | P1 |
| `InsightCard` | A surfaced serendipitous cross-document link | Discovery | chat/studio | P1 |
| `KnowledgeGraphView` | Interactive entity/edge graph (≤500 nodes < 2s) | Graph / Visual | studio | P1 |
| `ConceptMap` | Concept-relationship map for reasoning | Visual / Socratic | studio | P1 |
| `ComparisonChart` | Chart of structured comparative data | Visual | chat/studio | P1 |
| `Timeline` | Chronological event view | Visual | studio | P1 |
| `DataTable` | Sortable structured table | Visual | chat | P1 |
| `FlashcardDeck` | Active-recall cards with SR scheduling | Learning | chat/studio | P1 |
| `QuizCard` | MCQ / short-answer question item | Learning | chat | P1 |
| `BlurtingPrompt` | Free-recall prompt + comparison to source | Learning | chat | P1 |
| `FeynmanExplainer` | Simplified explanation + flagged gaps | Learning | chat | P1 |
| `CornellNotes` | Cue / notes / summary structured note | Learning | studio | P1 |
| `SocraticDialog` | Guided questioning that withholds answers | Socratic Tutor | chat | P1 |
| `StudyPlanner` | Schedule, Pomodoro and review queue | Study Planner | studio | P1 |
| `DraftEditor` | Editable grounded draft with citations | Writing | chat | P1 |
| `CitationPreview` | Formatted citation in chosen style | Citation | chat | P1 |
| `PlagiarismReport` | Originality and AI-content flags | Plagiarism | studio | P2 |
| `BibliographyExport` | BibTeX / RIS export panel | Citation | studio | P1 |
| `SourceList` | The notebook's ingested sources | Ingestion | sources | P0 |
| `ProgressDashboard` | Learning-progress and retention metrics | Analytics | studio | P1 |
| `AudioSummary` | Player for an audio overview | Audio | studio | P2 |

**The three-step rule for adding a component (never skip a step, never reorder):**
1. Add its `data` interface to `packages/schema/payloads.ts` and a variant to the `UIBlock` union in `blocks.ts`.
2. Create `web/components/genui/<Name>.tsx` implementing all four states.
3. Add one line to `web/components/genui/registry.ts`.

---

## 6. Interface states — every component implements all four

A streaming, agent-driven interface only feels predictable if every component defines its states explicitly. **Every catalog component MUST implement all four** via the shared `BlockStates.tsx` wrappers (NFR-USE-02, FR-UI-09). A component that cannot render a skeleton is not done.

| State | What the user sees | Example |
| --- | --- | --- |
| **Empty** | A clear prompt to act — never a blank panel | New notebook → "Add your first source" |
| **Loading** | An immediate skeleton matching the component's final shape | `CitedSummary` skeleton with shimmer lines |
| **Partial** | Real data filling in as agents complete | Matrix rows appearing one source at a time |
| **Error** | Plain-language cause + a retry affordance | "Couldn't read this PDF — it may be scanned. Retry with OCR?" |

**Streaming lifecycle** (PRD §13.2): agent emits block → server validates (fail closed) → SSE event → client resolves type via registry and mounts a **skeleton** → client **hydrates** as data arrives → panel widths animate to the new layout. Skeleton-first is why the user sees structure within the first second.

---

## 7. Key flows

### 7.1 First-run / activation (tracked metric ≥ 90%) — PRD §15.1
1. Sign in (Google OAuth or email) → land on an **empty notebook** with one clear CTA: **add sources**.
2. Drag-and-drop or pick PDFs/DOCX, or paste a URL → each source shows a **per-item ingestion progress** state.
3. On first successful ingest, the Chat panel surfaces **three suggested cross-document questions** drawn from the new graph.
4. The user asks (or taps a suggestion) → the first `CitedSummary` streams in → **activation achieved.**

> This flow is the single most important screen to get right and is **not yet dramatised in the mockup** — build it deliberately.

### 7.2 Core research flow — PRD §15.2
Query → Orchestrator detects research intent → hybrid retrieval → Research Agent synthesises with grounding → Fact Checker verifies → UI Agent streams `CitedSummary` + `LiteratureMatrix` + `KnowledgeGraphView` while the shell animates into **Research mode**. Any citation opens its source; the user can pivot to Writing mode to draft from the result.

### 7.3 Study flow — PRD §15.3
Topic or document → Learning Agent generates a `FlashcardDeck` → cards enter spaced-repetition scheduling → each review updates the schedule (FSRS/SM-2, Q-04) → `ProgressDashboard` reflects retention over time. The Socratic Tutor can be invoked to probe understanding rather than reveal answers.

### 7.4 Error & degradation UX — PRD §15.5
Failures are designed for, not hidden. A failed ingest is reported per item with cause + retry (FR-ING-08). A retriever outage degrades quietly — the answer still streams with a subtle note that graph context was unavailable (NFR-REL-01). An LLM provider failure is invisible (the fallback takes over, NFR-REL-02). The system always returns something honest rather than failing silently.

> Degradation states are also **not yet dramatised in the mockup** — specify the subtle "graph context unavailable" note and the per-item ingest-error card during the build.

---

## 8. The agent trace (transparency surface)

A defining, demonstrable feature: the user can watch the pipeline work. As the turn runs, a compact trace ticks through Orchestrator → specialist(s) → Fact Checker → UI Agent, with **A2A hop badges** when one agent calls another via `route_to_agent`. Colour the trace by agent tier (§2.1). This makes composability visible (it is the FYP's defining engineering claim) and doubles as honest "loading" feedback. Keep it compact and dismissible — it informs without dominating.

---

## 9. Accessibility & responsiveness

- **Focus & keyboard:** all controls reachable and operable by keyboard; visible focus ring in `--accent`. Citation links and flashcard flip are keyboard-actionable.
- **Contrast:** body text meets WCAG AA against `--paper`/`--card`. Semantic colours are never the *only* signal — pair with an icon or label (e.g. contradiction = red + an alert glyph).
- **Motion:** honour `prefers-reduced-motion` — disable width animations and shimmer, snap to final layout.
- **Responsive:** laptop-first. Below the breakpoint, panels collapse to a single-column stack (Chat primary; Sources and Studio become toggleable sheets). Mobile is not graded but must not break.

---

## 10. What the mockup proves vs. what's still to build

**`arcana_mockup_v3.html` demonstrates** (use it as the visual reference): the three-panel shell with animated mode reshaping across all five modes, the live agent-pipeline trace with A2A hop badges, skeleton→hydrate streaming, and **11 of the 24 components** — `CitedSummary`, `LiteratureMatrix`, `ContradictionAlert`, `GapAnalysis`, `InsightCard`, `ConceptMap`, `FlashcardDeck`, `QuizCard`, `SocraticDialog`, `DraftEditor`, `CitationPreview`.

**Still to build for parity with this plan:**
- The remaining **13 catalog components** (notably `KnowledgeGraphView`, `ComparisonChart`, `Timeline`, `DataTable`, `BlurtingPrompt`, `FeynmanExplainer`, `CornellNotes`, `StudyPlanner`, `ProgressDashboard`, `SourceList`, `BibliographyExport`, plus P2 `PlagiarismReport`, `AudioSummary`).
- The **first-run / activation flow** (§7.1) and the **error/degradation states** (§7.4) — specified but not yet dramatised.
- The four-state implementation for **every** component via `BlockStates.tsx`.

---

*Companion to `arcana_prd.md` (§13–§15), `project_file_structure.md` (`web/`), and `checklist.md` (§1.6). Reference implementation: `arcana_mockup_v3.html`. Keep token values in sync with `web/tailwind.config.ts` and the component list in sync with the PRD §13.3 catalog.*
