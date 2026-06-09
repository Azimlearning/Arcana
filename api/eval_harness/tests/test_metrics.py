"""Unit tests for eval/metrics.py — citation_recall, unique_doc_count, aggregate."""

from __future__ import annotations

import math

from api.retrieval.types import RetrievedChunk
from eval.metrics import (
    QuestionResult,
    RunMetrics,
    aggregate,
    citation_recall,
    unique_doc_count,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def _chunk(doc_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        id=f"c-{doc_id}",
        doc_id=doc_id,
        text="stub",
        page=1,
        score=0.9,
        source="vector",
    )


def _run(pipeline: str, chunks: list[RetrievedChunk], score: float | None = None) -> RunMetrics:
    return RunMetrics(pipeline=pipeline, latency_ms=100.0, chunks=chunks, llm_score=score)


def _result(
    qid: str,
    gold: list[str],
    hybrid_chunks: list[RetrievedChunk],
    flat_chunks: list[RetrievedChunk],
    hybrid_score: float | None = None,
    flat_score: float | None = None,
    category: str = "cross_document",
) -> QuestionResult:
    return QuestionResult(
        question_id=qid,
        question=f"Question {qid}",
        category=category,
        gold_doc_ids=gold,
        hybrid=_run("hybrid", hybrid_chunks, hybrid_score),
        flat=_run("flat", flat_chunks, flat_score),
    )


# ── citation_recall ───────────────────────────────────────────────────────


def test_citation_recall_no_gold_returns_nan():
    assert math.isnan(citation_recall([_chunk("doc1")], []))


def test_citation_recall_all_found():
    chunks = [_chunk("doc1"), _chunk("doc2")]
    assert citation_recall(chunks, ["doc1", "doc2"]) == 1.0


def test_citation_recall_partial():
    chunks = [_chunk("doc1")]
    assert citation_recall(chunks, ["doc1", "doc2"]) == 0.5


def test_citation_recall_none_found():
    chunks = [_chunk("doc3")]
    assert citation_recall(chunks, ["doc1", "doc2"]) == 0.0


def test_citation_recall_empty_chunks_and_gold():
    # Both empty — gold is empty so NaN
    assert math.isnan(citation_recall([], []))


def test_citation_recall_empty_chunks_with_gold():
    assert citation_recall([], ["doc1"]) == 0.0


# ── unique_doc_count ──────────────────────────────────────────────────────


def test_unique_doc_count_empty():
    assert unique_doc_count([]) == 0


def test_unique_doc_count_all_same_doc():
    chunks = [_chunk("doc1"), _chunk("doc1"), _chunk("doc1")]
    assert unique_doc_count(chunks) == 1


def test_unique_doc_count_multiple_docs():
    chunks = [_chunk("doc1"), _chunk("doc2"), _chunk("doc1"), _chunk("doc3")]
    assert unique_doc_count(chunks) == 3


# ── aggregate ────────────────────────────────────────────────────────────


def test_aggregate_empty():
    agg = aggregate([])
    assert agg["n_questions"] == 0
    assert math.isnan(agg["hybrid"]["mean_latency_ms"])
    assert math.isnan(agg["hybrid"]["mean_unique_docs"])


def test_aggregate_hybrid_wins_unique_docs():
    r = _result(
        "q-01",
        gold=[],
        hybrid_chunks=[_chunk("a"), _chunk("b")],  # 2 unique docs
        flat_chunks=[_chunk("a")],                  # 1 unique doc
    )
    agg = aggregate([r])
    assert agg["wins_unique_docs"]["hybrid"] == 1
    assert agg["wins_unique_docs"]["flat"] == 0
    assert agg["wins_unique_docs"]["tie"] == 0


def test_aggregate_flat_wins_unique_docs():
    r = _result(
        "q-01",
        gold=[],
        hybrid_chunks=[_chunk("a")],
        flat_chunks=[_chunk("a"), _chunk("b")],
    )
    agg = aggregate([r])
    assert agg["wins_unique_docs"]["flat"] == 1


def test_aggregate_tie_unique_docs():
    r = _result(
        "q-01",
        gold=[],
        hybrid_chunks=[_chunk("a")],
        flat_chunks=[_chunk("b")],
    )
    agg = aggregate([r])
    assert agg["wins_unique_docs"]["tie"] == 1


def test_aggregate_llm_score_wins():
    r = _result(
        "q-01",
        gold=[],
        hybrid_chunks=[_chunk("a")],
        flat_chunks=[_chunk("a")],
        hybrid_score=8.0,
        flat_score=5.0,
    )
    agg = aggregate([r])
    assert agg["wins_llm_score"]["hybrid"] == 1
    assert agg["hybrid"]["mean_llm_score"] == 8.0
    assert agg["flat"]["mean_llm_score"] == 5.0


def test_aggregate_skips_nan_scores():
    r = _result(
        "q-01",
        gold=[],
        hybrid_chunks=[_chunk("a")],
        flat_chunks=[_chunk("a")],
        hybrid_score=float("nan"),
        flat_score=float("nan"),
    )
    agg = aggregate([r])
    # NaN scores → no wins counted, mean is NaN
    assert agg["wins_llm_score"]["hybrid"] == 0
    assert math.isnan(agg["hybrid"]["mean_llm_score"])


def test_aggregate_mean_latency():
    r1 = _result("q-01", gold=[], hybrid_chunks=[], flat_chunks=[])
    r1.hybrid.latency_ms = 200.0
    r1.flat.latency_ms = 150.0
    r2 = _result("q-02", gold=[], hybrid_chunks=[], flat_chunks=[])
    r2.hybrid.latency_ms = 100.0
    r2.flat.latency_ms = 50.0
    agg = aggregate([r1, r2])
    assert agg["hybrid"]["mean_latency_ms"] == 150.0
    assert agg["flat"]["mean_latency_ms"] == 100.0


def test_aggregate_by_category():
    r1 = _result("q-01", gold=[], hybrid_chunks=[_chunk("a"), _chunk("b")], flat_chunks=[_chunk("a")], category="cross_document")
    r2 = _result("q-02", gold=[], hybrid_chunks=[_chunk("a")], flat_chunks=[_chunk("a")], category="single_document")
    agg = aggregate([r1, r2])
    assert "cross_document" in agg["by_category"]
    assert "single_document" in agg["by_category"]
    assert agg["by_category"]["cross_document"]["n"] == 1


def test_aggregate_citation_recall_with_gold():
    r = _result(
        "q-01",
        gold=["doc1", "doc2"],
        hybrid_chunks=[_chunk("doc1"), _chunk("doc2")],
        flat_chunks=[_chunk("doc1")],
    )
    agg = aggregate([r])
    assert agg["hybrid"]["mean_citation_recall"] == 1.0
    assert agg["flat"]["mean_citation_recall"] == 0.5
