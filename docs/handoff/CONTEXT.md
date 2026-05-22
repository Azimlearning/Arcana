# Arcana — Current State of Play

> Narrative snapshot of what's shipped, what's deferred, and where the
> next agent picks up. Companion to [`SETUP.md`](SETUP.md) (how to get
> the gates green) and [`PROCESS.md`](PROCESS.md) (how we build).
>
> If anything here disagrees with `.claude/memory/decisions.md` or the
> code itself, those win. This file is a guide, not the spec.

## The 60-second pitch

Arcana is a **graph-native, multi-agent research and learning platform**
for students and academic researchers. It ingests documents (PDFs at
slice scale; DOCX/web/YouTube/OCR in P1) into a knowledge graph plus
vector index, and answers cross-document questions with grounded, cited
summaries. The defining engineering claim is **composability** —
specialised agents collaborate over shared state, and the interface
itself is an agent output (the GenUI catalog).

The author is building this as their FYP at Universiti Teknologi
PETRONAS. The graded build (P1) ships a 15+ agent MVP with a 24-component
GenUI, five demonstrated modes, a learning system, accounts, and a
hybrid-vs-flat RAG benchmark with a user study. The post-FYP roadmap
(P2) completes the 25-agent suite, audio/video, real-time collaboration,
and mobile.

## Where we are in the build

| | |
|---|---|
| **Branch** | `ExDev` (parent of all the work) |
| **P0 walking skeleton** | ✅ commit `267b035` — one PDF → one CitedSummary, every layer wired |
| **Slice 1 — agent maturity** | ✅ HEAD — LangGraph + entity extraction + real GraphRetriever + Fact Checker + Memory Agent |
| **Tests** | 263 backend (pytest) + 7 frontend (vitest) — all green |
| **Open warnings from slice-1 reviewer** | 5 non-blocking (logged in `decisions.md` and in the CR section below) |

There are **roughly 14 more slices to P1 done**, then 4–5 P2 slices.
Slice 2 is the natural next step: GenUI catalog breadth.

## What's done — P0 (commit 267b035)

The P0 commit shipped the walking skeleton — *one* path end-to-end:

- **Monorepo + shared schema** (`packages/schema/`) — TypeScript wire
  contract with a ts-morph–based codegen that emits Pydantic into
  `api/genui/_generated.py`. The `codegen:check` step in CI detects drift.
- **`api/core/`** — typed `Settings(BaseSettings)`, structlog JSON,
  `ArcanaError` hierarchy, `TokenBudget` (per-turn cost + hop guard).
- **`api/llm/`** — `LLMService` with Anthropic primary + OpenRouter stub,
  disk cache, AllProvidersFailed semantics.
- **`api/embeddings/`** — OpenAI `text-embedding-3-large` @ 3072d, ASCII
  batching, fail-loud on dimension mismatch (R-02 fairness).
- **`api/stores/`** — `GraphStore` ABC (NetworkX impl with JSON node-link
  persistence, NOT pickle), `VectorStore` ABC (Pinecone REST via httpx —
  no SDK), `DocStore` ABC (filesystem impl with strict doc-id allowlist),
  `ChunkStore` ABC (JSONL impl for BM25 source).
- **`api/ingestion/`** — PDF parser (PyMuPDF), paragraph-aware chunker
  with min-chunk-size floor, content-addressable per-doc chunk IDs.
- **`api/retrieval/`** — dense (Pinecone), BM25 (rank-bm25 with ASCII
  tokenizer for benchmark reproducibility), graph stub, RRF fusion,
  hybrid with NFR-REL-01 degradation.
- **`api/agents/`** — `BaseAgent`, `@tool` decorator, `route_to_agent`,
  `Orchestrator` (direct-call sequencer), `ResearchAgent` with citation
  parser, `UIAgent` (only agent that picks components).
- **`api/genui/` + `api/routes/`** — fail-closed validator, W3C-SSE
  streamer, `POST /chat` route with anti-buffering headers.
- **`web/`** — Next 14 App Router, 3-panel shell, typed registry-based
  GenUI catalog (`CitedSummary` only), all four states wired
  (Empty/Loading/Partial/Error), fetch+ReadableStream SSE consumer.
