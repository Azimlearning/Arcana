# Arcana — Deployment Guide

> How to take the dev-only stack (Next.js on `localhost:3000`, FastAPI on
> `localhost:8000`, JSONL persistence) to a deployed environment. Companion
> to `docs/env_generation_guide.md` (where each credential comes from).

## Topology

| Piece | Where | How |
|---|---|---|
| `web/` (Next.js 14) | **Vercel** | `vercel.json` at repo root builds `@arcana/schema` then `@arcana/web` |
| `api/` (FastAPI) | Any container host (Cloud Run / Render / Railway) | `infra/Dockerfile.api` |
| Persistence | **Firestore** | `NOTEBOOK_BACKEND` / `EVENT_BACKEND` / `PROFILE_BACKEND` = `firestore` |
| Auth | Firebase | already wired (`api/core/auth.py`); set `FIREBASE_PROJECT_ID` |
| Vectors / graph | Pinecone / NetworkX-on-disk | unchanged from dev (Neo4j swap is P2) |

## 1. Web app → Vercel

The repo is a pnpm workspace; `web/` imports `@arcana/schema`, which must be
built first. The root `vercel.json` encodes this:

```json
{
  "installCommand": "pnpm install",
  "buildCommand": "pnpm --filter @arcana/schema build && pnpm --filter @arcana/web build",
  "outputDirectory": "web/.next",
  "framework": "nextjs"
}
```

Steps:

1. `vercel link` from the repo root (or import the Git repo in the Vercel
   dashboard). Leave **Root Directory at the repo root** — `vercel.json`
   handles the monorepo build.
2. Set the environment variables (Project → Settings → Environment Variables).
   Everything the browser needs is `NEXT_PUBLIC_*` — publishable identifiers
   only, never server keys (see `web/.env.local.example`):
   - `NEXT_PUBLIC_API_BASE_URL` — the deployed API origin (step 2 below).
   - `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`,
     `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`,
     `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`
     — the Firebase *client* config (Firebase console → Project settings →
     Your apps).
3. Deploy. Note the production origin (e.g. `https://arcana-web.vercel.app`).

## 2. API → container host

`infra/Dockerfile.api` builds a reproducible image from `uv.lock`:

```bash
docker build -f infra/Dockerfile.api -t arcana-api .
docker run -p 8000:8000 --env-file api/.env arcana-api   # local smoke test
```

Deploy the image to any container platform (Cloud Run and Render both
honour the `$PORT` convention the image uses). Required env vars — same
names as `infra/env/local.env.example`:

- **Required:** `OPENAI_API_KEY`, `PINECONE_API_KEY` (+ `PINECONE_INDEX`),
  and `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY` for the LLM tiers.
- **Auth (production):** `FIREBASE_PROJECT_ID` — switches `get_current_user`
  from the `X-Dev-User-Id` dev stub to real Firebase JWT verification.
  Set `ENV=study` (or `prod-design`) so the dev stub is disabled.
- **Persistence:** `NOTEBOOK_BACKEND=firestore`, `EVENT_BACKEND=firestore`,
  `PROFILE_BACKEND=firestore`, plus the service-account pair
  `FIREBASE_CLIENT_EMAIL` / `FIREBASE_PRIVATE_KEY` (Firebase console →
  Project settings → Service accounts → Generate new private key; paste the
  key with `\n` escapes intact). Without these flags the API falls back to
  JSONL files inside the container — fine for a demo, lost on redeploy
  unless you mount a volume at `/data`.
- **CORS:** `CORS_ORIGINS=https://<your-web-origin>` (comma-separated list;
  defaults to `http://localhost:3000`).

## 3. Firestore data model (for reference / security rules)

All server-side access uses the service account (Admin-equivalent); the
browser never talks to Firestore directly, so rules can deny all client
access:

```
users/{uid}                      — marker doc (uid field) for user enumeration
users/{uid}/notebooks/{id}       — Notebook documents (FR-USR-03/06)
users/{uid}/turns|feedback|surveys|events/{uuid} — analytics events (FR-ANL)
users/{uid}/profile/main         — UserProfile document (FR-USR-02)
```

## 4. Smoke checklist after a deploy

1. `GET https://<api>/api/swagger` loads (FastAPI up).
2. Sign in on the web app (Firebase auth round-trip).
3. Upload a small PDF → SourcesPanel shows parsing → ready.
4. Ask a question → blocks stream; trace strip renders.
5. Create a notebook, redeploy the API, confirm the notebook survives
   (Firestore persistence, not container disk).
