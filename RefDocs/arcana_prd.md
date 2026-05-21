# Arcana — Product Requirements Document (Engineering Edition)

> **The AI Research Assistant That Connects What Others Miss**
>
> Version 0.2 — Technical Expansion · May 2026
> Author: Fakhrul Azim Bin Ahmed Mardzukie · Universiti Teknologi PETRONAS
> Final Year Project · Companion to Concept Document v2.1
> Status: **DRAFT — source of truth for implementation**

---

## How to read this document (for the coding agent)

This is the canonical product + engineering specification for Arcana. It is written to be consumed directly during implementation: every requirement carries a stable ID, a priority, and a delivery phase, and every architectural claim is backed by a concrete code reference.

- **Requirement IDs** are stable. Reference them in commits and PRs (e.g. `feat(retrieval): RRF fusion — closes FR-RET-04`).
- **Priority (MoSCoW):** `M` = Must · `S` = Should · `C` = Could · `W` = Won't (this release).
- **Phase:** `P0` = FYP 1 Proof of Concept · `P1` = FYP 2 MVP (the graded build) · `P2` = post-FYP roadmap.
- **Companion files:** `project_file_structure.md` (the full repo tree, every file explained) and `checklist.md` (the phased build checklist derived from this PRD).
- **Code listings** in this document are illustrative contracts, not final code. They define the *shape* the implementation must honour — function signatures, schemas, data flow. They are finalised during system design but should not drift from what is written here without updating this PRD.

---

## 1. Document Control and Purpose

This PRD defines what Arcana must do, for whom, and to what engineering standard. It turns the vision in the Concept Document into concrete, testable requirements and a buildable engineering plan.

It covers the **full product vision** (the complete 25-agent platform) but marks every requirement with the release phase in which it is expected to be delivered, so "what Arcana will eventually be" is always separable from "what the FYP will demonstrate."

| Field | Detail |
| --- | --- |
| Document title | Arcana — Product Requirements Document (Engineering Edition) |
| Version | 0.2 (technical expansion) |
| Status | Draft — implementation source of truth |
| Author | Fakhrul Azim Bin Ahmed Mardzukie |
| Institution | Universiti Teknologi PETRONAS |
| Related documents | Arcana FYP Concept Document v2.1; VERA AI Project Summary (internal) |
| Intended readers | The implementing developer (and AI coding agent), supervisor, FYP examiners |

Sections most likely to evolve during implementation: §12 (Agent Specifications), §17 (Functional Requirements), §25 (Open Questions).

---

## 2. Executive Summary

Arcana is a **graph-native, multi-agent research and learning platform** for students and academic researchers. It ingests a user's documents — papers, reports, lecture notes, web pages — and turns them into a single connected knowledge base that can be queried, studied from, and written against.

**The problem.** Current retrieval-augmented assistants, including Google NotebookLM, treat each document as an isolated silo of vector chunks. They cannot answer questions that span sources, their agents cannot collaborate, and their interface is the same regardless of whether the user is reviewing literature, drafting a report, or revising for an exam.

**The product bet — three things, used together:**
1. **A knowledge graph** makes cross-document relationships — agreement, contradiction, influence — first-class and retrievable.
2. **A composable multi-agent system** lets specialised agents invoke one another, so a single request can be decomposed and solved autonomously.
3. **A Generative UI** assembles the interface per request from typed components, so the tool adapts to the user's task instead of the reverse.

**Why it is credible.** Arcana extends **VERA AI**, an enterprise RAG assistant the author built during a seven-month industrial placement, which reached 94% citation accuracy and cut retrieval time by 95%. Arcana reuses that proven baseline and pushes it forward with graph retrieval, agent composability, and adaptive UI.

**What the FYP will deliver (Phase 1 MVP):** full hybrid retrieval (graph + vector + BM25 + RRF), 15+ composable agents, a Generative UI with five demonstrated modes, an evidence-based learning module, and an empirical evaluation against a flat-RAG baseline and NotebookLM with a 10–15 participant user study.

---

## 3. Problem and Background

### 3.1 Background

Tools such as Google NotebookLM have made it normal to "chat with your sources" and set a baseline expectation: upload documents, ask questions, get grounded answers. Arcana accepts that baseline and targets the structural limitations that remain once it is met.

### 3.2 Problems Arcana Addresses

- **P1 — Flat, siloed knowledge.** Documents are stored as independently indexed vector chunks. Connections, contradictions, and themes across sources are invisible to the retriever. Global questions ("what do my sources collectively say about X?", "where do they disagree?") cannot be answered well.
- **P2 — Non-composable agents.** Where agents exist, they run in isolation and cannot delegate to each other. Multi-step tasks (drafting a literature review that needs both synthesis and fact-checking) must be manually broken down by the user.
- **P3 — Static, one-size-fits-all interfaces.** A fixed layout is shown regardless of task. Comparing papers, drafting a report, and making flashcards all get the same screen.
- **P4 — Research tools ignore learning science.** Existing tools help retrieve and summarise but do not help a student actually learn and retain material using evidence-based study methods.

### 3.3 Target Outcome

Arcana should let a user move from a pile of unconnected documents to genuine understanding — finding cross-source insight, producing grounded written work, and retaining knowledge — within a single tool that reshapes itself around whichever task the user is currently doing.

---

## 4. Goals, Non-Goals and Success Metrics

### 4.1 Product Goals
- Make cross-document relationships retrievable.
- Enable autonomous multi-step task completion through agents that invoke one another.
- Adapt the interface to the user's current task.
- Help users learn and retain, not just find, information.
- Demonstrate empirically that graph-augmented retrieval beats flat vector RAG for cross-document questions.

### 4.2 Non-Goals (this release)
- Real-time multi-user collaboration on a shared knowledge base.
- A native mobile application.
- Local or offline LLM inference.
- Video generation and animated explainers.
- General-purpose web search (Arcana reasons over the curated corpus; web search is limited to academic paper discovery).

### 4.3 Success Metrics

| Metric | Definition | Target |
| --- | --- | --- |
| **Cross-document retrieval accuracy (PRIMARY)** | Answer correctness on a benchmark of cross-document questions, hybrid retrieval vs flat vector-RAG baseline | Statistically significant improvement over baseline |
| Citation accuracy | Proportion of citations that correctly support the claim | ≥ 90% |
| Task completion rate | Core user-study tasks completed without facilitator intervention | ≥ 80% |
| Usability (SUS) | System Usability Scale score | ≥ 70 (good) |
| Time-to-insight | Time to answer a cross-document question vs manual / NotebookLM | Meaningful reduction |
| Activation | New user completes ingest → first grounded answer in session one | ≥ 90% of participants |
| Retrieval latency | Time to first streamed token for a standard query | < 3 s (see NFR-PERF-01) |

The primary metric is deliberately the academic one: the FYP is graded on a defensible contribution, and a rigorous retrieval benchmark is the strongest evidence Arcana can offer.

---

## 5. Target Users and Personas

| Attribute | Aisha — Undergraduate | Daniel — Postgraduate | Mei — Exam-Prep |
| --- | --- | --- | --- |
| Context | Final-year undergrad writing her FYP literature review | Master's student managing a large, growing thesis corpus | Undergrad revising dense modules before exams |
| Primary goal | Understand how 15–20 papers relate, agree, conflict; draft a review | Maintain a connected knowledge base; track gaps over months | Convert notes/readings into durable knowledge |
| Frustrations | Tools answer per-document; she connects ideas manually | Re-uploading, re-reading, losing context | Summaries help her read, not remember |
| Key Arcana value | Cross-document synthesis, contradiction reports, grounded drafts | Persistent graph, gap analysis, incremental updates | Flashcards + spaced repetition, quizzes, Socratic tutoring |
| Main modes | Research, Writing | Research, Exploration | Study, Socratic |

**Secondary persona — Dr. Rao (Supervising Academic):** may review a student's knowledge base. Arcana should be credible to such a reader (clear citations, transparent sourcing), but supervisor-specific features (oversight dashboards, cohort management) are out of scope.

### Jobs To Be Done
- When I have a stack of related documents, I want to see how they connect, so I understand the topic as a whole.
- When I'm writing, I want grounded, cited draft material from my sources, so I write faster without fabricating references.
- When I'm revising, I want my material turned into active-recall practice, so I retain it.
- When I return after days away, I want my knowledge base and context preserved.

---

## 6. User Stories (Epics)

Each epic maps to a functional-requirement group in §17.

**Epic A — Build the Knowledge Base.** Upload PDFs/DOCX; add web pages / YouTube by URL; see ingestion progress and failures.
**Epic B — Cross-Document Research.** Ask questions spanning all documents; see contradictions; ask what sources don't cover (gaps); explore the corpus as an interactive graph.
**Epic C — Study and Learning.** Generate flashcards; resurface them on a spaced-repetition schedule; take generated quizzes at chosen difficulty; be tutored with guiding questions rather than answers.
**Epic D — Writing and Drafting.** Generate a grounded draft section; have a draft checked against the knowledge base; export formatted citations and bibliographies.
**Epic E — Adaptive Interface.** Have the interface reshape around the current task; override the chosen layout when desired.
**Epic F — Continuity and Interoperability.** Persist knowledge base, history, and progress; import/export an Obsidian vault.

### Representative use case — Literature Review (the composability showcase)
Aisha uploads eighteen papers on GraphRAG. Arcana ingests them, extracts entities/relationships, and builds a knowledge graph. She asks: *"Write a literature review section on the limitations of GraphRAG."* The Orchestrator routes to the **Writing Agent**; the Writing Agent retrieves context through the hybrid pipeline, then invokes the **Research Agent** to compare contradictions across papers, which itself calls the **Graph Agent** for multi-hop context and the **Fact Checker** before returning a cited synthesis. The Writing Agent assembles a drafted section, streamed as a `DraftEditor` component with inline `CitationPreview` blocks, while the interface shifts into Writing mode. The whole task — synthesis, contradiction analysis, fact-checking, drafting — is decomposed and completed without manual orchestration. Traced step-by-step in §12.6.

---

## 7. Product Scope and Release Phasing

| Phase | Goal | Deliverables |
| --- | --- | --- |
| **P0 — FYP 1 PoC** | Prove the core technical premise | PDF/DOCX ingestion, KG construction, working hybrid-retrieval comparison demo, 3 core agents (Orchestrator, Research, Graph), NetworkX prototype graph store, FYP 1 report |
| **P1 — FYP 2 MVP (graded)** | A usable, evaluable product | Full hybrid RAG pipeline; 15+ composable agents with A2A invocation; GenUI streaming with 5 demonstrated modes; learning agent + spaced repetition; Neo4j migration; accounts + persistence; Obsidian import/export; empirical evaluation + user study |
| **P2 — Post-FYP** | Complete the vision | Full 25-agent suite; audio/video output; real-time collaboration; mobile app; Google Drive sync; deeper Anki/Obsidian; multi-language |

### In scope / out of scope for the FYP

| In scope (P0–P1) | Out of scope for the FYP |
| --- | --- |
| Ingestion: PDF, DOCX, web URL, YouTube transcript | Real-time collaborative multi-user knowledge bases |
| GraphRAG knowledge graph + hybrid retrieval | Native mobile application |
| 15+ composable agents with agent-to-agent calls | Local / offline LLM inference |
| Generative UI with 5 demonstrated modes | Video generation and animated explainers |
| 8 evidence-based study methods | Multi-language translation |
| Quantitative benchmark + 10–15 user study | Audio output as a graded deliverable (roadmap only) |
| Obsidian vault import / export | Full 25-agent suite as a graded deliverable |

---

## 8. System Architecture Overview

Arcana is organised as **six layers plus a cross-cutting LLM service**. A request flows down from the client through the API into agent orchestration, which draws on hybrid retrieval over the knowledge stores; documents enter through the ingestion pipeline; the LLM is used by ingestion (entity extraction), retrieval (synthesis), and every agent (reasoning).