- **`eval/`** — corpus directory, draft questions.yaml, ingest_demo
  driver, stubs for benchmark/baseline/metrics.
- **Tooling** — Makefile (`make help` shows targets),
  `.github/workflows/ci.yml` with backend + frontend jobs.

## What's done — Slice 1 (HEAD)

Slice 1 is the **agent-maturity slice**. Five chunks, in dependency
order. Each chunk landed with a code review and gates green.

### Chunk 1 — LangGraph StateGraph

- `api/agents/graph.py` — `build_graph()` compiles a `StateGraph` keyed
  on `AgentState`. Orchestrator becomes the graph runner; the
  orchestrator NODE is a free function (`_orchestrator_node`) so
  invoking the agent class from inside the graph can't recurse.
- `AgentState` gained `Annotated[..., reducer]` on `messages`,
  `retrieved_ctx`, `agent_results`, `ui_blocks`. The custom reducer
  `_merge_agent_results` lets later agents overwrite an entry by id.
- `make_node` snapshots list lengths before `agent.run` and returns
  only the deltas — so `add`-reducers don't double-count.

### Chunk 2 — Entity extraction

- `api/llm/prompts/extraction.py` — JSON-mandating extraction system
  prompt with `EXTRACTION_PROMPT_VERSION = "v1"` for R-02 reproducibility.
- `api/ingestion/extractor.py` — defensive parser (handles markdown
  fences, leading prose, partial garbage), CamelCase-aware slug
  canonicalisation (`GraphRAG` and `graph rag` → `graph_rag`).
- `api/ingestion/pipeline.py` — per-chunk extraction with
  fetch-merge-upsert on the graph store; `mentioned_in_chunks` +
  `doc_ids` accumulate across chunks; per-chunk failures log and skip
  (the doc still ingests).
- `GraphStore.get_node` added to the ABC (needed for the merge).

### Chunk 3 — Real GraphRetriever

- `api/retrieval/graph.py` — query → entity extraction → matched-entity
  lookup → 1-hop expand → score chunks (direct match 1.0, neighbor 0.5)
  → fetch text via ChunkStore. `GRAPH_SCORING_VERSION = "v1"`.
- Degrades cleanly if `llm` or `chunk_store` is missing (slice-0 path).
- Missing chunks in the store (graph references deleted chunks) silently
  skipped — no crash.

### Chunk 4 — Fact Checker

- `api/agents/tier4/fact_checker.py` — verdict-producing (does NOT
  mutate research's payload). Reads each citation's quote vs the summary,
  asks the LLM "supported?", returns `{checked, verified, dropped_ids}`.
- `UIAgent` reads `state.agent_results["fact_checker"]`, filters
  citations + segments, downgrades status from `ready` to `partial` when
  more than 50% are dropped.
- LLM failure → fail-safe (treat all as supported; don't penalize a
  legitimate turn for a provider outage).

### Chunk 5 — Memory Agent

- `api/stores/memory_store.py` + `api/stores/in_memory_store.py` —
  per-notebook chat history. In-memory now; Firestore swap is the same
  ABC pattern (P1 §1.8).
- `api/agents/tier4/memory.py` — runs FIRST in the graph (`START →
  memory → orchestrator → ...`). Loads up to `max_history=20` recent
  messages; appends current user query.
- `Orchestrator._persist_turn_to_memory` — writeback after the graph
  completes. **Error blocks don't pollute history** (apology strings
  would bias the model toward more apologies — code-reviewer flagged
  this; the gate is `block.meta.status != "error"`).
- `build_graph` is conditional: wires memory + fact_checker if
  registered, falls through to the slice-0 direct edges if not. Old
  test constructions `Orchestrator(research=, ui_agent=)` keep working.

## What's deferred (and WHY)

ADRs live in `.claude/memory/decisions.md`. Highlights from the slice's
deferral list (don't rebuild them without thinking — they're deliberate):

- **DocStore is a filesystem stub.** Firebase Firestore lands in P1 §1.8
  with accounts.
- **The 22 remaining agents** are P1 §1.5. Don't start building tier-2
  agents (Writing, Study, Socratic, Discovery, Learning) before the next
  slice's GenUI catalog is in place — they need components to emit into.
