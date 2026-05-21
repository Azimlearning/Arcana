"""Reciprocal Rank Fusion — FR-RET-04, PRD §10.4 Listing 10.4.

RRF score per item = Σ over rankings of 1/(k + rank_i).
`k` is a damping constant (60 is the standard from Cormack et al. 2009).
Items appearing only in one ranking still get a score; items appearing
in multiple rankings have additive boosting.

For the FYP benchmark (R-02), this single function is the *only*
difference between "graph + vector + bm25" and "vector + bm25 only".
The `RRF_K` setting flows in from `Settings`.
"""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[RetrievedChunk]],
    *,
    k: int = DEFAULT_RRF_K,
) -> list[RetrievedChunk]:
    """Fuse N ranked lists into one. Returns chunks sorted by fused score
    descending; duplicates across input rankings are deduped by chunk id.

    The output chunks carry `source="hybrid"` and `score=<fused RRF score>`
    — the per-retriever scores are intentionally discarded after fusion
    (RRF is rank-based, not score-based, by design).
    """
    if k < 1:
        raise ValueError(f"RRF k must be >= 1 (got {k})")

    fused_scores: dict[str, float] = {}
    first_seen: dict[str, RetrievedChunk] = {}

    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            fused_scores[chunk.id] = fused_scores.get(chunk.id, 0.0) + 1.0 / (k + rank)
            if chunk.id not in first_seen:
                first_seen[chunk.id] = chunk

    ranked_ids = sorted(fused_scores.items(), key=lambda kv: kv[1], reverse=True)

    out: list[RetrievedChunk] = []
    for chunk_id, score in ranked_ids:
        base = first_seen[chunk_id]
        out.append(
            RetrievedChunk(
                id=base.id,
                doc_id=base.doc_id,
                text=base.text,
                page=base.page,
                score=score,
                source="hybrid",
            )
        )
    return out
