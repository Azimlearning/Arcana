# `eval/corpus/` — demo / benchmark corpus

Drop your PDF(s) here, then ingest them:

```bash
make ingest-demo
```

The script (`eval/ingest_demo.py`) walks every `*.pdf` in this directory,
parses each one, chunks it, embeds the chunks via OpenAI, upserts the
vectors into Pinecone, persists chunk text under
`infra/local_storage/chunks.jsonl`, and writes per-document metadata to
`infra/local_storage/docs/`.

## What the slice ships

- One PDF, ingested end-to-end.
- Vector search via Pinecone (hybrid retrieval also reads BM25 from the
  chunk store; graph retrieval is a no-op until entity extraction lands).

## What lands later (R-02 / Q-03)

The user-study corpus is a **fixed multi-document set** with
pre-registered questions in `eval/questions.yaml`. Selection criteria
and exact corpus contents are decided before the FYP 2 benchmark runs
(`docs/checklist.md` §1.12).

This directory is intentionally `.gitkeep`'d empty — copyright matters
when checking in academic PDFs.
