"""Reciprocal Rank Fusion — math, dedupe, edge cases."""

from __future__ import annotations

import pytest

from api.retrieval.fusion import reciprocal_rank_fusion
from api.retrieval.types import RetrievedChunk


def _c(cid: str, source: str = "vector") -> RetrievedChunk:
    return RetrievedChunk(
        id=cid,
        doc_id="d1",
        text=f"chunk {cid}",
        page=1,
        score=0.0,
        source=source,  # type: ignore[arg-type]
    )


def test_empty_input_returns_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []
    assert reciprocal_rank_fusion([[], [], []]) == []


def test_single_ranking_passes_through_in_order():
    r1 = [_c("a"), _c("b"), _c("c")]
    fused = reciprocal_rank_fusion([r1], k=60)
    assert [c.id for c in fused] == ["a", "b", "c"]
    # Scores match 1/(60+rank).
    assert fused[0].score == pytest.approx(1 / 61)
    assert fused[1].score == pytest.approx(1 / 62)


def test_disjoint_rankings_concat_in_score_order():
    r1 = [_c("a"), _c("b")]   # rank 1, 2 from r1
    r2 = [_c("c"), _c("d")]   # rank 1, 2 from r2
    fused = reciprocal_rank_fusion([r1, r2], k=60)
    # `a` and `c` both have score 1/61 (rank 1 each); `b` and `d` both 1/62.
    score_by_id = {c.id: c.score for c in fused}
    assert score_by_id["a"] == pytest.approx(1 / 61)
    assert score_by_id["c"] == pytest.approx(1 / 61)
    assert score_by_id["b"] == pytest.approx(1 / 62)
    assert score_by_id["d"] == pytest.approx(1 / 62)
    # `a` and `c` (tied) must precede `b` and `d` (tied lower).
    first_two = {fused[0].id, fused[1].id}
    last_two = {fused[2].id, fused[3].id}
    assert first_two == {"a", "c"}
    assert last_two == {"b", "d"}


def test_overlapping_rankings_boost_score():
    # `a` appears at rank 1 in both rankings -> score = 2 * (1/61)
    r1 = [_c("a"), _c("b")]
    r2 = [_c("a"), _c("c")]
    fused = reciprocal_rank_fusion([r1, r2], k=60)
    assert fused[0].id == "a"
    assert fused[0].score == pytest.approx(2 / 61)


def test_dedupe_by_chunk_id():
    r1 = [_c("a")]
    r2 = [_c("a")]
    fused = reciprocal_rank_fusion([r1, r2], k=60)
    assert len(fused) == 1
    assert fused[0].id == "a"


def test_output_source_is_hybrid():
    r1 = [_c("a", source="vector"), _c("b", source="bm25")]
    fused = reciprocal_rank_fusion([r1], k=60)
    assert all(c.source == "hybrid" for c in fused)


def test_invalid_k_raises():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[_c("a")]], k=0)


def test_full_worked_example():
    """Manual RRF computation: three rankings, k=10.
        r1: [a, b, c]  → a=1/11, b=1/12, c=1/13
        r2: [b, c, d]  → b=1/11, c=1/12, d=1/13
        r3: [c, e, a]  → c=1/11, e=1/12, a=1/13
        totals: a=1/11+1/13≈0.168, b=1/11+1/12≈0.174,
                c=1/11+1/12+1/13≈0.252, d=1/13≈0.077, e=1/12≈0.083
        order:  c > b > a > e > d
    """
    r1 = [_c("a"), _c("b"), _c("c")]
    r2 = [_c("b"), _c("c"), _c("d")]
    r3 = [_c("c"), _c("e"), _c("a")]
    fused = reciprocal_rank_fusion([r1, r2, r3], k=10)
    assert [c.id for c in fused] == ["c", "b", "a", "e", "d"]