```
┌─────────────────────────────────────────────────────────────┐
│  CLIENT / PRESENTATION                                        │
│  Next.js 14 · adaptive 3-panel shell · 24-component catalog   │
└───────────────────────────────┬─────────────────────────────┘
                                 │  HTTP + SSE (typed UIBlocks)
┌───────────────────────────────▼─────────────────────────────┐
│  API & AUTHENTICATION                                         │
│  FastAPI · Firebase auth · session/context management         │
└───────────────────────────────┬─────────────────────────────┘
┌───────────────────────────────▼─────────────────────────────┐
│  AGENT ORCHESTRATION                                          │
│  LangGraph stateful graph · 25-agent suite · UI Agent         │
└───────────────────────────────┬─────────────────────────────┘
┌───────────────────────────────▼─────────────────────────────┐
│  HYBRID RETRIEVAL                                             │
│  graph traversal + dense vector + BM25  ──merge──▶  RRF       │
└───────────────────────────────┬─────────────────────────────┘
┌───────────────────────────────▼─────────────────────────────┐
│  KNOWLEDGE STORES                                             │
│  KG (Neo4j / NetworkX) · Pinecone vectors · Firestore meta    │
└──────────────────────────────────────────────────────────────┘
        ▲  INGESTION PIPELINE: parse → chunk → embed → extract
        │  LLM SERVICES (cross-cutting): Claude primary · OpenRouter fallback
```

**Layer summary:**
- **Client / Presentation.** Next.js 14, adaptive three-panel UI, 24-component GenUI catalog.
- **API & Authentication.** FastAPI service, Firebase auth, session/context management.
- **Agent Orchestration.** LangGraph stateful execution graph running the composable agent suite (incl. the UI Agent).
- **Hybrid Retrieval.** Graph traversal, dense vector search, and BM25, merged with Reciprocal Rank Fusion.
- **Knowledge Stores.** Knowledge graph (Neo4j prod, NetworkX prototype), Pinecone vector store, Firestore metadata/user data.
- **Ingestion Pipeline.** Parsing, chunking, embedding, LLM-based entity/relationship extraction.
- **LLM Services.** Claude API primary; OpenRouter fallback.

### Locked tech stack

| Layer | Technology | Justification |
| --- | --- | --- |
| Frontend | Next.js 14 (App Router), Tailwind CSS, Vercel AI SDK | Proven in VERA AI; AI SDK enables GenUI streaming |
| Agent orchestration | LangGraph (Python) | Native multi-agent graphs with tool-calling |
| LLM (primary) | Claude API (`claude-sonnet`) | Instruction-following, long-context reasoning |
| LLM (fallback) | OpenRouter (`openrouter/auto`) | Model redundancy |
| Knowledge graph | Neo4j Community / NetworkX | Neo4j prod; NetworkX FYP 1 prototype |
| Vector store | Pinecone | 3,072-dim support |
| Embeddings | OpenAI `text-embedding-3-large` | Same as VERA AI baseline (fair comparison) |
| Backend API | FastAPI (Python 3.11) | Async-native; integrates with LangGraph |
| Database | Firebase Firestore | Managed NoSQL for metadata, profiles |
| Auth | Firebase Auth | Email / Google OAuth |
| Spaced repetition | FSRS / SM-2 | Scientifically optimised scheduling |
| GenUI protocol | A2UI-inspired + Vercel AI SDK | Declarative component streaming |

---

## 9. Codebase and Repository Architecture

Arcana is a **monorepo** with two deployable applications — a Python backend (`api/`) and a Next.js frontend (`web/`) — plus shared schema definitions. The split mirrors the runtime boundary: the backend owns orchestration, retrieval and knowledge stores; the frontend owns the GenUI catalog and adaptive shell. They communicate over a typed HTTP + Server-Sent-Events (SSE) contract defined once in `packages/schema` and generated into both TypeScript and Python types, so a component's payload shape can never silently drift between agent and renderer.

> The full annotated tree lives in **`project_file_structure.md`**. The abridged layout below is the orientation map.

```
arcana/
├── api/                         # FastAPI backend (Python 3.11)
│   ├── main.py                  # app factory, routers, lifespan
│   ├── core/                    # settings, logging, auth, errors
│   ├── ingestion/               # parsers, chunker, embedder, extractor
│   │   ├── parsers/             # pdf.py, docx.py, web.py, youtube.py
│   │   ├── chunker.py           # semantic + fixed-window chunking
│   │   ├── embedder.py          # text-embedding-3-large client
│   │   └── extractor.py         # LLM entity/relationship extraction
│   ├── stores/                  # storage abstractions
│   │   ├── graph_store.py       # GraphStore ABC (NetworkX | Neo4j)
│   │   ├── vector_store.py      # Pinecone client wrapper
│   │   └── doc_store.py         # Firestore + object storage
│   ├── retrieval/               # hybrid retrieval
│   │   ├── vector.py  bm25.py  graph.py
│   │   └── fusion.py            # Reciprocal Rank Fusion
│   ├── agents/                  # the 25-agent suite
│   │   ├── base.py              # BaseAgent, @tool decorator, registry
│   │   ├── orchestrator.py
│   │   ├── tier2/  tier3/  tier4/   # specialist agents by tier
│   │   └── graph.py             # LangGraph state graph assembly
│   ├── genui/                   # server-side GenUI protocol
│   │   ├── blocks.py            # typed UIBlock pydantic models
│   │   └── streamer.py          # SSE block streamer
│   ├── llm/                     # LLM service + provider fallback
│   └── routes/                  # /chat /ingest /graph /notebooks /auth
├── web/                         # Next.js 14 frontend (TypeScript)
│   ├── app/                     # App Router routes & layouts
│   ├── components/genui/        # the 24 catalog components
│   ├── components/shell/        # 3-panel adaptive shell
│   ├── lib/stream.ts            # AI SDK block consumer
│   └── store/                   # Zustand UI + session state
├── packages/schema/             # shared block & API types (source of truth)
├── eval/                        # benchmark harness + question set
└── infra/                       # docker-compose, env, deploy scripts
```

### 9.2 Layering and Dependency Rules

Dependencies point in **one direction only**: `routes → agents → retrieval/stores → llm`. Agents never import a concrete store; they depend on the `GraphStore`, `VectorStore` and `DocStore` abstractions, which is what allows the NetworkX→Neo4j migration (FR-KG-07) to happen behind a single seam. The GenUI layer is the only place that knows `UIBlock` shapes, and those shapes are imported from `packages/schema` so the frontend renderer and backend producer share one definition.

| Module | Responsibility | Key external dep |
| --- | --- | --- |
| `core` | Settings, auth dependency, structured logging, error envelope | Pydantic Settings |
| `ingestion` | Turn raw files/URLs into chunks, embeddings, graph triples | PyMuPDF, Claude |
| `stores` | Persist/query graph, vectors, metadata, raw files | Neo4j/NetworkX, Pinecone, Firestore |
| `retrieval` | Three retrievers + RRF fusion behind one `hybrid_retrieve` | — |
| `agents` | 25 agents, tool registry, LangGraph assembly | LangGraph |
| `genui` | Validate and stream typed `UIBlock`s to the client | SSE |
| `llm` | Provider-agnostic completion + tool-calling with fallback | Anthropic, OpenRouter |

**Hard rules (enforce in review):**
1. An agent file in `agents/` must not `import` from `stores/neo4j_*` or `stores/networkx_*` — only the abstract base.
2. Any `UIBlock` type must be defined in `packages/schema` first, then imported by both `api/genui/blocks.py` and `web/components/genui`.
3. No secret literal in source — everything via `Settings` (§9.3).

### 9.3 Configuration and Environments

All configuration is environment-driven via a single typed `Settings` object; nothing is hard-coded. Three profiles: **local** (NetworkX, in-memory caches, demo corpus), **study** (the config used for the user study and benchmark), **prod-design** (Neo4j; documented, not required for the FYP). Secrets are injected from the environment, never committed.

```python
class Settings(BaseSettings):
    env: Literal["local", "study", "prod-design"] = "local"
    graph_backend: Literal["networkx", "neo4j"] = "networkx"
    llm_primary: str = "claude-sonnet"
    llm_fallback: str = "openrouter/auto"
    embedding_model: str = "text-embedding-3-large"   # 3072-dim
    pinecone_index: str = "arcana"
    rrf_k: int = 60                                    # RRF constant
    max_tools_per_prompt: int = 12                     # intent-scoping cap

    class Config:
        env_file = ".env"
```
> *Listing 9.2 — Typed settings (illustrative; finalised in FYP 1 system design).*

---

## 10. Backend Foundation

The backend is an **async FastAPI application**. Async matters because a single chat request fans out into many I/O-bound calls — three retrievers, several LLM completions, graph queries — and the agentic pipeline streams partial results back as they complete. This section specifies the three foundational services every agent relies on: the LLM service, the storage abstractions, and the hybrid retrieval pipeline.

### 10.1 Request Lifecycle

A chat turn enters at `POST /chat`, authenticated by a Firebase ID token. The route loads session context from the Memory Agent, hands the message to the Orchestrator, and opens an SSE stream. As agents produce `UIBlock`s they are validated and streamed to the client immediately, so the user sees a loading component within the first second and watches it fill in. The turn is persisted (messages, retrieved context, emitted blocks) for replay and analytics.

```python
@router.post("/chat")
async def chat(req: ChatRequest, user = Depends(current_user)):
    ctx = await memory.retrieve_session_context(user.id, req.notebook_id)

    async def event_stream():
        async for block in orchestrator.run(req.message, ctx):
            yield sse(block.model_dump())      # typed UIBlock → client

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```
> *Listing 10.1 — Chat endpoint streams typed component blocks over SSE.*

### 10.2 LLM Service and Provider Fallback

Every LLM call goes through one `LLMService` so model choice, tool-calling, retries, token accounting and provider fallback live in a single place (NFR-REL-02). If the primary provider errors or times out, the service retries the identical request against OpenRouter. The same method serves plain completion and tool-calling — the only difference is whether a `tools` schema is supplied.

```python
class LLMService:
    async def complete(self, messages, tools=None, model=None):
        for provider in (self.primary, self.fallback):
            try:
                return await provider.create(
                    model=model or self.default_model,
                    messages=messages, tools=tools, stream=False)
            except (RateLimitError, TimeoutError, ProviderError):
                continue                       # fall through to next provider
        raise AllProvidersFailed()
```
> *Listing 10.2 — Single LLM seam with automatic fallback.*

### 10.3 Storage Abstractions

Three abstractions isolate the system from storage technology. The most important is `GraphStore`, an ABC with NetworkX and Neo4j implementations. Agents and retrieval call only the abstract methods, so swapping the backend is a one-line settings change (FR-KG-07, R-06).

```python
class GraphStore(ABC):
    @abstractmethod
    async def upsert_node(self, node: GraphNode) -> str: ...
    @abstractmethod
    async def upsert_edge(self, edge: GraphEdge) -> str: ...
    @abstractmethod
    async def expand(self, entity: str, hops: int) -> Subgraph: ...
    @abstractmethod
    async def shortest_path(self, a: str, b: str) -> list[str]: ...
    @abstractmethod
    async def communities(self) -> list[Community]: ...       # Louvain
    @abstractmethod
    async def pagerank(self) -> dict[str, float]: ...

class NetworkXGraphStore(GraphStore): ...   # FYP 1 prototype, in-process
class Neo4jGraphStore(GraphStore): ...      # Phase 1 production target
```
> *Listing 10.3 — GraphStore abstraction; identical interface across backends.*

The `VectorStore` (Pinecone) and `DocStore` (Firestore + object storage) follow the same pattern: abstract interface, concrete implementation chosen by `Settings`.

### 10.4 Hybrid Retrieval Pipeline

Retrieval runs **all three retrievers concurrently** and merges them with **Reciprocal Rank Fusion**. RRF is chosen because it needs no score calibration across retrievers — it combines purely on rank, making a graph hit and a vector hit comparable without tuning weights. **This is the single most important piece of evidence in the FYP:** the benchmark holds corpus, embeddings and questions constant and varies only whether graph traversal participates in this function.

```python
async def hybrid_retrieve(query: str, top_k: int = 12) -> list[Chunk]:
    entities = extract_query_entities(query)
    vec, kw, graph = await asyncio.gather(
        vector_search(query, top_k * 2),          # dense, Pinecone
        bm25_search(query, top_k * 2),            # exact keyword
        graph_traverse(entities, hops=2),         # multi-hop expansion
    )
    fused = reciprocal_rank_fusion([vec, kw, graph], k=settings.rrf_k)
    return fused[:top_k]


def reciprocal_rank_fusion(rankings, k=60):
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, chunk in enumerate(ranking):
            scores[chunk.id] += 1.0 / (k + rank)   # rank-based, no calibration
    return [c for c, _ in sorted(by_score(scores), reverse=True)]
```
> *Listing 10.4 — Three-way hybrid retrieval merged via RRF.*

