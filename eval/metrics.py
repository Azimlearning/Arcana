"""Benchmark metrics — R-02, §23.1.

Three metric families:

  citation_recall(chunks, gold_doc_ids)
      Fraction of gold source documents that appear anywhere in the
      retrieved chunk set. Returns NaN when no gold_doc_ids are specified
      (pre-corpus-selection phase); callers should skip NaN values in
      aggregation.

  unique_doc_count(chunks)
      Number of distinct source documents in the retrieved chunks.
      A proxy for cross-document diversity: hybrid retrieval should
      surface more unique documents on cross-document questions.

  llm_judge(query, answer, llm) — async, optional
      Rates the synthesised answer 0-10 via a second LLM call.
      Optional because it costs API credits; enable with --llm-judge.
      Returns NaN on failure so callers can skip gracefully.

  aggregate(results)
      Computes mean / win-count summaries across all QuestionResults.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field
from typing import Any

from api.retrieval.types import RetrievedChunk

# ── Result containers ─────────────────────────────────────────────────────


@dataclass
class RunMetrics:
    """Metrics for one pipeline run (hybrid or flat) on a single question."""

    pipeline: str  # "hybrid" | "flat"
    latency_ms: float
    chunks: list[RetrievedChunk] = field(default_factory=list)
    answer: str = ""
    llm_score: float | None = None  # 0-10; None = judge not run


@dataclass
class QuestionResult:
    """Complete result for one question across both pipelines."""

    question_id: str
    question: str
    category: str  # cross_document | single_document | contradiction
    gold_doc_ids: list[str]
    hybrid: RunMetrics
    flat: RunMetrics


# ── Per-result metrics ────────────────────────────────────────────────────


def citation_recall(chunks: list[RetrievedChunk], gold_doc_ids: list[str]) -> float:
    """Fraction of gold docs that appear in the retrieved chunks.

    Returns NaN when gold_doc_ids is empty (corpus not yet fixed).
    """
    if not gold_doc_ids:
        return float("nan")
    retrieved = {c.doc_id for c in chunks}
    hits = sum(1 for g in gold_doc_ids if g in retrieved)
    return hits / len(gold_doc_ids)


def unique_doc_count(chunks: list[RetrievedChunk]) -> int:
    """Number of distinct source documents in retrieved chunks."""
    return len({c.doc_id for c in chunks})


_SCORE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")


async def llm_judge(query: str, answer: str, llm: Any) -> float:
    """Rate answer quality 0-10 using an LLM as impartial judge.

    Returns NaN on any failure (missing API key, timeout, parse error)
    so callers can detect and skip failed scores without crashing the run.
    """
    from api.llm.types import Message  # local import to avoid circular at module load

    if not answer or not answer.strip():
        return 0.0

    prompt = (
        f"QUESTION:\n{query}\n\n"
        f"ANSWER:\n{answer}\n\n"
        "Rate how well this answer addresses the question, on a scale from 0 to 10.\n"
        "10 = complete, accurate, well-cited; 0 = irrelevant or empty.\n"
        "Reply with ONLY a single number (e.g. '7' or '8.5'). No explanation."
    )
    try:
        comp = await llm.complete(
            messages=[Message(role="user", content=prompt)],
            system="You are an impartial evaluator. Reply with only a numeric score 0-10.",
            max_tokens=8,
        )
        m = _SCORE_RE.search(comp.text.strip())
        if m:
            return min(10.0, max(0.0, float(m.group(1))))
    except Exception:
        pass
    return float("nan")


# ── Aggregation ───────────────────────────────────────────────────────────


def _safe_mean(vals: list[float]) -> float:
    finite = [v for v in vals if not math.isnan(v)]
    return statistics.mean(finite) if finite else float("nan")


def _wins(a_vals: list[float], b_vals: list[float]) -> tuple[int, int, int]:
    """Count (a_wins, b_wins, ties) across paired finite values."""
    a_w = b_w = ties = 0
    for a, b in zip(a_vals, b_vals, strict=False):
        if math.isnan(a) or math.isnan(b):
            continue
        if a > b:
            a_w += 1
        elif b > a:
            b_w += 1
        else:
            ties += 1
    return a_w, b_w, ties


def aggregate(results: list[QuestionResult]) -> dict[str, Any]:
    """Compute aggregate statistics across all QuestionResults.

    Returns a dict safe to serialize as JSON.
    """
    hybrid_lat = [r.hybrid.latency_ms for r in results]
    flat_lat = [r.flat.latency_ms for r in results]

    hybrid_recall = [
        citation_recall(r.hybrid.chunks, r.gold_doc_ids) for r in results
    ]
    flat_recall = [
        citation_recall(r.flat.chunks, r.gold_doc_ids) for r in results
    ]

    hybrid_docs = [float(unique_doc_count(r.hybrid.chunks)) for r in results]
    flat_docs = [float(unique_doc_count(r.flat.chunks)) for r in results]

    hybrid_scores = [
        r.hybrid.llm_score if r.hybrid.llm_score is not None else float("nan")
        for r in results
    ]
    flat_scores = [
        r.flat.llm_score if r.flat.llm_score is not None else float("nan")
        for r in results
    ]

    docs_hw, docs_fw, docs_t = _wins(hybrid_docs, flat_docs)
    score_hw, score_fw, score_t = _wins(hybrid_scores, flat_scores)

    by_category: dict[str, dict[str, Any]] = {}
    categories = sorted({r.category for r in results})
    for cat in categories:
        cat_r = [r for r in results if r.category == cat]
        by_category[cat] = {
            "n": len(cat_r),
            "hybrid_mean_unique_docs": _safe_mean([float(unique_doc_count(r.hybrid.chunks)) for r in cat_r]),
            "flat_mean_unique_docs": _safe_mean([float(unique_doc_count(r.flat.chunks)) for r in cat_r]),
            "hybrid_mean_llm_score": _safe_mean(
                [r.hybrid.llm_score if r.hybrid.llm_score is not None else float("nan") for r in cat_r]
            ),
            "flat_mean_llm_score": _safe_mean(
                [r.flat.llm_score if r.flat.llm_score is not None else float("nan") for r in cat_r]
            ),
        }

    return {
        "n_questions": len(results),
        "hybrid": {
            "mean_latency_ms": _safe_mean(hybrid_lat),
            "mean_citation_recall": _safe_mean(hybrid_recall),
            "mean_unique_docs": _safe_mean(hybrid_docs),
            "mean_llm_score": _safe_mean(hybrid_scores),
        },
        "flat": {
            "mean_latency_ms": _safe_mean(flat_lat),
            "mean_citation_recall": _safe_mean(flat_recall),
            "mean_unique_docs": _safe_mean(flat_docs),
            "mean_llm_score": _safe_mean(flat_scores),
        },
        "wins_unique_docs": {
            "hybrid": docs_hw,
            "flat": docs_fw,
            "tie": docs_t,
        },
        "wins_llm_score": {
            "hybrid": score_hw,
            "flat": score_fw,
            "tie": score_t,
        },
        "by_category": by_category,
    }
