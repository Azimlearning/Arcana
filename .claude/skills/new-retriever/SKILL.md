---
name: new-retriever
description: Use when adding or modifying a retrieval path in Arcana — when the user asks to add a new retriever (e.g. "wire up colbert", "add a contradiction-aware retriever"), to tune the RRF fusion, or to extend hybrid retrieval. Walks the three-step pattern (independent ranker → RRF fusion → unified contract) and enforces the grounding-before-generation invariant.
---

# Skill: Add a new retriever (or modify hybrid retrieval)

**Authority:** PRD §10 (backend foundation), Listing 10.4 (RRF fusion), §11A.3 invariant #1 (ground before generating); FR-RET-01..08.

Arcana's retrieval is **hybrid by design**: each retriever returns a ranked list independently, then `reciprocal_rank_fusion(rankings, k=60)` fuses them. This is the central evidence for the FYP claim that hybrid beats flat-RAG. Don't subvert the pattern.

## The three-step pattern

Every retriever follows the same shape:

1. **Independent ranker.** Implements a single method returning `List[RetrievalResult]` ranked by its own signal. No fusion inside the retriever. No cross-retriever knowledge.
2. **RRF fusion.** All retriever outputs flow into `reciprocal_rank_fusion(rankings, k=60)` in `api/retrieval/fusion.py`. Adding a retriever = adding one entry to the `rankings` list, not changing the fusion math.
3. **Unified contract.** `hybrid_retrieve(query, k)` is the single entry point. Agents call it, never the individual retrievers.

## Step 1 — Place the file

| Signal | Path | Existing examples |
|---|---|---|
| Dense (vectors) | `api/retrieval/vector.py` | FR-RET-01 |
| Sparse (keyword) | `api/retrieval/bm25.py` | FR-RET-02 |
| Graph (multi-hop) | `api/retrieval/graph.py` | FR-RET-03 |
| Fusion | `api/retrieval/fusion.py` | FR-RET-04 |
| Orchestrator | `api/retrieval/hybrid.py` | FR-RET-04..08 |

If you're adding a new signal type (e.g. ColBERT late-interaction, re-ranker, semantic-cache), create a new file in `api/retrieval/`. Don't bolt it inside an existing retriever.

## Step 2 — Implement the ranker

```python
from api.stores.vector_store import VectorStore  # ABC, not a concrete backend
from api.retrieval.types import RetrievalResult  # in packages/schema if cross-cutting

class <New>Retriever:
    def __init__(self, store: <ABC>):
        self.store = store

    async def search(self, query: str, k: int = 50) -> list[RetrievalResult]:
        """Return ranked results for this signal alone. No fusion."""
        # 1. Translate query into the retriever's representation.
        # 2. Query through the storage ABC.
        # 3. Return List[RetrievalResult] ranked by this retriever's score.
        ...
```

**Rules:**

- Storage via ABCs only — never `Neo4jGraphStore`, `PineconeStore`, etc. The hook will block concrete imports.
- Async. Hybrid retrieval runs all retrievers under `asyncio.gather`.
- Every result must carry source attribution traceable to a document chunk (FR-RET-08). Anything that returns un-attributable text is unusable downstream.
- The 3072-dim embedding model (`text-embedding-3-large`) is **locked** for the benchmark (R-02). Don't change it inside a retriever. If a different model is genuinely needed, raise it as a new question in `decisions.md` — the benchmark fairness depends on the embedding being identical to the baseline.

## Step 3 — Wire into hybrid

Open `api/retrieval/hybrid.py`:

```python
async def hybrid_retrieve(query: str, k: int = 10) -> list[RetrievalResult]:
    rankings = await asyncio.gather(
        vector_retriever.search(query),
        bm25_retriever.search(query),
        graph_retriever.search(query),
        new_retriever.search(query),  # ← add here
    )
    fused = reciprocal_rank_fusion(rankings, k=60)
    return fused[:k]
```

Do **not** touch the RRF math. `k=60` is the standard constant (the same one cited in PRD §10 / Listing 10.4). Changing it invalidates the like-for-like benchmark.

## Step 4 — Degradation

A retriever that fails should **never** take the whole pipeline down. Wrap the new retriever in the same degradation pattern as the others (NFR-REL-01): on exception, log, return `[]`, and let RRF proceed with the remaining rankings. Verify by simulating a failure in tests.

## Step 5 — Benchmark integration

Open `eval/run_benchmark.py`. The benchmark runs flat-RAG vs hybrid with **identical** embeddings, corpus, and question set (PRD §23.1). If your new retriever is meant to be part of the hybrid claim, add it under hybrid. If it's experimental, gate it behind a config flag so the benchmark stays apples-to-apples.

## Step 6 — Tests

- Unit test the retriever in isolation against a small fixture corpus.
- Integration test that `hybrid_retrieve()` returns a sensible fused ranking with the new retriever included.
- Optional: a regression test comparing hybrid+new vs hybrid alone on the eval set, to confirm it helps (or at least doesn't hurt).

## Done checklist (paste into the commit)

- [ ] File in the right place; storage via ABCs only.
- [ ] Independent ranker, async, source attribution on every result.
- [ ] One line added to `hybrid_retrieve()`; RRF unchanged.
- [ ] Failure mode degrades gracefully (NFR-REL-01).
- [ ] Tests green; benchmark still reproducible.
- [ ] Commit references the FR-RET-* ID.
- [ ] `code-reviewer` and `qa-runner` subagents report green.