**Graceful degradation (NFR-REL-01):** if one retriever raises, `asyncio.gather` is wrapped so its slot returns an empty ranking and fusion proceeds on the remaining two — quality drops but the request still completes.

---

## 11. The Agentic Pipeline

Arcana's defining engineering claim is **composability**: agents are not isolated endpoints but nodes in a shared LangGraph state graph that can invoke one another as tools. This section specifies how a request is decomposed, how shared state flows, how an agent calls another agent, and how the loop terminates safely.

### 11.1 Shared State

Every node reads from and writes to **one typed state object**. Agents do not pass ad-hoc arguments to each other; they contribute to shared state, which keeps the graph debuggable and replayable. Reducers define how concurrent writes merge (e.g. `messages` and `ui_blocks` append rather than overwrite).

```python
class AgentState(TypedDict):
    messages:      Annotated[list[Message], append]
    active_mode:   Literal["research", "study", "writing", "socratic", "exploration"]
    intent:        Intent                       # parsed by the Orchestrator
    retrieved_ctx: list[Chunk]
    agent_results: dict[str, Any]               # keyed by agent name
    ui_blocks:     Annotated[list[UIBlock], append]
    user_profile:  UserProfile
    budget:        TokenBudget                  # guards cost & loop depth
```
> *Listing 11.1 — Shared LangGraph state.*

### 11.2 The Orchestrator

The Orchestrator is the single entry node. It (1) detects intent and mode from the message and history, (2) produces a **plan** — an ordered or branching set of agents to invoke, (3) routes to the first specialist, and (4) once results return, asks the UI Agent to assemble the final component layout. The plan is **not always linear**: the Orchestrator may dispatch independent agents concurrently and join their results.

```python
class Orchestrator(BaseAgent):
    async def run(self, message, ctx):
        intent = await self.detect_mode(message, ctx.history)
        plan   = await self.plan_agents(intent)      # e.g. [research, factcheck]
        state  = init_state(message, intent, ctx)
        async for block in self.graph.astream(state, plan):
            yield block                              # stream as they arrive
```
> *Listing 11.2 — Orchestrator: intent → plan → streamed execution.*

### 11.3 Tools and the `@tool` Decorator

Each agent capability is a **typed tool**. A decorator registers the function, its JSON schema (derived from type hints), and the tier it belongs to. The schema is what the LLM sees when deciding which tool to call; the type hints validate the arguments at runtime. This dual use — schema for the model, types for the runtime — is why the inventory in §12 reads as concrete signatures rather than prose.

```python
@tool(agent="research", tier=2)
async def cross_document_compare(
    concept: str,
    doc_ids: list[str] | None = None) -> ComparisonResult:
    """Compare how the corpus treats `concept`; surface agreement & conflict."""
    ctx = await hybrid_retrieve(f"{concept} comparison", top_k=20)
    return await synthesise_comparison(concept, ctx)
```
> *Listing 11.3 — A typed tool; its signature is the spec the LLM and runtime share.*

### 11.4 Agent-to-Agent Invocation

Composability is implemented by exposing **each agent as a tool** via `route_to_agent`. When the Writing Agent decides mid-draft that it needs cross-source comparison, the LLM emits a `route_to_agent("research", …)` call; the runtime executes the entire Research Agent — which may itself call the Graph Agent and Fact Checker — and returns its result as a single tool result back into the Writing Agent's reasoning loop. To the calling agent it is just another tool that happens to be powered by a whole agent.

```python
async def route_to_agent(agent_name: str, query: str, **kw) -> AgentResult:
    state.budget.charge_hop()                  # prevents infinite recursion
    if state.budget.exceeded:
        return AgentResult.partial("hop budget reached")
    sub_agent = registry.get(agent_name)
    return await sub_agent.invoke(query, parent_state=state, **kw)
```
> *Listing 11.4 — route_to_agent turns any agent into a composable tool.*

### 11.5 Intent-Scoped Tool Selection

The suite exposes roughly **120 tool calls across 25 agents**, but **no prompt ever sees all of them**. At dispatch the Orchestrator computes which tools are relevant to the current intent and injects only those (capped by `max_tools_per_prompt`). This keeps prompt size, latency and token cost roughly constant as the catalog grows — so "25 agents" does not mean "120 tools per prompt." The approach is adopted from intent-scoped tool routing seen in AnythingLLM.

### 11.6 Termination, Budgets and Failure Handling

Three guards keep the graph safe (FR-AGT-08, FR-AGT-10):

| Guard | Mechanism | Protects against |
| --- | --- | --- |
| Hop budget | `charge_hop()` decrements a per-turn counter on each `route_to_agent` | Infinite / runaway agent recursion |
| Token budget | Running token tally; model downgrade then hard stop | Cost overrun (R-03) |
| Tool try/except | Each tool wrapped; failure → recorded partial result | One tool crashing the whole task |
| Terminal join | Graph always routes to UI Agent before returning | Hung or never-terminating turns |

The Orchestrator always reaches a terminal node that hands off to the UI Agent, even on partial failure.

---

## 11A. System Operation Guide — How Arcana Works (read this first)

> This section is written for the implementing AI/developer. It is the mental model that makes the rest of the spec cohere. Read it before building any agent. The single most important idea: **Arcana is not a chatbot with features bolted on — it is a state graph where specialised agents collaborate over shared state, and the interface is itself an agent output.**

### 11A.1 The one-paragraph model
A user message enters the **Orchestrator**, which decides *what kind of task this is* (intent + mode) and *which agents are needed* (a plan). Agents execute as nodes in a **LangGraph state graph**, all reading and writing **one shared `AgentState`**. Any agent can pull in another agent mid-task by calling `route_to_agent` — that is composability. As agents finish, they don't return prose; they deposit **typed `UIBlock`s** into shared state. The **UI Agent** runs last, decides which components to show and how to lay them out, and the blocks **stream to the browser over SSE** as they're produced. Three guards (hop budget, token budget, per-tool try/except) keep the graph from looping, overspending, or crashing. That is the entire system.

### 11A.2 The end-to-end lifecycle of one request
Follow this sequence; every agent and tool fits somewhere in it.

1. **Ingress.** `POST /chat` authenticates the Firebase token (`core/auth.py`) and opens an SSE stream (`routes/chat.py`, *Listing 10.1*).
2. **Context load.** The **Memory Agent** loads session context (history, profile, active notebook). This always runs first so the Orchestrator reasons with continuity.
3. **Intent + mode detection.** The **Orchestrator** classifies the message into an `intent` and one of the five `active_mode`s. Mode drives the *eventual UI*; intent drives *which agents run*.
4. **Planning.** The Orchestrator produces a `plan` — an ordered or branching list of agents (e.g. `[research, factcheck, ui]`). Independent agents may be dispatched concurrently and joined.
5. **Retrieval (when needed).** Most intelligence agents begin by calling `hybrid_retrieve`, which fans out to vector + BM25 + graph retrievers concurrently and fuses with RRF (*Listing 10.4*). This is the grounding step — nothing is asserted without retrieved evidence.
6. **Specialist reasoning + composition.** The planned agent(s) run. When an agent needs a capability it doesn't own, it emits `route_to_agent("<other>", …)`; the runtime executes that whole agent (which may recurse) and returns its result as a single tool result. Each `route_to_agent` charges the hop budget.
7. **Verification.** For any generated claim that will be shown to the user, the **Fact Checker** verifies grounding before the block is finalised (citation accuracy is a graded metric).
8. **UI assembly.** The **UI Agent** (terminal node) reads `agent_results`, selects catalog components, assigns each to a panel, computes panel widths, and emits the final `UIBlock`s. It is the *only* agent that chooses components.
9. **Streaming + persistence.** Each validated block streams to the client immediately (skeleton → hydrate). The full turn (messages, retrieved context, emitted blocks) is persisted for replay and analytics.

### 11A.3 Invariants the AI must never violate
These are non-negotiable system properties. If an implementation choice breaks one, it is wrong regardless of how convenient it is.

- **Agents contribute to shared state; they do not pass private arguments to each other.** Everything an agent produces lands in `AgentState` (`agent_results`, `ui_blocks`, …) so the graph stays debuggable and replayable.
- **Grounding before generation.** No user-facing claim exists without retrieved evidence and a traceable citation. Provenance survives all the way to exports.
- **The UI is data, never code.** Agents emit typed `UIBlock`s only — never HTML, never executable strings. The server validates every block and fails closed (NFR-SEC-04, R-10).
- **One agent owns components.** Only the UI Agent selects/lays out components. Other agents produce *data*; they never decide *presentation*.
- **Composability is uniform.** Calling another agent is just another tool call (`route_to_agent`). There is no special-case wiring between specific agents — any agent can call any agent, subject to the hop budget.
- **The loop always terminates at the UI Agent.** Even on partial failure or budget exhaustion, the graph routes to the UI Agent so the user always gets an honest, rendered response.
- **Storage is always behind an abstraction.** Agents call `GraphStore` / `VectorStore` / `DocStore`, never a concrete backend. This is what makes NetworkX→Neo4j a one-line change.

### 11A.4 How to think about modes vs intents
- **Intent** answers "what work needs doing?" → drives the agent plan (which agents, in what order).
- **Mode** answers "what should the workspace look like?" → drives the UI Agent's component selection and panel layout.
- They are related but separate. The *same* research intent renders as a `CitedSummary` in Research mode, a `FlashcardDeck` in Study mode, or a `DraftEditor` in Writing mode — identical reasoning, different presentation (§13.6). Build the agents to produce *data*; let the UI Agent decide the *form*.

### 11A.5 How to read each agent spec in §12
Every agent below follows the same template so you can implement them consistently:
- **Role** — the one job this agent exists to do.
- **Phase** — P0 / P1 / P2 (build order).
- **System-prompt intent** — what to put in the agent's prompt so the LLM behaves correctly; the guardrails specific to this agent.
- **Triggers** — when the Orchestrator (or another agent) should route here.
- **Tool calls** — the typed signatures, each with its input contract, output contract, and an implementation note (how it should be built).
- **Composes with** — which agents it commonly invokes via `route_to_agent`, and why.
- **Build notes** — concrete guidance, gotchas, and the FRs it satisfies.

Build the agents in phase order. A P2 agent may exist as a stub that raises `NotImplementedError` until scheduled — the registry and routing should tolerate absent P2 agents gracefully.

---

## 12. Specialised Agent Suite — Full Specification

Arcana defines **25 specialised agents across four tiers**. Each agent is a role-scoped reasoning module with a set of typed tool calls; an agent itself is exposed as a tool to other agents via `route_to_agent` (§11.4), which is what makes the suite composable. The tool signatures below are the contract the orchestrating LLM reasons over and the runtime validates; exact argument types are finalised during FYP 1 system design.

**Phase tags:** `P0` = FYP 1 PoC · `P1` = FYP 2 MVP (graded, target 15+ agents) · `P2` = post-FYP roadmap toward the full 25.

### TIER 1 — Orchestration

#### Orchestrator — `P0`
**Role.** The single entry node and conductor. Turns a raw message into a plan, dispatches specialists, and triggers final UI assembly. It does no domain work itself — it routes.
**System-prompt intent.** "You are a router, not an answerer. Classify intent and mode, decompose the request into the minimal set of agents needed, prefer concurrency for independent sub-tasks, and never fabricate content — delegate. Always end by handing results to the UI Agent." Inject only the tools below plus the intent-relevant specialist tools (§11.5).
**Triggers.** Every turn. It is the graph's entry point.
**Tool calls.**
```python
detect_mode(query: str, history: list[Message]) -> Mode
# IN: message + recent history. OUT: one of research|study|writing|socratic|exploration.
# IMPL: a single classification LLM call with a tight rubric; default to `research` when ambiguous.

route_to_agent(agent: str, query: str) -> AgentResult
# IN: agent name + sub-query. OUT: that agent's result. IMPL: §11.4; charges hop budget.

sequence_agents(plan: list[AgentStep]) -> Plan
# IN: ordered/branching steps. OUT: an executable plan. IMPL: mark steps independent|dependent so
#     the runtime can asyncio.gather independents.

get_conversation_history() -> list[Message]      # IMPL: thin wrapper over Memory Agent context.
get_user_context() -> UserProfile                # IMPL: from Memory Agent; informs adaptation.
assemble_response(blocks: list[UIBlock]) -> Response
# IN: the UI Agent's blocks. OUT: the final streamed response envelope.
```
**Composes with.** Any agent (it is the top-level caller). Always finishes with the UI Agent.
**Build notes.** Keep planning cheap — one LLM call to classify + plan, not a chain. The plan is a *hint*; specialists may still call `route_to_agent` for things the plan didn't foresee. Satisfies **FR-AGT-01**. *Listing 11.2*.

