# Arcana — Environment & Secrets Generation Guide

> How to obtain every credential Arcana needs, what each variable does, and how the three environment profiles differ. Companion to `arcana_prd.md` (§9.3, §21.3) and `project_file_structure.md` (`infra/env/`). Referenced from `CLAUDE.md`.
>
> **Golden rule:** secrets are environment-injected and **never committed** (NFR-SEC-03). The repo ships `.env.example` files with every key documented and empty; real values live only in local `.env` files and your deploy platform's secret store.

---

## 0. The three profiles

Arcana's `Settings` object (`api/core/settings.py`) selects behaviour by the `ENV` variable. Each profile is just a different `.env` file under `infra/env/`.

| Profile | `ENV` | Graph backend | Intended use | What you need keys for |
| --- | --- | --- | --- | --- |
| **local** | `local` | NetworkX (in-process) | Day-to-day development on the demo corpus | LLM, embeddings, vector store, Firebase (can stub) |
| **study** | `study` | NetworkX or Neo4j | The configuration used for the benchmark + user study | Everything `local` needs, reliably provisioned |
| **prod-design** | `prod-design` | Neo4j | Documented production target (not required for the FYP) | Adds a managed Neo4j instance |

You can run the **entire FYP** on `local` and `study`. Neo4j is only required for `prod-design`; in `local`/`study` the NetworkX backend means **no graph database to provision** — one fewer credential to manage early on.

---

## 1. Backend variables — `api/.env`

Below is the complete backend env file. Each section explains what the variable is, where to get it, and whether it is required for the FYP.

```bash
# ─────────────────────────────────────────────────────────────
# CORE / PROFILE
# ─────────────────────────────────────────────────────────────
ENV=local                                  # local | study | prod-design
GRAPH_BACKEND=networkx                      # networkx | neo4j
LOG_LEVEL=INFO

# ─────────────────────────────────────────────────────────────
# LLM — PRIMARY (Anthropic Claude)        [REQUIRED]
# ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=
LLM_PRIMARY=claude-sonnet                   # model string used by LLMService
LLM_PRIMARY_MAX_TOKENS=4096

# ─────────────────────────────────────────────────────────────
# LLM — FALLBACK (OpenRouter)             [RECOMMENDED]
# ─────────────────────────────────────────────────────────────
OPENROUTER_API_KEY=
LLM_FALLBACK=openrouter/auto                # any OpenRouter-routable model

# ─────────────────────────────────────────────────────────────
# EMBEDDINGS (OpenAI)                     [REQUIRED]
# ─────────────────────────────────────────────────────────────
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-large      # 3072-dim — keep identical to VERA AI baseline

# ─────────────────────────────────────────────────────────────
# VECTOR STORE (Pinecone)                 [REQUIRED]
# ─────────────────────────────────────────────────────────────
PINECONE_API_KEY=
PINECONE_INDEX=arcana                       # 3072-dim, cosine metric
PINECONE_ENVIRONMENT=                       # serverless region, e.g. us-east-1

# ─────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH (Neo4j)                 [OPTIONAL — only if GRAPH_BACKEND=neo4j]
# ─────────────────────────────────────────────────────────────
NEO4J_URI=                                  # bolt://localhost:7687 or neo4j+s://<id>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=

# ─────────────────────────────────────────────────────────────
# FIREBASE (Auth + Firestore)             [REQUIRED for P1; stubbable in P0]
# ─────────────────────────────────────────────────────────────
FIREBASE_PROJECT_ID=
FIREBASE_CLIENT_EMAIL=                      # from the service-account JSON
FIREBASE_PRIVATE_KEY=                       # paste with literal \n preserved, wrapped in quotes
# (Alternative: GOOGLE_APPLICATION_CREDENTIALS=/abs/path/to/service-account.json)

# ─────────────────────────────────────────────────────────────
# ACADEMIC PAPER DISCOVERY                 [OPTIONAL — Web Search Agent, P1]
# ─────────────────────────────────────────────────────────────
SEMANTIC_SCHOLAR_API_KEY=                   # optional — works keyless at lower rate limits
# arXiv needs no key.

# ─────────────────────────────────────────────────────────────
# RETRIEVAL / PIPELINE TUNING (defaults shown)
# ─────────────────────────────────────────────────────────────
RRF_K=60                                    # Reciprocal Rank Fusion constant
MAX_TOOLS_PER_PROMPT=12                     # intent-scoping cap (§11.5)
HOP_BUDGET=4                                # max agent-to-agent recursion depth (§11.6, Q-09)
TOKEN_BUDGET_PER_TURN=60000                 # cost guard; downgrade then hard-stop (R-03, Q-09)

# ─────────────────────────────────────────────────────────────
# OBJECT STORAGE for raw files             [REQUIRED for P1]
# ─────────────────────────────────────────────────────────────
STORAGE_BUCKET=                             # Firebase Storage bucket or local path in `local`
```

