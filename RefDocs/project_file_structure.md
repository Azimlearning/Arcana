# Arcana — Project File Structure

> Canonical repository layout for Arcana. Companion to `arcana_prd.md` (the full spec) and `checklist.md` (the phased build plan). Referenced from `CLAUDE.md`.
>
> **Read this before creating or moving any file.** The directory boundaries here are also architectural boundaries — they encode the one-directional dependency rule (`routes → agents → retrieval/stores → llm`) and the shared-schema seam that prevents backend/frontend payload drift.

---

## 0. Top-level monorepo

Arcana is a monorepo with two deployable applications and one shared schema package. The split mirrors the runtime boundary: `api/` owns orchestration, retrieval and the knowledge stores; `web/` owns the GenUI catalog and the adaptive shell; `packages/schema/` is the single source of truth for the wire contract between them.

```
arcana/
├── api/                 # FastAPI backend (Python 3.11) — all reasoning lives here
├── web/                 # Next.js 14 frontend (TypeScript) — rendering only, no business logic
├── packages/
│   └── schema/          # SHARED block & API types — source of truth, generated into TS + Python
├── eval/                # benchmark harness + the 20-question cross-document set
├── infra/               # docker-compose, env templates, deploy scripts
├── docs/                # arcana_prd.md, project_file_structure.md, checklist.md, concept doc
├── CLAUDE.md            # agent operating instructions (points at the docs above)
├── README.md
├── .env.example         # every env var, documented, no secrets
├── .gitignore           # .env, __pycache__, node_modules, .next, *.pyc
└── Makefile / justfile  # dev shortcuts: up, test, lint, ingest-demo, bench
```

**Golden rules (enforced in review):**
1. A type that crosses the wire is defined in `packages/schema/` **first**, then imported by both sides. Never define a `UIBlock` variant in only one place.
2. Backend dependency direction is one-way: `routes/ → agents/ → retrieval/ + stores/ → llm/`. Lower layers never import upper layers.
3. Agents depend on **abstractions** (`GraphStore`, `VectorStore`, `DocStore`), never on a concrete backend module.
4. No secret literal anywhere in source — everything via `api/core/settings.py`.
5. The frontend renderer never `switch`es on block type by hand — it goes through `web/components/genui/registry.ts`.

---

## 1. Backend — `api/`

FastAPI, async throughout. A chat turn fans out into many concurrent I/O calls (three retrievers, several LLM completions, graph queries) and streams partial results back, so every layer that touches I/O is `async`.