---

### TIER 2 — Core Intelligence

#### Research Agent — `P0`
**Role.** The flagship cross-document reasoner: synthesis, comparison, contradiction detection, gap analysis — always grounded and cited.
**System-prompt intent.** "Answer only from retrieved evidence. Every claim must carry a citation to a specific passage. When sources disagree, surface the disagreement rather than averaging it away. If the corpus doesn't cover something, say so — that's a gap, not a failure." Forbid ungrounded assertion explicitly.
**Triggers.** Research/Exploration intents; questions spanning multiple documents; any "compare / contrast / what do my sources say about X" request. Also invoked by the Writing and Learning agents for grounded material.
**Tool calls.**
```python
hybrid_retrieve(query: str, top_k: int = 12) -> list[Chunk]
# IN: query + k. OUT: top-k fused chunks. IMPL: the shared retrieval entry point (Listing 10.4).
#     This is the first call in almost every Research task.

cross_document_compare(concept: str, doc_ids: list[str]) -> ComparisonResult
# IN: concept + target docs. OUT: {agreements[], conflicts[], per-doc stance}.
# IMPL: retrieve broadly (top_k≈20), then a structured-output LLM call that fills a typed comparison
#     schema; route_to_agent("graph") first for multi-hop context (Listing 11.3).

detect_contradictions(concept: str) -> list[Contradiction]
# OUT: pairs of conflicting claims + their source passages. IMPL: lean on contradicts-edges in the
#     graph where present; confirm with an LLM judgement over the retrieved passages.

find_research_gaps(corpus: CorpusRef) -> GapReport
# OUT: themes the corpus underspecifies. IMPL: cluster the graph (Louvain via Graph Agent), then ask
#     the LLM which expected sub-topics for the dominant themes are absent.

summarise_with_grounding(chunks: list[Chunk], query: str) -> CitedSummary
# OUT: CitedSummaryData (§16.1). IMPL: synthesis prompt that REQUIRES a [marker]→passage map; reject
#     any sentence lacking a citation before returning.

cite_sources(chunks: list[Chunk]) -> list[Citation]
# OUT: structured citations (doc_id, passage, page). IMPL: deterministic mapping, not an LLM call.
```
**Composes with.** **Graph** (multi-hop context for comparisons), **Fact Checker** (validate the synthesis before output).
**Build notes.** This agent produces the FYP's headline capability. Keep `summarise_with_grounding` strict: a claim without a passage is a bug. Satisfies **FR-RET-05/06/08**.

#### Graph Agent — `P0`
**Role.** The knowledge-graph specialist: traversal and the four graph algorithms. It answers structural questions ("how are these connected?", "what's central?", "what bridges these clusters?").
**System-prompt intent.** "Reason over graph structure, not text. Return entities, paths, and clusters with their evidence edges. You are usually called *by* other agents — return compact, typed structures, not prose."
**Triggers.** Any need for multi-hop context, connection-finding, centrality, or community structure. Heavily invoked by Research, Discovery, Socratic, and Learning.
**Tool calls.**
```python
graph_expand(entity: str, hops: int = 2) -> Subgraph
# IN: seed entity + hop count. OUT: neighbourhood subgraph. IMPL: GraphStore.expand(); cap node count
#     to keep payloads small.

find_shortest_path(entity_a: str, entity_b: str) -> list[str]
# OUT: the connecting chain of entities. IMPL: GraphStore.shortest_path(); the "how are X and Y related" answer.

detect_communities() -> list[Community]            # Louvain — FR-KG-04
find_bridge_concepts() -> list[Concept]            # betweenness centrality — FR-KG-06
pagerank_concepts() -> dict[str, float]            # node importance — FR-KG-05
detect_entity_contradictions() -> list[Contradiction]
# IMPL: scan for contradicts-edges and conflicting property values on canonicalised entities.
```
**Composes with.** Rarely calls others; it is a leaf provider of structure.
**Build notes.** All four algorithms live behind the `GraphStore` ABC so NetworkX and Neo4j expose them identically (*Listing 10.3*). Satisfies **FR-RET-03**, **FR-KG-04/05/06**.

#### Learning Agent — `P1`
**Role.** Turns corpus material into evidence-based study artifacts and schedules their review. The engine behind Study mode and P4 of the problem statement.
**System-prompt intent.** "Generate study material grounded in the user's sources, not generic facts. Cards/quizzes must trace to a passage. Favour active recall over re-reading. Match difficulty to the user's tracked progress." Each method (flashcards, quiz, Feynman, Cornell, blurting, interleaving) has a distinct output contract — don't blur them.
**Triggers.** Study intent; "make flashcards / quiz me / explain simply / take notes" requests; scheduled review resurfacing.
**Tool calls.**
```python
generate_flashcards(concepts: list[str], style: CardStyle) -> FlashcardDeck
# OUT: FlashcardDeckData (§16.1) — each card carries source{doc_id,passage} + schedule. IMPL: pull
#     grounded material (route_to_agent("research")), then generate atomic Q/A pairs; init schedule.

generate_quiz(topic: str, difficulty: Level, n: int) -> Quiz
# OUT: MCQ + short-answer items with answer keys + source passages. IMPL: difficulty maps to Bloom level.

feynman_explain(concept: str) -> FeynmanExplanation
# OUT: simple explanation + explicitly flagged gaps the learner should revisit. IMPL: deliberately
#     simple language; the value is in the flagged gaps.

cornell_notes(doc_id: str) -> CornellNotes        # cue / notes / summary structure — FR-LRN-05
assess_knowledge_gap(user_history: History) -> GapAssessment
# IMPL: combine review failures + quiz scores to find weak topics; feeds adaptive difficulty.

schedule_spaced_review(card_id: str) -> ReviewSchedule
# OUT: next due/interval/ease. IMPL: FSRS or SM-2 (Q-04); updates ReviewState in Firestore — FR-LRN-02.

generate_blurting_prompt(topic: str) -> BlurtingPrompt   # free recall then compare to source — FR-LRN-06
create_interleaving_set(topics: list[str]) -> PracticeSet  # mixed-topic practice — FR-LRN-07 (P2)
```
**Composes with.** **Research** + **Graph** (grounded material and related concepts for cards/quizzes).
**Build notes.** Pick FSRS or SM-2 early (Q-04) and keep the scheduler isolated so the choice is swappable. Satisfies **FR-LRN-01..07,10**.

#### Writing Agent — `P1`
**Role.** Produces grounded written work — drafts, outlines, literature reviews — and checks it against the user's own corpus. The engine behind Writing mode and the §6.7 composability showcase.
**System-prompt intent.** "Write from the user's sources, never from your own memory. Every factual sentence cites a passage. Before finalising, check the draft for consistency against the corpus and flag any claim that contradicts the user's own sources." Forbid invented references absolutely.
**Triggers.** Writing intent; "draft / write a section / outline / literature review" requests.
**Tool calls.**
```python
draft_section(title: str, context: list[Chunk], style: Style) -> Draft
# OUT: DraftEditor payload with inline citation markers. IMPL: retrieve → draft → for each claim,
#     route_to_agent("factcheck"); attach citations via the Citation Agent.

generate_outline(topic: str) -> Outline           # structure before prose
build_literature_review(doc_ids: list[str]) -> LiteratureReview
# IMPL: the showcase chain — route_to_agent("research") for cross-doc comparison + contradictions,
#     which itself calls Graph + Fact Checker; assemble into a cited review (§6.7, Listing 12.1).

check_consistency(draft: Draft) -> ConsistencyReport
# OUT: claims in the draft that conflict with the corpus. IMPL: re-retrieve each claim; flag mismatches.

generate_annotated_bibliography(doc_ids: list[str]) -> Bibliography
get_document_outline(doc_ids: list[str]) -> Outline
```
**Composes with.** **Research** (ground claims), **Fact Checker** (verify each), **Citation** (format references).
**Build notes.** This is the most composition-heavy agent — it is the proof that A2A invocation works. Make `draft_section`'s fact-check loop visible in traces. Satisfies **FR-RET-05**, **FR-AGT-03/09**, **FR-EXP-01/02**.

#### Socratic Tutor — `P1`
**Role.** Teaches by asking, never telling. Guides the learner to insight through probing questions, scaffolds, and misconception detection.
**System-prompt intent.** "Never give the answer. Respond to the learner with the next question that moves them one step forward. Detect misconceptions and target them with a question, not a correction. Track the Bloom level and gradually raise it." This withholding behaviour is the defining, gradeable property — enforce it hard in the prompt.
**Triggers.** Socratic intent; "tutor me / quiz my understanding / help me reason through X"; invoked from Study mode.
**Tool calls.**
```python
generate_probing_question(concept: str, user_response: str) -> Question
# OUT: the next question (never an answer). IMPL: condition on the learner's last response; reference
#     the concept graph (route_to_agent("graph")) to pick the most productive next probe.

assess_understanding(user_answer: str) -> Assessment       # depth + correctness signal
build_bloom_assessment(topic: str) -> BloomAssessment      # questions laddered across Bloom levels
scaffold_hint(concept: str, difficulty: Level) -> Hint     # minimal nudge, not the solution
evaluate_misconception(user_answer: str) -> Misconception  # name the misconception; do not lecture
```
**Composes with.** **Graph** (map concepts being reasoned over), **Learning** (generate scaffolds/cards).
**Build notes.** Output is `SocraticDialogData` whose `next_question` field must *never* contain an answer (§16.1). Add a post-generation check that rejects answer-shaped outputs. Satisfies **FR-LRN-08**.

#### Discovery Agent — `P1`
**Role.** Surfaces non-obvious, serendipitous cross-document connections the user didn't think to ask about. The engine behind Exploration mode.
**System-prompt intent.** "Find connections the user would be surprised by. Rank by novelty, not relevance — an obvious link is useless here. Ground every connection in graph evidence." 
**Triggers.** Exploration intent; idle/ambient discovery; "show me interesting connections / what links these".
**Tool calls.**
```python
surface_cross_document_link(corpus: CorpusRef) -> list[Link]
# IMPL: use bridge concepts + community structure from the Graph Agent to find cross-cluster links.

generate_insight_card(entity_cluster: Cluster) -> InsightCard   # a human-readable surprising link
detect_serendipitous_connection() -> list[Connection]
rank_novelty(connection: Connection) -> float
# IMPL: novelty ≈ inverse of co-occurrence / shortest-path length; longer surprising paths score higher.
```
**Composes with.** **Graph** (bridge + community analysis).
**Build notes.** Output is `InsightCard` + `GapAnalysis`. The novelty ranking is what stops this from being a generic "related items" feature.

#### Methodology Agent — `P2`
**Role.** Advises on research design, methodology comparison, sample size, and evaluation metrics.
**Triggers.** "How should I study this / which method / what sample size" — research-design questions.
**Tool calls.**
```python
recommend_research_design(question: str) -> Design
compare_methodologies(options: list[str]) -> Comparison
estimate_sample_size(params: PowerParams) -> int          # IMPL: power analysis, not an LLM guess
suggest_evaluation_metrics(study_type: str) -> list[Metric]
generate_methodology_template(design: Design) -> Template
```
**Build notes.** P2 stub. `estimate_sample_size` should use a real power-analysis library, not the LLM.

#### Debate Agent — `P2`
**Role.** Stress-tests arguments: counterarguments, steelmanning, counter-evidence, simulated peer review.
**Triggers.** "Argue against / find weaknesses / peer-review my draft".
**Tool calls.**
```python
generate_counterargument(claim: str) -> Counterargument
build_steelman(position: str) -> Steelman
find_counter_evidence(thesis: str) -> list[Evidence]      # IMPL: retrieve passages that conflict
simulate_peer_review(draft: Draft) -> ReviewReport
```
**Build notes.** P2 stub. `find_counter_evidence` must ground in the corpus, not invent objections.