- **DOCX / web / YouTube parsers + OCR** — P1 §1.1.
- **Neo4j swap** — P1 §1.2. The GraphStore ABC is the seam; flip
  `graph_backend=neo4j` in settings once the impl ships.
- **Eval benchmark + user study** — P1 §1.12, slice 11.
- **Auth + accounts** — P1 §1.8, slice 7.

## Active architectural decisions

| Decision | Location | Why |
|---|---|---|
| Python `pyproject.toml` at repo root (not `api/`) | `decisions.md` 2026-05-21 | The dependency-direction hook matches `api.<layer>.*` import prefixes — package must sit above `api/`. |
| Spec docs under `docs/` (moved from root) | `decisions.md` 2026-05-21 | CLAUDE.md + preflight + project_file_structure all reference `docs/...`. |
| `api/embeddings/` separate from `api/llm/` | `decisions.md` (chunk 3 of P0) | User-requested split; embeddings is its own peer service. |
| GraphStore persistence as JSON node-link (not pickle) | `decisions.md` + `networkx_store.py` | Pickle-load exec gadget — JSON is content-only. |
| Pinecone via raw httpx (no SDK) | `decisions.md` + `pinecone_store.py` | Matches Anthropic provider pattern; avoids vendored SDK quirks; cleaner respx tests. |
| LangGraph 0.2+ with Pydantic `AgentState` | `decisions.md` 2026-05-22 (slice 1) | Reducers via Annotated; mutation persists within a node call via Python aliasing. |
| Citation parser lives in research agent (not next to prompt) | `decisions.md` (slice 0) | Cohesion — parser needs LLM output + source chunks together. |
| Per-prompt VERSION constants | `extraction.py`, `fact_checker.py`, `graph.py` | R-02 benchmark reproducibility — bump on every edit. |

## Open warnings (slice-1 code reviewer; non-blocking)

These were flagged at the end of slice 1 but **don't block the slice
commit**. Address them when they next become load-bearing:

1. **Partial-graph state visibility.** When entity extraction fails for
   chunk N, the doc still marks `ready` but the graph reflects a subset.
   Acceptable today; P1 should surface `extracted_chunks / total_chunks`
   in metadata.
2. **`make_node` doesn't propagate `agent_results` mutations to other
   keys.** Each agent's wrapper returns `{agent.name: result}` — if an
   agent ever mutates another agent's entry in `state.agent_results`,
   that mutation is lost across the reducer. None currently do, but the
   contract is implicit. Document or assert.
3. **Per-doc graph operations are O(chunks × entities).** 50 chunks × 5
   entities = 250 fetch-merge-upsert round-trips. Fine for NetworkX
   in-process; expensive over Neo4j network. P1 should add a batch
   `upsert_nodes_batch` to the ABC.
4. **Truncated-quote false-drops in Fact Checker.** Quotes >280 chars
   are truncated pre-LLM. The model could falsely reject a legitimate
   citation if the supporting text is past the cap. Bump cap or
   add a "this quote was truncated" warning at the prompt level.
5. **Fact Checker prompt invalidates benchmark on edit.** Bump
   `FACT_CHECK_PROMPT_VERSION` on every edit. The eval harness should
   record this version alongside results when slice 11 runs.

## The next slice's outline (Slice 2 — GenUI catalog breadth)

Sketched in the slice-0 closeout message; not yet ADR'd. The intent:

- Add 4–5 GenUI catalog components: `LiteratureMatrix`,
  `ContradictionAlert`, `GapAnalysis`, `InsightCard`,
  `KnowledgeGraphView`. Each is the three-step change:
  schema variant → React component (all four states) → registry line.
- Codegen will mirror schema changes into `_generated.py` automatically.
- Teach the UI Agent to **pick** components based on intent/mode (right
  now it always picks `CitedSummary`). This is FR-UI-04.
- New agents that produce data for these components (`Discovery`,
  `Visual`) — but only their payload-producing parts. Mode-specific
  agents (Writing, Study, Socratic) land in slices 4–6.

When you start slice 2, read **PROCESS.md** for the preflight ritual,
then write the slice plan into a new ADR before any code.