```
api/
├── main.py                      # app factory: mounts routers, lifespan (warm stores/LLM clients)
├── pyproject.toml               # deps: fastapi, uvicorn, langgraph, anthropic, pinecone-client,
│                                #       neo4j, networkx, pymupdf, rank-bm25, firebase-admin, pydantic
│
├── core/                        # cross-cutting foundation (no business logic)
│   ├── settings.py              # typed Settings(BaseSettings) — env profiles: local/study/prod-design
│   ├── auth.py                  # current_user dependency: verifies Firebase ID token  [NFR-SEC-01]
│   ├── logging.py               # structured JSON logging; request + agent trace ids
│   ├── errors.py                # error envelope, exception handlers, AllProvidersFailed, etc.
│   └── budget.py                # TokenBudget + charge_hop() — guards cost & recursion  [§11.6]
│
├── ingestion/                   # raw files/URLs → chunks + embeddings + graph triples  [§12 Ingestion Agent]
│   ├── pipeline.py              # orchestrates: parse → chunk → embed → upsert vectors → extract → build graph
│   ├── parsers/
│   │   ├── pdf.py               # PyMuPDF text extraction; routes scanned PDFs to OCR  [FR-ING-01,04]
│   │   ├── docx.py              # DOCX text extraction                                  [FR-ING-01]
│   │   ├── web.py               # readable web-page content extraction                  [FR-ING-02]
│   │   └── youtube.py           # transcript fetch + parse                              [FR-ING-03]
│   ├── ocr.py                   # OCR for scanned/image PDFs                            [FR-ING-04]
│   ├── chunker.py               # semantic + fixed-window chunking                      [FR-ING-05]
│   ├── embedder.py              # OpenAI text-embedding-3-large client (3072-dim)       [FR-ING-05]
│   └── extractor.py             # LLM entity/relationship extraction → typed Triples    [FR-ING-06,09]
│
├── stores/                      # storage abstractions — the migration seam            [FR-KG-07, R-06]
│   ├── graph_store.py           # GraphStore ABC: upsert_node/edge, expand, shortest_path,
│   │                            #   communities (Louvain), pagerank                     [Listing 10.3]
│   ├── networkx_store.py        # NetworkXGraphStore — FYP 1 prototype, in-process      [P0]
│   ├── neo4j_store.py           # Neo4jGraphStore — Phase 1 production target           [P1]
│   ├── vector_store.py          # VectorStore ABC + Pinecone impl (3072-dim index)
│   └── doc_store.py             # DocStore: Firestore metadata + object storage for raw files
│
├── retrieval/                   # three retrievers + RRF fusion behind one entry point  [§10.4]
│   ├── vector.py                # dense vector search over Pinecone                     [FR-RET-01]
│   ├── bm25.py                  # BM25 keyword search                                   [FR-RET-02]
│   ├── graph.py                 # multi-hop graph traversal (uses GraphStore)           [FR-RET-03]
│   ├── fusion.py                # reciprocal_rank_fusion(rankings, k=60)                [FR-RET-04]
│   └── hybrid.py                # hybrid_retrieve(): asyncio.gather all 3 → RRF → top_k  [Listing 10.4]
│                                #   wraps each retriever so one failure → empty slot     [NFR-REL-01]
│
├── agents/                      # the 25-agent suite + orchestration                    [§12]
│   ├── base.py                  # BaseAgent, the @tool decorator (schema from type hints),
│   │                            #   the tool registry, route_to_agent()                 [§11.3, 11.4]
│   ├── orchestrator.py          # Tier 1: intent/mode detect → plan → route → assemble   [P0]
│   ├── tier2/                   # Core Intelligence
│   │   ├── research.py          #   Research Agent                                       [P0]
│   │   ├── graph_agent.py       #   Graph Agent                                          [P0]
│   │   ├── learning.py          #   Learning Agent                                       [P1]
│   │   ├── writing.py           #   Writing Agent                                        [P1]
│   │   ├── socratic.py          #   Socratic Tutor                                       [P1]
│   │   ├── discovery.py         #   Discovery Agent                                      [P1]
│   │   ├── methodology.py       #   Methodology Agent                                    [P2]
│   │   └── debate.py            #   Debate Agent                                         [P2]
│   ├── tier3/                   # Output Generation
│   │   ├── ui_agent.py          #   UI Agent — the ONLY agent that picks components      [P1]
│   │   ├── citation.py          #   Citation Agent                                       [P1]
│   │   ├── visual.py            #   Visual Agent                                         [P1]
│   │   ├── document.py          #   Document Agent (PDF/DOCX/PPTX export)                [P1]
│   │   └── audio.py             #   Audio Agent                                          [P2]
│   ├── tier4/                   # Quality & Meta
│   │   ├── fact_checker.py      #   Fact Checker                                         [P1]
│   │   ├── annotation.py        #   Annotation Agent                                     [P1]
│   │   ├── memory.py            #   Memory Agent (loaded at start of every turn)         [P1]
│   │   ├── ingestion_agent.py   #   Ingestion Agent (wraps ingestion/ as tools)          [P0]
│   │   ├── web_search.py        #   Web Search Agent (academic discovery only)           [P1]
│   │   ├── study_planner.py     #   Study Planner                                        [P1]
│   │   ├── plagiarism.py        #   Plagiarism Agent                                     [P2]
│   │   ├── grammar_style.py     #   Grammar & Style Agent                                [P2]
│   │   ├── paraphrase.py        #   Paraphrase Agent                                     [P2]
│   │   ├── export_agent.py      #   Export Agent                                         [P2]
│   │   └── analytics.py         #   Analytics Agent (feeds the FYP evaluation)           [P1]
│   └── graph.py                 # LangGraph StateGraph assembly: AgentState, nodes,      [§11.1, FR-AGT-04]
│                                #   conditional routing, terminal join to UI Agent
│
├── genui/                       # server-side GenUI protocol
│   ├── blocks.py                # Pydantic UIBlock models — IMPORT shapes from packages/schema  [§13.1]
│   ├── validate.py              # validate every block before streaming (fail closed)    [NFR-SEC-04, R-10]
│   └── streamer.py              # SSE block streamer
│
├── llm/                         # provider-agnostic LLM seam
│   ├── service.py               # LLMService.complete(messages, tools, model) + fallback  [Listing 10.2]
│   ├── providers/
│   │   ├── anthropic.py         #   Claude (primary)
│   │   └── openrouter.py        #   OpenRouter (fallback)                                [NFR-REL-02]
│   └── prompts/                 # versioned prompt templates (extraction, layout, synthesis)
│
└── routes/                      # HTTP entry points (top of the dependency chain)
    ├── chat.py                  # POST /chat — SSE stream of UIBlocks                    [Listing 10.1]
    ├── ingest.py                # POST /ingest — upload / URL ingestion + progress       [FR-ING-07]
    ├── graph.py                 # GET /graph — interactive graph data                    [FR-KG-08]
    ├── notebooks.py             # CRUD notebooks                                         [FR-USR-03]
    └── auth.py                  # session / token endpoints
```