### TIER 3 — Output Generation

#### UI Agent — `P1`
**Role.** The terminal node and the *only* agent that chooses presentation. Translates results into a concrete component layout. Generative UI lives here.
**System-prompt intent.** "You decide what the user sees. Given the intent, mode, history and preferences, choose the smallest set of catalog components that fully answers the request, assign each to a panel, and compute panel widths. You may blend modes or invent task-specific layouts — you are not limited to the five named modes. Respect any user layout override. Emit typed component blocks only, never markup."
**Triggers.** Always, last, on every turn (terminal join — §11.6).
**Tool calls.**
```python
select_output_components(intent: Intent, mode: Mode) -> list[ComponentSpec]
# OUT: which catalog components to render + their data. IMPL: an LLM call constrained to the 24-component
#     catalog vocabulary; reads agent_results to fill each component's typed payload (Listing 13.2).

determine_layout(context: Context) -> LayoutSpec
# OUT: panel assignment + widths (e.g. Sources 20% | Chat 45% | Studio 35%). IMPL: derive from mode +
#     component set; this is what makes the shell animate.

get_user_preferences() -> Preferences                     # from Memory Agent; honour overrides — FR-UI-07
adapt_complexity_level(user_profile: UserProfile) -> ComplexityLevel  # FR-UI-08 (P2)
stream_component_block(component: str, data: dict) -> UIBlock
# OUT: a validated UIBlock. IMPL: build {type,data,meta}; genui/validate.py rejects malformed (fail closed).
```
**Composes with.** None — it consumes everyone else's results and emits the layout.
**Build notes.** The unbounded-UI claim is realised here: because layout is composed at runtime from typed components, new interfaces need no new code. Constrain the LLM's component choices to the registry to prevent hallucinated component types. Satisfies **FR-UI-04/05/06**.

#### Citation Agent — `P1`
**Role.** Formats and exports citations and bibliographies in academic styles.
**System-prompt intent.** "Produce exact, style-correct citations from source metadata. Never invent bibliographic fields — if a field is missing, mark it, don't fabricate it."
**Triggers.** Any draft/answer needing formatted references; export requests.
**Tool calls.**
```python
format_citation(source: Source, style: CitationStyle) -> str   # APA/MLA/IEEE/etc — deterministic templates
export_bibtex(doc_ids: list[str]) -> str                       # FR-EXP-08
export_ris(doc_ids: list[str]) -> str                          # FR-EXP-08
sync_zotero(library: ZoteroRef) -> SyncResult                  # P2 nicety
detect_citation_style(text: str) -> CitationStyle              # infer the user's preferred style
```
**Composes with.** Invoked by Writing.
**Build notes.** Formatting should be template-driven and deterministic, not an LLM call, to guarantee correctness (this feeds the ≥90% citation-accuracy metric). Output renders as `CitationPreview` / `BibliographyExport`.

#### Visual Agent — `P1`
**Role.** Produces the data structures for visual components (maps, charts, timelines, tables, graph views).
**System-prompt intent.** "Emit the typed data a visual component needs — not an image. The frontend renders it. Choose the visual that best fits the structure of the data."
**Triggers.** When the UI Agent selects a visual component; when Research/Graph results are best shown visually.
**Tool calls.**
```python
render_concept_map(entities: list[str]) -> ConceptMap          # nodes + relations for reasoning
render_comparison_chart(data: ChartData) -> Chart
render_timeline(events: list[Event]) -> Timeline
render_data_table(structured_data: Table) -> DataTable         # sortable
render_knowledge_graph_view(subgraph: Subgraph) -> KnowledgeGraphView  # interactive, ≤500 nodes — NFR-PERF-04
```
**Composes with.** Consumes Graph Agent subgraphs.
**Build notes.** "Render" here means *produce typed data*, not raster output — the actual drawing happens in the React component. Keep `KnowledgeGraphView` payloads node-capped for the <2s render target.

#### Document Agent — `P1`
**Role.** Generates downloadable file artifacts (PDF, DOCX, slides, matrices, vaults) with provenance preserved.
**System-prompt intent.** "Produce export-ready files. Every citation and source link must survive into the exported artifact (§19.3)."
**Triggers.** Export requests; "download as PDF/DOCX/deck".
**Tool calls.**
```python
generate_pdf_report(content: Content) -> File                 # FR-EXP-01
generate_docx(content: Content) -> File                       # FR-EXP-02
generate_slide_deck(synthesis: Synthesis) -> File             # FR-EXP-03 (P2)
export_literature_matrix(doc_ids: list[str]) -> File
export_obsidian_vault(graph: GraphRef) -> Vault               # wikilinks from edges — FR-EXP-06
```
**Composes with.** Consumes Research/Writing output.
**Build notes.** Provenance preservation is a hard requirement — strip nothing on export.

#### Audio Agent — `P2`
**Role.** Audio overviews, TTS, podcast scripts, spoken flashcards.
**Tool calls.**
```python
generate_audio_summary(content: Content) -> AudioFile
text_to_speech(text: str, voice: Voice) -> AudioFile
generate_podcast_script(topic: str) -> Script
generate_spoken_flashcards(deck: FlashcardDeck) -> AudioFile
```
**Build notes.** P2 stub; audio is roadmap-only for the FYP (out of graded scope).

---

### TIER 4 — Quality & Meta

#### Fact Checker — `P1`
**Role.** The guardrail on output quality. Verifies that generated claims are grounded before they reach the user.
**System-prompt intent.** "For each claim, find the supporting passage. If you cannot, flag it as unverified — do not pass it. You are the last line before the user sees a claim." This agent is why citation accuracy can be a graded metric.
**Triggers.** Invoked by Research and Writing before output finalisation; on any synthesis with novel claims.
**Tool calls.**
```python
verify_claim(claim: str) -> Verification
# OUT: {grounded|partial|unverified, supporting_passage?}. IMPL: re-retrieve for the claim; LLM judges
#     whether the passage actually supports it (not just topical overlap).

check_citation_accuracy(citation: Citation, source: Source) -> float   # 0..1 — does the passage support the marker
flag_hallucination(text: str) -> list[Flag]                            # spans with no grounding
cross_reference_sources(statement: str) -> list[Source]                # corroborating sources
```
**Composes with.** Invoked by Writing, Research. Calls retrieval directly.
**Build notes.** `verify_claim` must check *entailment*, not topic match — a passage about the right topic that doesn't support the claim is still unverified. Satisfies **FR-AGT-09**.

#### Annotation Agent — `P1`
**Role.** Captures user highlights/notes and folds them back into the knowledge graph (FR-USR-05).
**System-prompt intent.** "Treat the user's own notes as first-class sources. Link them to the entities they discuss so future retrieval can surface them."
**Triggers.** User highlights text or adds a note.
**Tool calls.**
```python
add_user_annotation(text: str, doc_id: str) -> Annotation
enrich_graph_node(node_id: str, note: str) -> GraphNode        # attach user note to an entity
link_user_note_to_entity(note: str, entity: str) -> Edge       # new edge into the KG
capture_highlight(selection: Selection) -> Highlight
```
**Build notes.** User notes become retrievable graph content — they participate in `hybrid_retrieve` like any source.

#### Memory Agent — `P1`
**Role.** The continuity layer. Loads/saves user profile, history, session context, and learning progress. Runs first on every turn.
**System-prompt intent.** N/A mostly mechanical — but its `retrieve_session_context` shapes how every other agent behaves, so keep it accurate and current.
**Triggers.** Start of every chat turn (context load, §10.1, §11A.2 step 2); after every turn (history update).
**Tool calls.**
```python
get_user_profile() -> UserProfile
retrieve_session_context() -> SessionContext                   # history + active notebook + prefs
update_interaction_history(event: Event) -> None               # persisted to Firestore — FR-USR-04
track_learning_progress(topic: str) -> Progress                # feeds adaptive difficulty — FR-LRN-10
store_user_preference(key: str, value: Any) -> None
```
**Build notes.** This is what makes "I never have to rebuild my context" true (Epic F). Persists to Firestore.

#### Ingestion Agent — `P0`
**Role.** The agent-facing wrapper around the ingestion pipeline (`api/ingestion/`). Lets the system add sources mid-conversation.
**System-prompt intent.** "Turn a raw source into graph + vector content reliably. Report failures with a cause; never silently drop a document."
**Triggers.** User adds a source (upload/URL/YouTube); mid-task source addition.
**Tool calls.**
```python
parse_document(file: File) -> ParsedDoc                        # FR-ING-01 (delegates to parsers/)
extract_entities_relationships(chunk: Chunk) -> list[Triple]   # FR-ING-06
chunk_and_embed(text: str) -> list[Embedding]                  # FR-ING-05
ocr_scan(image: Image) -> str                                  # FR-ING-04
parse_youtube_transcript(url: str) -> Transcript               # FR-ING-03
```
**Build notes.** Thin wrapper — the real work is in `api/ingestion/`. Surfaces per-item progress (FR-ING-07) and retryable failures (FR-ING-08).

#### Web Search Agent — `P1`
**Role.** Academic paper discovery only — extends the corpus with relevant external papers. **Not** a general web search.
**System-prompt intent.** "Find academic papers relevant to the user's corpus or query. Return structured paper metadata. Never browse the open web for general information — scope is scholarly discovery."
**Triggers.** "Find related papers / what else has been published / expand my sources".
**Tool calls.**
```python
search_semantic_scholar(query: str) -> list[Paper]
search_arxiv(query: str) -> list[Paper]                        # keyless
search_google_scholar(query: str) -> list[Paper]
fetch_citation_network(paper_id: str) -> CitationGraph
recommend_related_papers(corpus: CorpusRef) -> list[Paper]     # IMPL: embed corpus themes, query APIs
```
**Build notes.** Respect the §4.2 non-goal: discovery, not web answering. Discovered papers can be ingested via the Ingestion Agent.

#### Study Planner — `P1`
**Role.** Schedules study time, manages Pomodoro, tracks deadlines, sends review reminders.
**System-prompt intent.** "Build realistic schedules around the user's deadlines and the spaced-repetition queue. Don't over-pack — forecast workload honestly."
**Triggers.** "Plan my study / set a schedule / remind me"; review-due events.
**Tool calls.**
```python
generate_study_schedule(deadlines: list[Deadline], goals: Goals) -> Schedule   # FR-LRN-09
create_pomodoro_session(task: str) -> PomodoroSession
track_deadline(assignment: Assignment) -> None
forecast_workload(schedule: Schedule) -> Forecast
send_review_reminder(card_id: str) -> None                     # ties into spaced repetition
```
**Build notes.** Renders as `StudyPlanner`. Pull the review queue from the Learning Agent's ReviewState.

#### Analytics Agent — `P1`
**Role.** Measures the things the FYP is graded on. Produces the evaluation evidence and the user-facing progress dashboard.
**System-prompt intent.** Mechanical/measurement — accuracy over narrative.
**Triggers.** Background instrumentation; "show my progress"; evaluation runs.
**Tool calls.**
```python
measure_retrieval_quality(query_log: QueryLog) -> QualityReport   # feeds the benchmark — FR-ANL-01
track_study_effectiveness(user_id: str) -> EffectivenessReport
generate_progress_dashboard(user_id: str) -> Dashboard            # renders as ProgressDashboard
compute_retention_rate(deck: FlashcardDeck) -> float
```
**Build notes.** This agent's output is partly *for the author* (evaluation, §20, §23) and partly *for the user* (dashboard). Keep the two paths distinct.

#### Plagiarism Agent — `P2`
**Role.** Originality + AI-content checks, uncited-passage flagging.
**Tool calls.**
```python
check_originality(text: str) -> OriginalityScore
detect_ai_content(text: str) -> float
flag_uncited_passage(draft: Draft) -> list[Passage]
suggest_citation(passage: str) -> Citation
```
**Build notes.** P2 stub. Renders as `PlagiarismReport`.

