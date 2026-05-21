"""BM25 keyword retrieval — FR-RET-02.

Uses `rank_bm25.BM25Okapi`. Slice-time: rebuilds the index on every
query from the `ChunkStore`. The corpus is small (one PDF for the
walking skeleton), so the cost is sub-100ms. P1 will cache the index
and invalidate on `ChunkStore.upsert_many`.

Tokenization is intentionally minimal and ASCII-locked: the FYP
benchmark (R-02) requires reproducible results across machines, and
Python's default Unicode-aware `\\w+` would vary subtly between
runtime Unicode db versions. ASCII restriction is acceptable for the
English-language academic corpus; if multi-language ingestion lands
in P1, bump a `BENCHMARK_VERSION` constant in the eval harness so old
results aren't compared against new tokenization.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from api.retrieval.types import RetrievedChunk
from api.stores.chunk_store import ChunkStore

# ASCII-only word tokens. Determinism > Unicode richness for the slice.
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.ASCII)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Retriever:
    def __init__(self, *, chunk_store: ChunkStore) -> None:
        self._chunks = chunk_store

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        chunks = await self._chunks.list_all()
        if not chunks:
            return []

        corpus = [_tokenize(c.text) for c in chunks]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)

        ranked = sorted(
            zip(chunks, scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        out: list[RetrievedChunk] = []
        for c, raw_score in ranked[:top_k]:
            score = float(raw_score)
            if score <= 0.0:
                # Below-threshold hits add nothing useful to RRF and bloat traces.
                continue
            out.append(
                RetrievedChunk(
                    id=c.id,
                    doc_id=c.doc_id,
                    text=c.text,
                    page=c.page,
                    score=score,
                    source="bm25",
                )
            )
        return out
