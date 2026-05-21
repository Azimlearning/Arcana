# Arcana

> The AI Research Assistant That Connects What Others Miss
> Final Year Project · Universiti Teknologi PETRONAS

Arcana is a **graph-native, multi-agent research and learning platform**.
It ingests documents into a knowledge graph plus vector index and answers
cross-document questions with grounded, cited summaries. The defining
engineering claim is composability — specialised agents collaborate over
shared state, and the interface is itself an agent output.

This repository is the **P0 walking skeleton** — one PDF, one question,
one streaming `CitedSummary` block, end-to-end. The full 15+ agent MVP
lands in P1 (FYP 2); the complete 25-agent vision is the P2 roadmap.

## Quick start

**Prerequisites**

- Node 20+ and `corepack` (ships with Node)
- Python 3.11 or 3.12
- `uv` (`pip install uv`)
- Accounts: [Anthropic](https://console.anthropic.com), [OpenAI](https://platform.openai.com), [Pinecone](https://app.pinecone.io)

**1. Install workspace + Python deps**

```bash
corepack pnpm install
uv sync --dev
```

**2. Fill in credentials**

```bash
cp infra/env/local.env.example api/.env
cp web/.env.local.example      web/.env.local
# Edit api/.env with your Anthropic, OpenAI, and Pinecone keys.
# See docs/env_generation_guide.md for where each key comes from.
```

Create a Pinecone serverless index named `arcana` with **dimension 3072,
metric cosine** — those values must match what `text-embedding-3-large`
emits (R-02).

**3. Build the schema, ingest a PDF, run both apps**

```bash
# Build the shared wire-contract package (once after every schema change)
corepack pnpm --filter @arcana/schema build

# Drop a PDF into eval/corpus/, then ingest it
make ingest-demo

# Two terminals:
make up-api      # FastAPI on :8000
make up-web      # Next.js on :3000
```

Open [`http://localhost:3000`](http://localhost:3000) — it redirects to
`/notebooks/demo`, shows the three-panel shell, accepts a question, and
streams back a CitedSummary block with clickable inline citations.

## Testing

```bash
uv run pytest -q api/                                    # backend  (200+ tests)
corepack pnpm --filter @arcana/web test                  # frontend (7 tests)
corepack pnpm --filter @arcana/schema codegen:check      # schema drift
uv run ruff check api/                                   # backend lint
uv run --with pyright pyright api/                       # backend types
corepack pnpm --filter @arcana/web typecheck             # frontend types
corepack pnpm --filter @arcana/web build                 # production build
```

## What ships in this slice

- ✅ PDF ingestion → chunking → embedding → Pinecone upsert + chunk store
- ✅ Hybrid retrieval (vector + BM25; graph stub) with RRF fusion
- ✅ Three-agent path: Orchestrator → Research → UI Agent
- ✅ Typed `UIBlock` wire contract with schema-drift CI gate
- ✅ Fail-closed server-side validation + SSE streaming
- ✅ Next.js 14 frontend with registry-based GenUI and all four block states

## What lands later

- P1 (FYP 2 MVP): the other 12+ agents, LangGraph `StateGraph`, Fact
  Checker, Memory Agent, entity extraction, Neo4j, full 24-component
  catalog, ≥3 modes, Firebase auth, the 20-question benchmark, the user
  study. See [`docs/checklist.md`](docs/checklist.md) §1.
- P2 (post-FYP): complete 25-agent suite, audio/video, real-time
  collaboration, mobile. See [`docs/checklist.md`](docs/checklist.md) §2.

## Documentation

- [`docs/arcana_prd.md`](docs/arcana_prd.md) — the full product spec (single source of truth)
- [`docs/project_file_structure.md`](docs/project_file_structure.md) — canonical repo layout
- [`docs/uiux_plan.md`](docs/uiux_plan.md) — design tokens, modes, 24-component catalog
- [`docs/checklist.md`](docs/checklist.md) — phased build plan with FR/NFR/R IDs
- [`docs/env_generation_guide.md`](docs/env_generation_guide.md) — every env var, where to get each credential
- [`CLAUDE.md`](CLAUDE.md) — operating brief for the coding agent
- [`.claude/memory/decisions.md`](.claude/memory/decisions.md) — ADR log (slice deferrals etc.)

## License

Proprietary — FYP submission. Contact the author for use beyond academic review.