#### Grammar & Style Agent — `P2`
**Role.** Grammar, readability, journal-readiness, style suggestions.
**Tool calls.**
```python
check_grammar(text: str) -> list[Correction]
score_readability(text: str) -> ReadabilityScore
assess_journal_readiness(draft: Draft) -> ReadinessReport
suggest_style_improvement(sentence: str) -> Suggestion
```
**Build notes.** P2 stub.

#### Paraphrase Agent — `P2`
**Role.** Rewrites for complexity, length, register, or audience — without losing meaning or provenance.
**Tool calls.**
```python
rewrite_complexity(text: str, target_level: Level) -> str
reduce_word_count(text: str, target: int) -> str
academify_text(text: str) -> str
simplify_for_audience(text: str, audience: Audience) -> str
```
**Build notes.** P2 stub. Must preserve citations through any rewrite.

#### Export Agent — `P2`
**Role.** Bulk import/export and third-party sync (Drive, Anki, Obsidian).
**Tool calls.**
```python
bulk_import(source: ImportSource) -> ImportResult
sync_google_drive(folder: DriveFolder) -> SyncResult            # FR-EXP-09
export_anki_deck(flashcards: FlashcardDeck) -> File             # FR-EXP-07
export_obsidian(graph: GraphRef) -> Vault                       # FR-EXP-06 (shares logic with Document Agent)
batch_export(format: ExportFormat) -> File
```
**Build notes.** P2 stub. Obsidian export overlaps the Document Agent — share the vault serialiser.

### 12.6 Composability Matrix and Worked Example

| Calling agent | Commonly invokes | Why |
| --- | --- | --- |
| Writing Agent | Research, Fact Checker, Citation | Ground each drafted claim, verify it, format its citation |
| Research Agent | Graph, Fact Checker | Multi-hop context, then validate the synthesis |
| Learning Agent | Research, Graph | Pull grounded material and related concepts for cards/quizzes |
| Socratic Tutor | Graph, Learning | Map concepts the learner is reasoning over; generate scaffolds |
| Discovery Agent | Graph | Bridge-concept and community analysis for serendipity |
| Orchestrator | any (via `route_to_agent`) | Top-level routing and final assembly |
| UI Agent | — | Terminal: consumes results, emits the component layout |

**Worked example — "Compare how these three papers treat attention":**

```
USER  → "Compare how these three papers treat attention."
Orchestrator.detect_mode()      → mode = research
Orchestrator.plan_agents()      → [research, factcheck, ui]
Research.cross_document_compare("attention", [d1,d2,d3])
  └─ route_to_agent("graph", "attention")          # A2A hop 1
     Graph.graph_expand("attention", hops=2) → subgraph
  └─ hybrid_retrieve("attention comparison", 20)   # G+V+BM25+RRF
  → ComparisonResult{ agreements:[...], conflicts:[...] }
route_to_agent("factcheck", result)                 # A2A hop 2
  FactChecker.verify_claim(...) → all claims grounded
UI.select_output_components(research) →
  [ LiteratureMatrix, ContradictionAlert, KnowledgeGraphView ]
UI.determine_layout() → Sources 20% │ Chat 45% │ Studio 35%
STREAM → 3 typed UIBlocks rendered as they arrive
```
> *Listing 12.1 — Execution trace: one request, two A2A hops, three streamed components.*

---

## 13. Generative UI — Protocol and Component Catalog

Arcana's interface is **assembled per request** rather than fixed. Instead of returning plain text or raw HTML, agents emit declarative, typed component descriptions; a trusted frontend catalog renders them. This follows Google's A2UI protocol and is delivered through the Vercel AI SDK's streaming of React Server Components. **Security property:** agents never emit executable code — only data conforming to a known component schema — so a model can never inject markup or script into the page (NFR-SEC-04).

### 13.1 The UIBlock Protocol

The unit of GenUI is a `UIBlock`: a tagged union of `{ type, data, meta }` where `type` names a catalog component, `data` matches that component's typed schema, and `meta` carries placement hints (target panel, ordering, complexity). Defined **once** in `packages/schema` and shared by backend producer and frontend renderer.

```typescript
// packages/schema/blocks.ts  (shared source of truth)
type UIBlock =
  | { type: "CitedSummary";       data: CitedSummaryData; meta: BlockMeta }
  | { type: "FlashcardDeck";      data: FlashcardDeckData; meta: BlockMeta }
  | { type: "LiteratureMatrix";   data: MatrixData;        meta: BlockMeta }
  | { type: "KnowledgeGraphView"; data: GraphData;         meta: BlockMeta }
  /* ...one variant per catalog component... */;

interface BlockMeta {
  panel: "sources" | "chat" | "studio";
  order: number;
  complexity?: "concise" | "standard" | "detailed";
}
```
> *Listing 13.1 — UIBlock as a typed tagged union shared across the wire.*

### 13.2 Streaming Lifecycle

Blocks stream over SSE as produced. The frontend reads the stream, looks each `type` up in the catalog registry, mounts the matching component immediately in a loading state, then hydrates it as data arrives — which is why the user sees structure within the first second even on a long multi-agent task (NFR-PERF-01).

1. **Agent emits** a `UIBlock` into shared state as soon as its result is ready.
2. **Server validates** the block against the schema and rejects malformed ones (fail closed).
3. **Server streams** the validated block as an SSE event.
4. **Client resolves** `type` to a component via the registry and mounts it in a skeleton state.
5. **Client hydrates** the component as data fills in; panel widths animate to the new layout.

### 13.3 The 24-Component Catalog

The catalog is the vocabulary of the interface. Each component is a typed React component mapped to the agent tool calls that produce it. Expanding the catalog directly widens the space of interfaces the UI Agent can compose.

| Component | Purpose | Produced by |
| --- | --- | --- |
| `CitedSummary` | Grounded answer with inline source citations | Research |
| `LiteratureMatrix` | Papers × dimensions comparison grid | Research |
| `ContradictionAlert` | Flags where sources disagree on a concept | Research / Graph |
| `GapAnalysis` | What the corpus does not cover | Research |
| `InsightCard` | A surfaced serendipitous cross-document link | Discovery |
| `KnowledgeGraphView` | Interactive graph of entities and edges | Graph / Visual |
| `ConceptMap` | Concept-relationship map for reasoning | Visual / Socratic |
| `ComparisonChart` | Chart of structured comparative data | Visual |
| `Timeline` | Chronological event view | Visual |
| `DataTable` | Sortable structured table | Visual |
| `FlashcardDeck` | Active-recall cards with SR scheduling | Learning |
| `QuizCard` | MCQ / short-answer question item | Learning |
| `BlurtingPrompt` | Free-recall prompt + comparison to source | Learning |
| `FeynmanExplainer` | Simplified explanation + flagged gaps | Learning |
| `CornellNotes` | Cue / notes / summary structured note | Learning |
| `SocraticDialog` | Guided questioning that withholds answers | Socratic Tutor |
| `StudyPlanner` | Schedule, Pomodoro and review queue | Study Planner |
| `DraftEditor` | Editable grounded draft with citations | Writing |
| `CitationPreview` | Formatted citation in chosen style | Citation |
| `PlagiarismReport` | Originality and AI-content flags | Plagiarism |
| `BibliographyExport` | BibTeX / RIS export panel | Citation |
| `SourceList` | The notebook's ingested sources | Ingestion |
| `ProgressDashboard` | Learning-progress and retention metrics | Analytics |
| `AudioSummary` | Player for an audio overview (P2) | Audio |

### 13.4 The UI Agent's Decision

The UI Agent is the **only** agent that chooses components. Given parsed intent, active mode, interaction history and user preferences, it selects components, assigns each to a panel, and computes panel widths. Because layout is computed at runtime from typed components, the space of possible interfaces is effectively **unbounded** — the five documented modes are concrete samples from a continuous design space, not a fixed menu. The UI Agent can blend modes or compose a task-specific view (e.g. "thesis defence rehearsal", "systematic review screening") with **no new code**.

```python
class UIAgent(BaseAgent):
    async def select_output_components(self, intent, mode, history):
        prefs = await self.get_user_preferences()
        plan  = await self.llm.complete(
            prompt = layout_prompt(intent, mode, history, prefs),
            tools  = [select_output_components, determine_layout])
        return [ self.stream_component_block(c.type, c.data)
                 for c in plan.components ]
```
> *Listing 13.2 — The UI Agent composes a layout from typed components.*

### 13.5 Five Demonstrated Modes

The five configurations below are the representative modes the FYP demonstrates. They are samples, not a ceiling.

| Mode | Sources | Chat | Studio | Streams |
| --- | --- | --- | --- | --- |
| **Research** | papers list (~20%) | dense (~45%) | clustered graph (~35%) | `CitedSummary`, `LiteratureMatrix`, `ContradictionAlert` |
| **Study** | collapsed strip | cards (~45%) | SR review + planner (expanded) | `FlashcardDeck`, `QuizCard`, `BlurtingPrompt` |
| **Writing** | sources | maximised draft space | hidden | `DraftEditor`, `CitationPreview`, `PlagiarismReport` |
| **Socratic** | sources | dialog | concept-relationship graph | `SocraticDialog`, `FeynmanExplainer`, `ConceptMap` |
| **Exploration** | hidden | narrow | full-canvas interactive graph | `InsightCard`, `GapAnalysis` |

### 13.6 Worked Example — same request, different mode

The trace in Listing 12.1 produces three streamed components in Research mode. The same request in Study mode would yield a `FlashcardDeck` and `QuizCard`; in Writing mode, a `DraftEditor`. **The agents and retrieval are identical — only the UI Agent's component selection differs.** That is the essence of Generative UI.

---

## 14. Frontend Architecture and Design System

The frontend is a **Next.js 14 App Router** application in TypeScript, styled with Tailwind CSS, consuming the GenUI block stream through the Vercel AI SDK. Its job is narrow: render the adaptive three-panel shell, host the trusted component catalog, manage UI/session state. **It contains no business logic** — all reasoning lives in the backend.

### 14.1 Route and Component Structure

```
web/app/
├── (auth)/login                 # Firebase auth screens
├── notebooks/                   # notebook list / create
└── notebooks/[id]/
    ├── layout.tsx               # 3-panel adaptive shell
    └── page.tsx                 # chat + block stream consumer
web/components/
├── shell/  SourcesPanel  ChatPanel  StudioPanel  ModeIndicator
├── genui/  <24 catalog components, one file each>
└── genui/registry.ts            # type → component map
web/lib/stream.ts                # SSE → UIBlock[] consumer (AI SDK)
web/store/                       # Zustand: ui-state, session, blocks
```

### 14.2 The Component Registry

The registry is the single mapping from a block `type` to a React component. The stream consumer never switches on type by hand; it looks the type up, so adding a catalog component is **a one-line registry entry plus the component file** (NFR-MNT-02).

```typescript
export const registry = {
  CitedSummary: CitedSummary,
  FlashcardDeck: FlashcardDeck,
  LiteratureMatrix: LiteratureMatrix,
  KnowledgeGraphView: KnowledgeGraphView,
  /* ...all 24... */
} as const;

function renderBlock(block: UIBlock) {
  const Component = registry[block.type];
  return <Component {...block.data} meta={block.meta} />;
}
```
> *Listing 14.2 — Type-safe registry; the renderer never hand-switches on type.*

### 14.3 State Management

| Store | Scope | Holds |
| --- | --- | --- |
| `uiStore` | Client | Active mode, panel widths, overrides, animation state |
| `sessionStore` | Client | Current notebook, message history, auth user |
| `blockStore` | Client | Streamed `UIBlock`s for the active turn, by panel + order |
| Server state | Backend | Knowledge graph, vectors, profiles, review schedule |

**Deliberate rule (FR-UI-07):** the agent-chosen layout is a *suggestion* the user can override. On manual resize / mode switch, `uiStore` records the override and the UI Agent respects it for the rest of the session — adaptation never fights the user.

### 14.4 Design Tokens

A small, deliberate token set so the interface reads as one calm scholarly tool. Colour encodes meaning (agent tier, citation state, contradiction), not decoration.

