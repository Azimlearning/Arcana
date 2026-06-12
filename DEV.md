# Arcana — Local Dev Guide (Windows)

Two terminals. Both must stay running while you test.

---

## Terminal A — API (FastAPI on :8000)

```powershell
cd "C:\Users\User\Documents\FYP DOCS\Arcana"
.venv\Scripts\uvicorn.exe api.main:app --reload --port 8000
```

**Ready when you see:**
```
INFO:     Application startup complete.
```

**Restart needed after:** editing `api/.env` (env vars are read once at startup).

---

## Terminal B — Web (Next.js on :3000)

```powershell
cd "C:\Users\User\Documents\FYP DOCS\Arcana"
corepack pnpm --filter @arcana/web dev
```

**Ready when you see:**
```
▲ Next.js ... ready on http://localhost:3000
```

Then open: **http://localhost:3000**

---

## api/.env — key settings

| Variable | Value | What it does |
|---|---|---|
| `OPENROUTER_API_KEY` | `sk-or-v1-...` | All LLM calls |
| `LLM_HEAVY` | `anthropic/claude-opus-4.8` | Research, Writing, Literature |
| `LLM_FALLBACK` | `anthropic/claude-sonnet-4.6` | Standard + fallback |
| `LLM_LIGHT` | `anthropic/claude-haiku-4.5` | Fact-check, Flashcards, Extraction |
| `OPENAI_API_KEY` | `sk-proj-...` | Embeddings only (text-embedding-3-large) |
| `PINECONE_API_KEY` | `pcsk_...` | Vector store |
| `PINECONE_INDEX` | `arcana` | Must match the index you created |
| `ANTHROPIC_API_KEY` | *(leave empty)* | Not needed — remove or blank |

---

## What you can test right now

| Mode | How to trigger | Expected output |
|---|---|---|
| **Research** | Type any question, RESEARCH tab active | `CitedSummary` with `[c8]` citations |
| **Study** | Switch to STUDY tab, ask "make flashcards on X" | `FlashcardDeck` component |
| **Writing** | Switch to WRITING tab, ask "write intro on X" | `DraftEditor` block |
| **Socratic** | Switch to SOCRATIC tab, ask about a concept | `SocraticDialog` — AI asks you questions |
| **Explore** | Switch to EXPLORE tab, ask "what's missing?" | `GapAnalysis` block |

Upload PDFs via the **Sources panel** (left column, drag & drop or click).

---

## Uploading documents

The Sources panel (left column) accepts PDFs via drag-and-drop or the file picker.

**What happens on upload:**
1. PDF is parsed (PyMuPDF) → chunked → embedded (OpenAI `text-embedding-3-large`) → upserted to Pinecone
2. Entities and relationships are extracted by the LLM → written to the NetworkX graph
3. Chunks are also written to the local JSONL chunk store (for BM25)

**After upload, allow ~10–30 seconds** before querying — Pinecone upserts are eventually consistent. If you get empty results immediately, wait and retry.

**Only PDFs are supported right now.** Web URLs, DOCX, and YouTube transcripts are P1 backlog (FR-ING-02/03/04).

**If ingest silently fails:** check the API terminal for `ERROR` lines. Common causes:
- `OPENAI_API_KEY` missing or wrong — embeddings use OpenAI, not OpenRouter
- `PINECONE_API_KEY` or `PINECONE_INDEX` wrong — use the index name (`arcana`), not the host URL
- PDF has no extractable text (scanned image) — OCR support is not yet implemented

---

## API and LLM setup — what we learned

The project runs on **OpenRouter for all LLM calls** and **OpenAI for embeddings only**. No direct Anthropic API key is needed.

**How LLM calls work:**
- All agents call `OpenRouterProvider` (real httpx implementation in `api/llm/providers/openrouter.py`)
- The provider sends OpenAI-format messages to `https://openrouter.ai/api/v1/chat/completions`
- Headers: `Authorization: Bearer <OPENROUTER_API_KEY>`, `X-OpenRouter-Title: Arcana`
- Three tiers: Heavy = Opus 4.8 (research/writing), Standard = Sonnet 4.6, Light = Haiku 4.5 (flashcards/fact-check)
- If Opus 4.8 fails, it falls back to Sonnet 4.6 automatically

**`ANTHROPIC_API_KEY` — leave it blank.** The settings field exists but is optional. If it's present and wrong it will cause 401 errors from a second provider trying to run in parallel. Remove it or leave empty.

**`Every LLM provider failed` error:** means `OPENROUTER_API_KEY` is missing, wrong, or out of credits. Check your OpenRouter dashboard. The key starts with `sk-or-v1-`.

**Embeddings are separate from LLM calls.** `OPENAI_API_KEY` is used *only* by the embedding service (`api/embeddings/service.py`) — it never touches OpenRouter. If you see embedding errors but LLM calls work, the two keys are independent.

---

## Prompt testing — known behaviours

Things discovered from manually testing each mode:

| Mode | Known behaviour | Notes |
|---|---|---|
| **Research** | Returns `CitedSummary` with `[c1]`-style inline citations | Citations are traceable to source chunks |
| **Study** | Returns `FlashcardDeck` — front/back cards from your docs | Ask "make flashcards on X" or just ask about a topic |
| **Writing** | Returns `DraftEditor` — editable draft block | Keep prompts specific: "write an intro on X" works better than "help me write" |
| **Socratic** | Returns `SocraticDialog` — AI asks *you* questions, never gives direct answers | First turn shows a question immediately (fixed: was showing empty state) |
| **Explore** | Returns `GapAnalysis` — gaps in your uploaded docs | Requires at least one document ingested; without docs shows "No documents retrieved" error block |

**Empty results / wrong mode output:** if the wrong block type comes back, check the mode indicator tab is actually highlighted before sending. The mode is sent on the wire with each turn — switching mid-conversation takes effect immediately.

**Explore with no documents:** this is correct behaviour, not a bug. Upload at least one PDF first.

**Socratic follow-up turns:** after the first question, type your answer in the chat input. The tutor reads your response and asks the next probing question. The conversation history accumulates in the `SocraticDialog` block.

---

## Common issues

| Symptom | Fix |
|---|---|
| `Every LLM provider failed` | Check `LLM_FALLBACK` in `api/.env` is `anthropic/claude-sonnet-4.6`. Restart API. |
| `Pinecone 404` | Check `PINECONE_INDEX=arcana` (not the host URL prefix). Restart API. |
| API not reloading after `.env` change | Stop with `Ctrl+C`, run the uvicorn command again. |
| CORS error in browser console | Confirm API is on `:8000` and web on `:3000`. |
| `uv.exe not valid for platform` | Use `.venv\Scripts\uvicorn.exe` directly (already in command above). |