### Backend notes
- **`agents/base.py` is the keystone.** The `@tool` decorator does double duty: it produces the JSON schema the LLM sees and registers the type hints the runtime validates against. `route_to_agent` lives here and is what makes any agent callable as a tool by any other agent.
- **`agents/graph.py` (LangGraph assembly) is distinct from `agents/tier2/graph_agent.py` (the knowledge-Graph Agent)** and from `stores/graph_store.py` (storage). Keep the names straight: *graph.py* = execution graph; *graph_agent.py* = the agent; *graph_store.py* = persistence; *retrieval/graph.py* = traversal retriever.
- **Phase tags** in comments mirror §12. When building for FYP 2 (P1), the P2 agent files may exist as stubs that raise `NotImplementedError` or simply be absent until scheduled.

---

## 2. Frontend — `web/`

Next.js 14 App Router, TypeScript, Tailwind CSS, Vercel AI SDK. **No business logic** — it renders the adaptive three-panel shell, hosts the trusted component catalog, and manages UI/session state. All reasoning is in `api/`.

```
web/
├── package.json                 # next@14, react, tailwindcss, ai (Vercel AI SDK),
│                                #   zustand, firebase, d3 / react-force-graph (graph view)
├── next.config.js
├── tailwind.config.ts           # design tokens from §14.4 (fonts, scale, spacing, radius, colour)
├── tsconfig.json                # path alias "@/schema" → ../packages/schema
│
├── app/                         # App Router
│   ├── layout.tsx               # root layout, fonts (Inter, Source Serif, JetBrains Mono)
│   ├── globals.css              # token CSS vars; prefers-reduced-motion handling
│   ├── (auth)/
│   │   └── login/page.tsx       # Firebase auth (email + Google OAuth)                  [FR-USR-01]
│   ├── notebooks/
│   │   ├── page.tsx             # notebook list / create                                [FR-USR-03]
│   │   └── [id]/
│   │       ├── layout.tsx       # the 3-panel adaptive shell                            [FR-UI-01,05]
│   │       └── page.tsx         # chat input + block-stream consumer                    [FR-UI-03]
│   └── api/                     # (thin Next route handlers if any; most calls hit FastAPI directly)
│
├── components/
│   ├── shell/                   # the stable frame — never disorients the user          [§14.5]
│   │   ├── SourcesPanel.tsx     #   ingested sources; collapses in Study/Exploration
│   │   ├── ChatPanel.tsx        #   message + streamed-block column
│   │   ├── StudioPanel.tsx      #   graph / review / canvas; expands per mode
│   │   ├── ModeIndicator.tsx    #   shows + lets user override the active mode          [FR-UI-07]
│   │   └── PanelResizer.tsx     #   manual resize → records override in uiStore
│   │
│   ├── genui/                   # the 24-component catalog — one file each               [§13.3, FR-UI-02]
│   │   ├── registry.ts          #   type → component map; renderBlock()                 [Listing 14.2]
│   │   ├── BlockStates.tsx      #   shared Empty / Loading / Partial / Error wrappers    [NFR-USE-02]
│   │   ├── CitedSummary.tsx
│   │   ├── LiteratureMatrix.tsx
│   │   ├── ContradictionAlert.tsx
│   │   ├── GapAnalysis.tsx
│   │   ├── InsightCard.tsx
│   │   ├── KnowledgeGraphView.tsx   # interactive force graph, up to 500 nodes < 2s     [NFR-PERF-04]
│   │   ├── ConceptMap.tsx
│   │   ├── ComparisonChart.tsx
│   │   ├── Timeline.tsx
│   │   ├── DataTable.tsx
│   │   ├── FlashcardDeck.tsx
│   │   ├── QuizCard.tsx
│   │   ├── BlurtingPrompt.tsx
│   │   ├── FeynmanExplainer.tsx
│   │   ├── CornellNotes.tsx
│   │   ├── SocraticDialog.tsx
│   │   ├── StudyPlanner.tsx
│   │   ├── DraftEditor.tsx
│   │   ├── CitationPreview.tsx
│   │   ├── PlagiarismReport.tsx
│   │   ├── BibliographyExport.tsx
│   │   ├── SourceList.tsx
│   │   ├── ProgressDashboard.tsx
│   │   └── AudioSummary.tsx      # P2
│   │
│   └── ui/                       # primitives (Button, Skeleton, Card, Tooltip…)
│
├── lib/
│   ├── stream.ts                # SSE → UIBlock[] consumer via the AI SDK              [§13.2]
│   ├── api.ts                   # typed fetch client; attaches Firebase token
│   └── firebase.ts              # client SDK init
│
└── store/                       # Zustand                                              [§14.3]
    ├── uiStore.ts               #   active mode, panel widths, overrides, animation
    ├── sessionStore.ts          #   notebook, message history, auth user
    └── blockStore.ts            #   streamed blocks for the active turn, by panel + order
```