| Token group | Values |
| --- | --- |
| Typography | Inter (UI) · Source Serif (long-form reading) · JetBrains Mono (code/citations) |
| Type scale | 12 / 14 / 16 / 20 / 28 / 36 px on a 1.25 ratio |
| Spacing | 4-px base grid (4, 8, 12, 16, 24, 32, 48) |
| Radius | 6 px controls · 10 px cards · 14 px panels |
| Surface | Near-white canvas, subtle slate borders, soft shadows; restrained, paper-like |
| Semantic colour | Tier accents (blue/green/violet/orange); green = grounded, amber = unverified, red = contradiction |
| Motion | 120–200 ms panel transitions; respects `prefers-reduced-motion` |

### 14.5 Web Design Principles
- **Stable mental model, dynamic content.** The three-panel frame is a constant; only contents and proportions adapt. Users are never disoriented by a wholly unfamiliar screen.
- **Structure before content.** Streamed components appear as skeletons immediately, so the page has shape within a second (perceived performance over raw latency).
- **Provenance is always one click away.** Every citation resolves to the exact source passage; trust is a first-class goal inherited from VERA AI.
- **Calm density.** Legible typographic hierarchy and whitespace over chrome; colour reserved for meaning.
- **Laptop-first, responsive-aware.** Primary target is a laptop browser; the shell degrades to a single-column stack on narrow viewports (mobile not a graded deliverable).

---

## 15. UX Flows and Interface States

Defining states explicitly is what keeps a streaming, agent-driven interface from feeling unpredictable.

### 15.1 First-Run Flow (Activation — tracked metric, ≥ 90%)
1. Sign in (Google OAuth or email) → land on an empty notebook with a single clear CTA: **add sources**.
2. Drag-and-drop or pick PDFs/DOCX, or paste a URL; each source shows a per-item ingestion progress state.
3. On first successful ingest, the Chat panel surfaces three suggested cross-document questions drawn from the new graph.
4. The user asks (or taps a suggestion); the first `CitedSummary` streams in — **activation achieved**.

### 15.2 Core Research Flow
Query → Orchestrator detects research intent → hybrid retrieval → Research Agent synthesises with grounding → Fact Checker verifies → UI Agent streams `CitedSummary` + `LiteratureMatrix` + `KnowledgeGraphView` while the shell animates into Research mode. The user can click any citation to open the source, or pivot into Writing mode to draft from the result.

### 15.3 Study Flow
Topic or document → Learning Agent generates a `FlashcardDeck` → cards enter the spaced-repetition schedule → each review updates the schedule via FSRS/SM-2 → `ProgressDashboard` reflects retention over time. The Socratic Tutor can be invoked at any point to probe understanding rather than reveal answers.

### 15.4 System State Taxonomy (every streamed component MUST define all four)

| State | What the user sees | Example |
| --- | --- | --- |
| Empty | A clear prompt to act, never a blank panel | New notebook → "Add your first source" |
| Loading | An immediate skeleton matching the component's shape | `CitedSummary` skeleton with shimmer lines |
| Partial | Real data filling in as agents complete | Matrix rows appearing one source at a time |
| Error | A plain-language cause and a retry affordance | "Couldn't read this PDF — it may be scanned. Retry with OCR?" |

### 15.5 Error and Degradation UX
Failures are designed for, not hidden. A failed source ingest is reported per-item with a cause and retry (FR-ING-08). A retriever outage degrades quietly — the answer still streams, with a subtle note that graph context was unavailable (NFR-REL-01). An LLM provider failure is invisible because the fallback provider takes over (NFR-REL-02). The system always returns something honest rather than failing silently or crashing the turn.

---

## 16. Output Artifacts and Payload Schemas

Arcana produces **in-app components** (GenUI blocks, §13) and **exportable artifacts** (downloadable files). Schemas are illustrative, finalised in FYP 1; producer and renderer/exporter must agree on shape.

### 16.1 In-App Component Payloads

```typescript
interface CitedSummaryData {
  answer: string;                 // synthesised, grounded prose
  citations: {
    marker: string;               // e.g. "[1]"
    doc_id: string;
    passage: string;              // exact supporting text
    page?: number;
  }[];
  confidence: "grounded" | "partial" | "unverified";
}

interface MatrixData {            // LiteratureMatrix
  dimensions: string[];           // columns, e.g. ["method","dataset","finding"]
  rows: {
    doc_id: string; title: string;
    cells: Record<string, string>;
    conflicts?: string[];         // dimensions where this source disagrees
  }[];
}

interface FlashcardDeckData {
  cards: {
    id: string; front: string; back: string;
    source: { doc_id: string; passage: string };
    schedule: { due: string; interval_days: number; ease: number };  // FSRS/SM-2
  }[];
  algorithm: "FSRS" | "SM-2";
}

interface SocraticDialogData {
  exchange: { role: "tutor" | "learner"; text: string }[];
  next_question: string;          // never an answer — always a probe
  bloom_level: "remember"|"understand"|"apply"|"analyze"|"evaluate"|"create";
  detected_misconception?: string;
}

interface PlagiarismReportData {
  originality_score: number;      // 0..1
  ai_likelihood: number;          // 0..1
  flagged: { passage: string; reason: string; suggestion?: string }[];
}
```

### 16.2 Exportable Artifacts

| Artifact | Format | Produced by | Phase |
| --- | --- | --- | --- |
| Formatted report | PDF | Document Agent | P1 |
| Editable document | DOCX | Document Agent | P1 |
| Slide deck | PPTX | Document Agent | P2 |
| Bibliography | BibTeX / RIS | Citation Agent | P1 |
| Knowledge-graph export | Obsidian vault | Document / Export | P1 |
| Flashcards | Anki deck | Export Agent | P2 |
| Audio overview | Audio file | Audio Agent | P2 |

Every exportable artifact **preserves provenance**: citations and source links survive the export so a downloaded report or vault remains traceable to the original corpus (see §19.3).

---

## 17. Functional Requirements

Requirements are grouped by subsystem and identified as `FR-<area>-<n>`. **Priority:** M/S/C/W. **Phase:** P0/P1/P2.

### 17.1 Document Ingestion (FR-ING)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-ING-01 | Users can upload PDF and DOCX documents into a notebook. | M | P0 |
| FR-ING-02 | Users can add a source by web URL; readable page content is extracted. | M | P1 |
| FR-ING-03 | Users can add a YouTube video; its transcript is ingested. | S | P1 |
| FR-ING-04 | Scanned/image PDFs are processed via OCR before extraction. | S | P1 |
| FR-ING-05 | Ingested text is chunked and embedded for vector retrieval. | M | P0 |
| FR-ING-06 | An LLM extracts entities and relationships as typed triples. | M | P0 |
| FR-ING-07 | Per-document ingestion progress and status are shown to the user. | S | P1 |
| FR-ING-08 | Failed ingestion is reported with a cause and is retryable. | M | P1 |
| FR-ING-09 | Entities are canonicalised so the same concept across documents is one node. | S | P1 |

### 17.2 Knowledge Graph (FR-KG)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-KG-01 | Builds a graph of Concept/Person/Document/Topic nodes with typed edges (mentions, supports, contradicts, defines, cited_by, related_to). | M | P0 |
| FR-KG-02 | The knowledge graph persists across sessions per user. | M | P1 |
| FR-KG-03 | Adding a document updates the graph incrementally without full reprocessing. | S | P1 |
| FR-KG-04 | Computes community clusters (Louvain) over the graph. | S | P1 |
| FR-KG-05 | Ranks node importance via PageRank. | S | P1 |
| FR-KG-06 | Identifies bridge concepts via betweenness centrality. | C | P1 |
| FR-KG-07 | Graph access is behind a GraphStore abstraction (NetworkX / Neo4j interchangeable). | M | P0 |
| FR-KG-08 | Users can view and navigate the knowledge graph interactively. | M | P1 |

### 17.3 Hybrid Retrieval (FR-RET)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-RET-01 | Retrieves via dense vector search over embeddings. | M | P0 |
| FR-RET-02 | Retrieves via BM25 keyword search. | M | P0 |
| FR-RET-03 | Retrieves via multi-hop graph traversal. | M | P0 |
| FR-RET-04 | Results from all three methods are merged via Reciprocal Rank Fusion. | M | P0 |
| FR-RET-05 | Users can ask cross-document comparison questions over the whole corpus. | M | P1 |
| FR-RET-06 | Surfaces contradictions between sources on a queried concept. | S | P1 |
| FR-RET-07 | Retrieval mode (local / global / hybrid) can be selected or auto-chosen. | C | P1 |
| FR-RET-08 | Every retrieved answer carries source attribution traceable to documents. | M | P0 |

### 17.4 Agents and Orchestration (FR-AGT)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-AGT-01 | An Orchestrator interprets user intent and routes to specialist agents. | M | P0 |
| FR-AGT-02 | Each agent exposes typed tool calls with defined arguments and results. | M | P0 |
| FR-AGT-03 | An agent can invoke another agent as a tool within a single task. | M | P1 |
| FR-AGT-04 | Agent execution runs on a shared stateful LangGraph execution graph. | M | P1 |
| FR-AGT-05 | Only tools relevant to the current intent are injected into an agent's context. | S | P1 |
| FR-AGT-06 | The platform provides 15+ agents across four tiers (full vision: 25). | M | P1 |
| FR-AGT-07 | Long-running agent tasks stream partial results to the user. | S | P1 |
| FR-AGT-08 | Agent or tool failures degrade gracefully without crashing the task. | M | P1 |
| FR-AGT-09 | The Fact Checker can verify generated claims before output is finalised. | S | P1 |
| FR-AGT-10 | Agent-to-agent recursion is bounded by a per-turn hop budget. | M | P1 |

### 17.5 Generative UI (FR-UI)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-UI-01 | The interface uses a three-panel layout: Sources, Chat, Studio. | M | P0 |
| FR-UI-02 | A catalog of pre-built, typed React components is available (target 24). | M | P1 |
| FR-UI-03 | Agents emit declarative typed component descriptions rather than raw text/HTML. | M | P1 |
| FR-UI-04 | A UI Agent selects which components to render from intent, mode and history. | M | P1 |
| FR-UI-05 | Panel widths and tool visibility adapt dynamically to the active configuration. | M | P1 |
| FR-UI-06 | At least 3 modes ship (Research, Writing, Study); architecture supports unbounded configurations. | M | P1 |
| FR-UI-07 | The user can manually override the agent-chosen layout/mode. | S | P1 |
| FR-UI-08 | Output complexity adapts to the user's profile (e.g. reading level). | C | P2 |
| FR-UI-09 | Streamed components render an immediate skeleton/loading state. | S | P1 |

### 17.6 Learning System (FR-LRN)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-LRN-01 | Generates flashcards from a document or topic. | M | P1 |
| FR-LRN-02 | Flashcards are scheduled for review via spaced repetition (FSRS/SM-2). | M | P1 |
| FR-LRN-03 | Generates quizzes (MCQ and short-answer) at selectable difficulty. | M | P1 |
| FR-LRN-04 | Produces Feynman-style simplified explanations and flags gaps. | S | P1 |
| FR-LRN-05 | Generates Cornell-style structured notes. | C | P1 |
| FR-LRN-06 | Provides blurting prompts and compares recall against sources. | C | P1 |
| FR-LRN-07 | Generates interleaved practice sets across topics. | C | P2 |
| FR-LRN-08 | A Socratic tutor guides via probing questions and never gives direct answers. | S | P1 |
| FR-LRN-09 | Supports Pomodoro sessions and personalised study schedules. | C | P1 |
| FR-LRN-10 | Tracks per-topic learning progress over time. | S | P1 |

### 17.7 Accounts and Persistence (FR-USR)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-USR-01 | Users can sign in via email or Google OAuth. | M | P1 |
| FR-USR-02 | A persistent user profile stores preferences and context. | M | P1 |
| FR-USR-03 | Users can organise documents into separate notebook workspaces. | M | P1 |
| FR-USR-04 | Interaction history persists across sessions and informs adaptation. | S | P1 |
| FR-USR-05 | User highlights and notes are ingested back into the knowledge graph. | S | P1 |
| FR-USR-06 | Each user's documents and graph are isolated from other users. | M | P1 |