---

## 2. How to obtain each credential

> Sign-up flows and free-tier limits change over time — when in doubt, follow the official console and check current pricing there. The steps below are the stable shape of each process.

### 2.1 Anthropic Claude — `ANTHROPIC_API_KEY` *(required)*
1. Create an account at the Anthropic Console (`console.anthropic.com`).
2. Add billing (pay-as-you-go; there is usually a small starter credit).
3. **API Keys → Create Key**, copy it once (it is shown only once).
4. Paste into `ANTHROPIC_API_KEY`.
- **Used by:** every agent's reasoning, entity extraction, synthesis. This is the most cost-sensitive key — the token budget guard (`TOKEN_BUDGET_PER_TURN`) exists to protect it (R-03).

### 2.2 OpenRouter — `OPENROUTER_API_KEY` *(recommended)*
1. Sign up at `openrouter.ai`.
2. Add a small credit balance.
3. **Keys → Create Key**, copy, paste into `OPENROUTER_API_KEY`.
- **Used by:** the fallback path in `LLMService` (NFR-REL-02). If Claude rate-limits or times out, the identical request retries here. You can skip this for very early P0 work, but it satisfies NFR-REL-02 and is cheap insurance for the demo/defence.

### 2.3 OpenAI embeddings — `OPENAI_API_KEY` *(required)*
1. Create an account at the OpenAI platform (`platform.openai.com`).
2. Add billing.
3. **API keys → Create new secret key**, copy, paste into `OPENAI_API_KEY`.
- **Used by:** `api/ingestion/embedder.py` and query embedding. **Keep `text-embedding-3-large` (3072-dim)** — it must match the VERA AI baseline so the benchmark comparison stays fair (R-02). Changing the embedding model invalidates a like-for-like comparison.

### 2.4 Pinecone — `PINECONE_API_KEY`, `PINECONE_INDEX`, `PINECONE_ENVIRONMENT` *(required)*
1. Sign up at `pinecone.io` (a free serverless tier is usually available).
2. Create an index named `arcana` with **dimension 3072** and **cosine** metric (must match the embedding model).
3. From the console: copy the API key → `PINECONE_API_KEY`; note the index name → `PINECONE_INDEX`; note the serverless region → `PINECONE_ENVIRONMENT`.
- **Used by:** `api/stores/vector_store.py` and the dense retriever (`retrieval/vector.py`).

### 2.5 Neo4j — `NEO4J_*` *(optional; only when `GRAPH_BACKEND=neo4j`)*
- **Local option:** install Neo4j Community / Desktop and run it; URI is `bolt://localhost:7687`, set your own password.
- **Managed option:** Neo4j AuraDB Free gives a hosted instance; copy the `neo4j+s://…` URI, username, and the generated password.
- **Used by:** `api/stores/neo4j_store.py`. **Skip entirely while `GRAPH_BACKEND=networkx`** — the GraphStore abstraction (FR-KG-07) means the rest of the system doesn't care which backend is active.