### Frontend notes
- **Adding a catalog component is a two-step change** (NFR-MNT-02): create `components/genui/<Name>.tsx`, then add one line to `registry.ts`. Nothing else should need to change — this is the property that lets the UI Agent expand the interface space.
- **Every catalog component must implement the four states** (Empty / Loading / Partial / Error) via `BlockStates.tsx`. A component that can't render a skeleton fails NFR-USE-02 and FR-UI-09.
- The shell layout (`notebooks/[id]/layout.tsx`) reads panel widths from `uiStore`; the UI Agent's chosen widths are applied unless the user has set an override.

---

## 3. Shared schema — `packages/schema/`

The **single source of truth** for everything that crosses the wire. Defined here once, generated/imported into both TypeScript (frontend) and Python (backend) so a block's payload shape can never silently drift (R-10).

```
packages/schema/
├── package.json
├── blocks.ts                    # UIBlock tagged union + BlockMeta                     [Listing 13.1]
├── payloads.ts                  # CitedSummaryData, MatrixData, FlashcardDeckData,      [§16.1]
│                                #   SocraticDialogData, PlagiarismReportData, …
├── api.ts                       # ChatRequest, IngestRequest, AgentResult, etc.
├── entities.ts                  # Document, Chunk, GraphNode, GraphEdge, Notebook,      [§19.1]
│                                #   UserProfile, ReviewState
└── codegen/
    └── to_python.ts             # emits Pydantic models into api/ (build step)
```

**Rule:** when you add a new GenUI component, add its `data` interface to `payloads.ts` and a new variant to the `UIBlock` union in `blocks.ts` *before* writing either the agent that produces it or the React component that renders it.

---

## 4. Evaluation — `eval/`

The benchmark harness. This produces the FYP's primary evidence (§23.1), so it is first-class, not a script in a corner.

```
eval/
├── corpus/                      # the fixed multi-document corpus (held constant)
├── questions.yaml               # the ~20 cross-document questions + gold answers       [Q-03]
├── baseline_flat_rag.py         # flat vector-RAG baseline (no graph traversal)
├── run_benchmark.py             # runs hybrid vs baseline; identical embeddings/corpus   [Listing 10.4]
├── metrics.py                   # answer accuracy, citation correctness, latency
└── report.py                    # tables/plots for the FYP 2 report
```

**Methodological guard (R-02):** the only variable between the two runs is whether `retrieval/graph.py` participates in fusion. Embeddings, corpus, chunking and questions are held constant. Pre-register `questions.yaml`.

---

## 5. Infrastructure — `infra/`

```
infra/
├── docker-compose.yml           # local stack: api, web, neo4j (optional), networkx is in-process
├── Dockerfile.api
├── Dockerfile.web
├── env/
│   ├── local.env.example        # NetworkX, in-memory caches, demo corpus
│   ├── study.env.example        # the config used for the user study + benchmark
│   └── prod-design.env.example  # Neo4j (documented, not required for the FYP)
└── deploy/                      # low-cost cloud deploy scripts (hosting TBD — Q-07)
```

---

## 6. Where things live — quick lookup

| If you are working on… | Go to |
| --- | --- |
| A new agent or tool call | `api/agents/tierN/<agent>.py`; register tools via `@tool` in `base.py` |
| Agent-to-agent invocation / recursion guard | `api/agents/base.py` (`route_to_agent`), `api/core/budget.py` |
| The LangGraph execution graph / shared state | `api/agents/graph.py` |
| Retrieval logic / RRF | `api/retrieval/` (`hybrid.py`, `fusion.py`) |
| Swapping NetworkX ↔ Neo4j | `api/stores/` (implement the `GraphStore` ABC); flip `graph_backend` in settings |
| Ingestion / a new file type | `api/ingestion/parsers/` + register in `pipeline.py` |
| A new GenUI component | `packages/schema/` (types) → `web/components/genui/<Name>.tsx` → `registry.ts` |
| The 3-panel shell / mode behaviour | `web/components/shell/` + `web/store/uiStore.ts` |
| The wire contract (any cross-boundary type) | `packages/schema/` — always here first |
| LLM provider / fallback / prompts | `api/llm/` |
| The benchmark | `eval/` |
| Env vars / secrets / profiles | `api/core/settings.py` + `infra/env/` + root `.env.example` |

---

*Companion to `arcana_prd.md` and `checklist.md`. Keep this file in sync with the PRD: if a module moves or a boundary changes, update both.*