### 17.8 Export and Interoperability (FR-EXP)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-EXP-01 | Users can export a generated report as a formatted PDF. | S | P1 |
| FR-EXP-02 | Users can export generated content as a DOCX file. | S | P1 |
| FR-EXP-03 | Users can export a generated slide deck (PPTX). | C | P2 |
| FR-EXP-04 | Users can generate an audio summary of content. | C | P2 |
| FR-EXP-05 | Users can import an Obsidian vault, preserving wikilinks as edges. | S | P1 |
| FR-EXP-06 | Users can export the knowledge graph to Obsidian vault format. | S | P1 |
| FR-EXP-07 | Users can export flashcards as an Anki deck. | C | P2 |
| FR-EXP-08 | Users can export citations as BibTeX / RIS. | S | P1 |
| FR-EXP-09 | Users can sync a notebook with a Google Drive folder. | C | P2 |

### 17.9 Analytics and Instrumentation (FR-ANL)

| ID | Requirement | Pri. | Phase |
| --- | --- | --- | --- |
| FR-ANL-01 | Retrieval quality metrics are logged for evaluation and tuning. | S | P1 |
| FR-ANL-02 | A study-effectiveness dashboard summarises learning progress. | C | P2 |
| FR-ANL-03 | Usage events are instrumented to support the FYP user study. | S | P1 |

---

## 18. Non-Functional Requirements

### 18.1 Performance
| ID | Requirement | Target |
| --- | --- | --- |
| NFR-PERF-01 | Time to first streamed token for a standard retrieval query. | < 3 s |
| NFR-PERF-02 | Full multi-agent synthesis for a typical research question. | < 15 s |
| NFR-PERF-03 | Ingestion time for a 20-page text PDF. | < 60 s |
| NFR-PERF-04 | Interactive graph render for up to 500 nodes. | < 2 s |

### 18.2 Scalability
| ID | Requirement | Target |
| --- | --- | --- |
| NFR-SCAL-01 | Documents per notebook. | ≥ 50 (FYP); 500+ design |
| NFR-SCAL-02 | Concurrent users during the study. | 10–15 |
| NFR-SCAL-03 | Graph/vector stores scale to production targets without architectural change. | Design requirement |

### 18.3 Reliability and Availability
| ID | Requirement | Target |
| --- | --- | --- |
| NFR-REL-01 | Failure of one retrieval method degrades quality but not availability. | Graceful degradation |
| NFR-REL-02 | Primary LLM failure falls back to the secondary provider. | Automatic fallback |
| NFR-REL-03 | Demo-environment uptime during evaluation and defence. | Stable for sessions |

### 18.4 Security and Privacy
| ID | Requirement | Target |
| --- | --- | --- |
| NFR-SEC-01 | All routes require an authenticated Firebase identity. | Enforced |
| NFR-SEC-02 | A user's corpus, graph and data are isolated from other users. | Per-user isolation |
| NFR-SEC-03 | Secrets are environment-injected, never committed. | Enforced |
| NFR-SEC-04 | GenUI agents emit data only; no executable code crosses the wire. | Schema-validated |

### 18.5 Usability and Maintainability
| ID | Requirement | Target |
| --- | --- | --- |
| NFR-USE-01 | System Usability Scale score from the user study. | ≥ 70 |
| NFR-USE-02 | Every streamed component defines empty/loading/partial/error states. | Required |
| NFR-MNT-01 | Storage backends are swappable behind abstractions (graph/vector/doc). | Required |
| NFR-MNT-02 | Adding a catalog component is a single registry entry plus its file. | Required |
| NFR-COST-01 | Third-party API spend stays within a student budget. | Capped, monitored |

---

## 19. Data Requirements

### 19.1 Core Entities
| Entity | Key fields |
| --- | --- |
| Document | id, notebook_id, title, type, source_uri, status, ingested_at |
| Chunk | id, doc_id, text, embedding_ref, position |
| GraphNode | id, type (Concept/Person/Document/Topic), label, properties |
| GraphEdge | id, source, target, relation, weight, evidence_chunk_ids |
| Notebook | id, user_id, name, created_at |
| UserProfile | id, preferences, complexity_level, interaction_history_ref |
| ReviewState | card_id, user_id, due, interval_days, ease, last_result |
| UIBlock (turn) | turn_id, type, data, meta, panel, order |

### 19.2 Data Storage Mapping
| Data | Store | Notes |
| --- | --- | --- |
| Knowledge graph (nodes, edges) | Neo4j (NetworkX in P0) | Behind the GraphStore abstraction |
| Chunk embeddings | Pinecone | 3,072-dimensional vectors |
| Documents, notebooks, users, profiles | Firestore | Managed NoSQL metadata |
| Review state, interaction history | Firestore | Drives spaced repetition + adaptation |
| Turn blocks (replay/analytics) | Firestore | Emitted UIBlocks per turn |
| Raw uploaded files | Object storage | Source of truth for re-processing |

### 19.3 Data Handling Rules
- User-uploaded content is processed only to provide Arcana's features and is not used to train external models.
- Derived artefacts (chunks, embeddings, graph nodes) are deleted when their source notebook is deleted.
- Generated answers and exports must retain traceable provenance back to source documents.

---

## 20. Analytics and Instrumentation

**Events to capture:**
- **Ingestion:** documents added, success/failure, time taken.
- **Retrieval:** query issued, per-method contributions, latency, result selected.
- **Agents:** agent invoked, agent-to-agent calls, tool calls, failures, hop depth.
- **Learning:** cards reviewed, quiz scores, review adherence.
- **UI:** mode entered, manual overrides, components rendered.

**Derived evaluation metrics:** retrieval accuracy + latency (benchmark), task completion / time-on-task / error rate (user study), citation accuracy (sampled). Analytics are for the author's own evaluation; no third-party advertising or tracking is integrated.

---

## 21. Assumptions, Constraints and Dependencies

**Assumptions:** users supply their own corpus; users work primarily in English; users work on a laptop/desktop browser; the VERA AI architecture and retrieval components can be reused as a baseline.

**Constraints:** two-semester FYP timeline, single developer; third-party API costs must stay within a student budget; production-only infrastructure is avoided where a free or local tier is sufficient.

**External dependencies:**
| Dependency | Used for |
| --- | --- |
| Claude API | Primary LLM reasoning, entity extraction, synthesis |
| OpenRouter | Fallback LLM provider |
| Pinecone | Vector storage and similarity search |
| OpenAI text-embedding-3-large | Embeddings (consistent with VERA AI baseline) |
| Neo4j Community / NetworkX | Knowledge graph storage |
| Firebase (Auth, Firestore) | Authentication and metadata/user storage |
| LangGraph | Multi-agent orchestration framework |
| Vercel AI SDK | Generative UI component streaming |
| Semantic Scholar / arXiv APIs | Academic paper discovery |

---

## 22. Risks and Mitigations

| ID | Risk | Sev. | Mitigation |
| --- | --- | --- | --- |
| R-01 | Scope too large for two semesters across three innovations. | High | Phase strictly; the hybrid-retrieval benchmark is the protected minimum deliverable; UI breadth is cut first. |
| R-02 | Benchmark comparison not methodologically fair. | High | Hold embeddings, corpus, questions constant; vary only retrieval; pre-register the question set. |
| R-03 | LLM API cost exceeds the student budget. | Med | Intent-scoped tool selection; caching; smaller models for non-critical steps; token-budget guard. |
| R-04 | Generative UI proves complex and time-consuming. | Med | Ship 3 required modes first; extra modes/components are Should/Could. |
| R-05 | User-study recruitment falls short of 10–15. | Med | Recruit early from peer cohorts; short sessions; contingency floor of 8. |
| R-06 | NetworkX→Neo4j migration introduces regressions. | Low | Use the GraphStore abstraction from day one. |
| R-07 | Entity extraction quality inconsistent across documents. | Med | Structured extraction; canonicalise entities; allow user correction of the graph. |
| R-08 | Supervisor assigned late, delaying scope sign-off. | Med | Proceed on the documented plan; keep Open Questions current. |
| R-09 | Agent-to-agent recursion loops or runs away. | Med | Hop budget and terminal-join guard (§11.6); cap invocations per turn. |
| R-10 | GenUI block schema drifts between backend and frontend. | Low | Single shared schema in `packages/schema`; server validates every block (fail closed). |

---

## 23. Evaluation Plan

**23.1 Quantitative retrieval benchmark.** A fixed evaluation set of cross-document questions (target: 20) is answered by Arcana's hybrid retrieval and a flat vector-RAG baseline. Embeddings, corpus and questions held constant; only the retrieval strategy varies (Listing 10.4). Primary measures: answer accuracy and citation correctness; secondary: latency. Informal NotebookLM comparison for external context.

**23.2 Structured user study.** 10–15 student participants complete standard tasks across Research, Study and Writing modes. Measures: task completion rate, time-on-task, error rate, SUS questionnaire, qualitative feedback.

**23.3 Acceptance linkage.** Results feed the §4 success metrics and §24 release criteria. A release is successful only if the primary retrieval metric shows a significant improvement over baseline **and** the usability score meets its target.

---

## 24. Release Criteria (FYP 2 MVP / Phase 1)

Considered complete and defensible when all hold:
- All Must-have (M) FRs for P0 and P1 are implemented and demonstrable.
- The full hybrid retrieval pipeline runs end-to-end on a real multi-document corpus.
- At least 15 agents operate with demonstrated agent-to-agent invocation.
- The Generative UI runs with at least the three required modes, with live component streaming.
- The learning module generates flashcards and schedules them via spaced repetition.
- The retrieval benchmark is complete and shows a statistically significant gain over the flat-RAG baseline.
- The user study is complete with ≥ 10 participants and a SUS score ≥ 70.
- No known defect prevents completion of the core Research, Study and Writing journeys.
- The FYP 2 report documents architecture, results and limitations.

Should/Could items not completed are recorded in the post-FYP roadmap rather than blocking release.

---

## 25. Open Questions

| ID | Question | Owner / next step |
| --- | --- | --- |
| Q-01 | How many agents are realistically implementable in FYP 2 — confirm 15+ vs timeline. | Author + supervisor at scope sign-off |
| Q-02 | Reframe the 25-agent figure as "designed" vs "implemented" to avoid examiner mismatch? | Author — align Concept Doc and PRD |
| Q-03 | Final size and sourcing of the 20-question retrieval benchmark set. | Author during system design |
| Q-04 | Which spaced-repetition algorithm is primary — FSRS or SM-2 — for the FYP build? | Author during learning-module design |
| Q-05 | Is Obsidian import/export a Phase 1 commitment or a Phase 2 stretch? | Author + supervisor |
| Q-06 | Minimum acceptable user-study sample if recruitment is hard (floor of 8?). | Author + supervisor |
| Q-07 | Hosting for the demo and study — fully local, or a low-cost cloud deployment? | Author during system design |
| Q-08 | Programme, student ID and supervisor details for document headers. | Author — administrative |
| Q-09 | Final hop-budget and token-budget values for the agentic pipeline. | Author during pipeline implementation |
| Q-10 | Should the 24-component catalog be trimmed to a core set for the graded build? | Author + supervisor |

---

## 26. Glossary

| Term | Definition |
| --- | --- |
| Agent | A specialised LLM-driven module with a defined role and a set of tool calls. |
| Agent-to-agent invocation | One agent calling another agent as a tool within a single task (`route_to_agent`). |
| A2UI | Agent-to-User-Interface; a declarative protocol for agents to describe interface components. |
| BM25 | A keyword-based ranking function for exact-term retrieval. |
| Composability | The property that agents can be combined and can invoke one another. |
| Generative UI (GenUI) | An interface assembled at runtime from typed components chosen by an agent. |
| GraphRAG | Retrieval-augmented generation that retrieves over a knowledge graph, not only flat chunks. |
| Hybrid retrieval | Retrieval combining graph traversal, vector search and BM25, merged via RRF. |
| Intent-scoped tool selection | Injecting only the tools relevant to the current intent into a prompt. |
| Knowledge graph | A network of typed nodes (concepts, people, documents, topics) and typed edges. |
| MoSCoW | A prioritisation scheme: Must, Should, Could, Won't have. |
| RRF | Reciprocal Rank Fusion; a rank-based method for merging results from multiple retrievers. |
| Spaced repetition | Scheduling reviews at increasing intervals to maximise long-term retention. |
| UIBlock | The typed unit of GenUI: `{ type, data, meta }` naming a catalog component. |
| VERA AI | The author's prior enterprise RAG assistant; the baseline Arcana extends. |

---

*End of Document · Arcana PRD v0.2 (Engineering Edition) · Implementation source of truth · May 2026*