### 2.6 Firebase — `FIREBASE_*` *(required for P1, stubbable in P0)*
1. Create a project in the Firebase console (`console.firebase.google.com`).
2. **Authentication → Sign-in method:** enable **Email/Password** and **Google** (FR-USR-01).
3. **Firestore Database:** create a database (start in test mode locally; lock down with rules before the study).
4. **Project settings → Service accounts → Generate new private key** → downloads a JSON. From it:
   - `project_id` → `FIREBASE_PROJECT_ID`
   - `client_email` → `FIREBASE_CLIENT_EMAIL`
   - `private_key` → `FIREBASE_PRIVATE_KEY` (keep the `\n` escapes; wrap the whole value in double quotes)
   - *Or* simply set `GOOGLE_APPLICATION_CREDENTIALS` to the JSON's absolute path and skip the three split vars.
5. **Storage:** enable a bucket → `STORAGE_BUCKET`.
- **Used by:** `api/core/auth.py` (verifies Firebase ID tokens — NFR-SEC-01), `api/stores/doc_store.py` (Firestore metadata + Storage for raw files).
- **P0 shortcut:** while there are no real users, you can stub auth (a fixed dev user) and store metadata locally, deferring Firebase until P1 §1.8.

### 2.7 Semantic Scholar / arXiv *(optional; Web Search Agent, P1)*
- **arXiv:** no key needed.
- **Semantic Scholar:** works without a key at modest rate limits; request an API key from their site for higher limits and set `SEMANTIC_SCHOLAR_API_KEY`.
- **Used by:** `api/agents/tier4/web_search.py`. Scope reminder: academic paper discovery only — not general web search.

---

## 3. Frontend variables — `web/.env.local`

Next.js exposes only `NEXT_PUBLIC_*` vars to the browser; everything else stays server-side. The frontend needs the **client** Firebase config (safe to expose) and the backend URL.

```bash
# Backend API base (FastAPI)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# Firebase CLIENT config — from Project settings → General → "Your apps" (Web app)
# These are publishable client identifiers, not secrets.
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
```

> The **service-account** key (§2.6) is backend-only and must **never** appear in `web/`. The client config above is a different, publishable set generated when you register a Web app in Firebase.

---

## 4. Minimum keys to get moving

| Milestone | Keys you actually need |
| --- | --- |
| **First P0 ingest + retrieval demo** | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `PINECONE_API_KEY` (+ index). NetworkX needs none; auth stubbed. |
| **Add fallback + paper discovery** | `+ OPENROUTER_API_KEY`, (optional) `SEMANTIC_SCHOLAR_API_KEY` |
| **P1 accounts, persistence, study** | `+ FIREBASE_*` (server) and `NEXT_PUBLIC_FIREBASE_*` (client), `STORAGE_BUCKET` |
| **prod-design only** | `+ NEO4J_*` and `GRAPH_BACKEND=neo4j` |

---

## 5. Security & hygiene checklist
- [ ] `.env`, `.env.local`, and any service-account JSON are in `.gitignore`. Verify with `git status` before the first commit.
- [ ] Only `.env.example` / `infra/env/*.example` (empty placeholders) are committed.
- [ ] No key is read directly from `os.environ` in feature code — everything goes through `Settings` (`api/core/settings.py`).
- [ ] `FIREBASE_PRIVATE_KEY` newlines are preserved (quoted, `\n` intact) or you used `GOOGLE_APPLICATION_CREDENTIALS` instead.
- [ ] The Pinecone index dimension (3072) matches `EMBEDDING_MODEL`.
- [ ] Firestore security rules enforce per-user isolation before the user study (NFR-SEC-02).
- [ ] `TOKEN_BUDGET_PER_TURN` is set conservatively while developing to avoid runaway LLM spend (R-03).
- [ ] If a key leaks, rotate it in the provider console immediately and purge it from git history.

---

## 6. Local bootstrap (suggested)

```bash
# from repo root
cp infra/env/local.env.example api/.env          # fill in the 3 required keys
cp web/.env.local.example web/.env.local          # API base + (later) Firebase client config
make up                                            # docker-compose: api + web (+ neo4j if enabled)
make ingest-demo                                   # ingest the demo corpus into NetworkX + Pinecone
# open http://localhost:3000 → create a notebook → ask a cross-document question
```

---

*Companion to `arcana_prd.md`, `project_file_structure.md`, and `checklist.md`. Keep variable names in sync with `api/core/settings.py`.*
