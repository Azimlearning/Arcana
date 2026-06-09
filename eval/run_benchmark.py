"""Hybrid vs flat-RAG benchmark — P1 §1.12, R-02, §23.1.

Usage
-----
    # basic run (no LLM judge, no API calls for scoring)
    uv run python -m eval.run_benchmark

    # with LLM judge (costs API credits per question x 2)
    uv run python -m eval.run_benchmark --llm-judge

    # override defaults
    uv run python -m eval.run_benchmark --top-k 15 --output eval/results/run_01.json

    # dry-run: validate questions.yaml without calling any API
    uv run python -m eval.run_benchmark --dry-run

Design
------
Both pipelines share:
  - The same Settings (api/.env) → same embeddings model and Pinecone index.
  - The same VectorStore (Pinecone), ChunkStore (JSONL), GraphStore (NetworkX).
  - The same synthesis prompt (SYNTHESIS_SYSTEM from api/llm/prompts/synthesis.py).

Only the graph_retriever is toggled:
  - Hybrid: VectorRetriever + BM25Retriever + GraphRetriever → RRF
  - Flat:   VectorRetriever + BM25Retriever + NullRetriever  → RRF

Methodological guard (R-02): question set committed before first run;
embeddings / corpus / chunking constant; only retrieval varies.

Graceful degradation
--------------------
Missing API keys → the retriever degrades (returns []) via `_safe_call`
in `hybrid_retrieve`. The benchmark still runs and reports empty-corpus
scores; this is expected before `make ingest-demo` is executed.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import sys
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = REPO_ROOT / "eval" / "questions.yaml"
RESULTS_DIR = REPO_ROOT / "eval" / "results"

from eval.metrics import QuestionResult  # noqa: E402

# ── Synthesis helper (shared by both pipelines) ──────────────────────────


async def _synthesise(query: str, chunks: list, llm: object) -> str:
    """Call the LLM with the grounded synthesis prompt. Returns plain text."""
    from api.llm.prompts.synthesis import SYNTHESIS_SYSTEM, build_user_prompt
    from api.llm.types import Message

    if not chunks:
        return "No relevant information found in the corpus for this query."
    try:
        comp = await llm.complete(  # type: ignore[union-attr]
            messages=[Message(role="user", content=build_user_prompt(query, chunks))],
            system=SYNTHESIS_SYSTEM,
            max_tokens=512,
        )
        return comp.text
    except Exception as exc:
        return f"[synthesis failed: {exc}]"


# ── Per-question runner ───────────────────────────────────────────────────


async def _run_question(
    q: dict,
    *,
    top_k: int,
    vector_retriever: object,
    bm25_retriever: object,
    graph_retriever: object,
    llm: object,
    with_llm_judge: bool,
) -> QuestionResult:
    from api.retrieval.hybrid import hybrid_retrieve
    from eval.baseline_flat_rag import flat_retrieve
    from eval.metrics import RunMetrics, llm_judge

    query = q["question"]
    gold_ids = q.get("gold_doc_ids") or []
    category = q.get("category", "cross_document")

    # --- Hybrid pipeline ---
    t0 = time.perf_counter()
    hybrid_chunks = await hybrid_retrieve(
        query,
        top_k=top_k,
        vector_retriever=vector_retriever,  # type: ignore[arg-type]
        bm25_retriever=bm25_retriever,  # type: ignore[arg-type]
        graph_retriever=graph_retriever,  # type: ignore[arg-type]
    )
    hybrid_latency_ms = (time.perf_counter() - t0) * 1000
    hybrid_answer = await _synthesise(query, hybrid_chunks, llm)

    # --- Flat-RAG baseline ---
    t0 = time.perf_counter()
    flat_chunks = await flat_retrieve(
        query,
        top_k=top_k,
        vector_retriever=vector_retriever,  # type: ignore[arg-type]
        bm25_retriever=bm25_retriever,  # type: ignore[arg-type]
    )
    flat_latency_ms = (time.perf_counter() - t0) * 1000
    flat_answer = await _synthesise(query, flat_chunks, llm)

    # --- Optional LLM judge ---
    hybrid_score: float | None = None
    flat_score: float | None = None
    if with_llm_judge:
        hybrid_score = await llm_judge(query, hybrid_answer, llm)
        flat_score = await llm_judge(query, flat_answer, llm)

    return QuestionResult(
        question_id=q["id"],
        question=query,
        category=category,
        gold_doc_ids=gold_ids,
        hybrid=RunMetrics(
            pipeline="hybrid",
            latency_ms=hybrid_latency_ms,
            chunks=hybrid_chunks,
            answer=hybrid_answer,
            llm_score=hybrid_score,
        ),
        flat=RunMetrics(
            pipeline="flat",
            latency_ms=flat_latency_ms,
            chunks=flat_chunks,
            answer=flat_answer,
            llm_score=flat_score,
        ),
    )


# ── Report printers ───────────────────────────────────────────────────────


def _fmt_score(v: float | None) -> str:
    if v is None or math.isnan(v):
        return "  n/a"
    return f"{v:5.1f}"


def _fmt_ms(ms: float) -> str:
    return f"{ms:7.0f}"


def _print_table(results: list) -> None:
    from eval.metrics import citation_recall, unique_doc_count

    header = (
        f"{'ID':<18} {'Cat':<12}"
        f" {'H-docs':>6} {'F-docs':>6}"
        f" {'H-lat':>7} {'F-lat':>7}"
        f" {'H-rcl':>6} {'F-rcl':>6}"
        f" {'H-llm':>6} {'F-llm':>6}"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in results:
        h_rcl = citation_recall(r.hybrid.chunks, r.gold_doc_ids)
        f_rcl = citation_recall(r.flat.chunks, r.gold_doc_ids)
        print(
            f"{r.question_id:<18} {r.category:<12}"
            f" {unique_doc_count(r.hybrid.chunks):>6} {unique_doc_count(r.flat.chunks):>6}"
            f" {_fmt_ms(r.hybrid.latency_ms)} {_fmt_ms(r.flat.latency_ms)}"
            f" {'n/a':>6} {'n/a':>6}"
            if math.isnan(h_rcl) else
            f"{r.question_id:<18} {r.category:<12}"
            f" {unique_doc_count(r.hybrid.chunks):>6} {unique_doc_count(r.flat.chunks):>6}"
            f" {_fmt_ms(r.hybrid.latency_ms)} {_fmt_ms(r.flat.latency_ms)}"
            f" {h_rcl:>6.2f} {f_rcl:>6.2f}"
            f" {_fmt_score(r.hybrid.llm_score)} {_fmt_score(r.flat.llm_score)}"
        )
    print(sep)


def _print_summary(agg: dict) -> None:
    h = agg["hybrid"]
    f = agg["flat"]
    w = agg["wins_unique_docs"]
    ws = agg["wins_llm_score"]
    n = agg["n_questions"]

    print(f"\n{'=== AGGREGATE SUMMARY ':=<60}")
    print(f"  Questions run: {n}")
    print(f"\n  {'Metric':<28} {'Hybrid':>10} {'Flat':>10}")
    print(f"  {'-'*50}")

    def _row(label: str, hv: float, fv: float) -> str:
        hstr = f"{hv:.1f}" if not math.isnan(hv) else "n/a"
        fstr = f"{fv:.1f}" if not math.isnan(fv) else "n/a"
        return f"  {label:<28} {hstr:>10} {fstr:>10}"

    print(_row("Mean latency (ms)", h["mean_latency_ms"], f["mean_latency_ms"]))
    print(_row("Mean unique docs", h["mean_unique_docs"], f["mean_unique_docs"]))
    print(_row("Mean citation recall", h["mean_citation_recall"], f["mean_citation_recall"]))
    print(_row("Mean LLM score (0-10)", h["mean_llm_score"], f["mean_llm_score"]))

    print(f"\n  Unique-doc wins  → hybrid: {w['hybrid']}, flat: {w['flat']}, tie: {w['tie']}")
    print(f"  LLM-score wins   → hybrid: {ws['hybrid']}, flat: {ws['flat']}, tie: {ws['tie']}")

    if "by_category" in agg:
        print(f"\n  {'Category breakdown':}")
        for cat, stats in agg["by_category"].items():
            print(
                f"    {cat:<18} n={stats['n']}"
                f"  hybrid_docs={stats['hybrid_mean_unique_docs']:.1f}"
                f"  flat_docs={stats['flat_mean_unique_docs']:.1f}"
            )
    print("=" * 60)


# ── Results serialiser ────────────────────────────────────────────────────


def _serialise(results: list, agg: dict) -> dict:
    from eval.metrics import citation_recall, unique_doc_count

    rows = []
    for r in results:
        h_rcl = citation_recall(r.hybrid.chunks, r.gold_doc_ids)
        f_rcl = citation_recall(r.flat.chunks, r.gold_doc_ids)
        rows.append(
            {
                "id": r.question_id,
                "category": r.category,
                "question": r.question,
                "hybrid": {
                    "latency_ms": r.hybrid.latency_ms,
                    "unique_docs": unique_doc_count(r.hybrid.chunks),
                    "citation_recall": None if math.isnan(h_rcl) else h_rcl,
                    "llm_score": r.hybrid.llm_score,
                    "answer": r.hybrid.answer,
                },
                "flat": {
                    "latency_ms": r.flat.latency_ms,
                    "unique_docs": unique_doc_count(r.flat.chunks),
                    "citation_recall": None if math.isnan(f_rcl) else f_rcl,
                    "llm_score": r.flat.llm_score,
                    "answer": r.flat.answer,
                },
            }
        )
    return {"questions": rows, "aggregate": _nan_to_none(agg)}


def _nan_to_none(obj: object) -> object:
    """Recursively replace float NaN with None for JSON serialisation."""
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if isinstance(obj, dict):
        return {k: _nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nan_to_none(v) for v in obj]
    return obj


# ── Main ─────────────────────────────────────────────────────────────────


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arcana hybrid vs flat-RAG benchmark")
    parser.add_argument(
        "--questions",
        default=str(QUESTIONS_PATH),
        help="Path to pre-registered questions YAML (default: eval/questions.yaml)",
    )
    parser.add_argument("--top-k", type=int, default=10, help="Retrieval top-k (default: 10)")
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Enable LLM-based answer quality scoring (costs API credits)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="JSON output path (default: eval/results/run_<timestamp>.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate questions.yaml and print plan without calling any API",
    )
    args = parser.parse_args(argv)

    # 1. Load questions
    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"ERROR: questions file not found: {questions_path}", file=sys.stderr)
        return 1
    with questions_path.open() as fh:
        doc = yaml.safe_load(fh)
    questions = doc.get("questions", [])
    if not questions:
        print("ERROR: no questions found in YAML.", file=sys.stderr)
        return 1

    print(f"Arcana retrieval benchmark — {len(questions)} questions")
    print(f"  questions : {questions_path}")
    print(f"  top-k     : {args.top_k}")
    print(f"  llm-judge : {args.llm_judge}")
    if args.dry_run:
        print("\nDry-run mode — no API calls made.")
        for q in questions:
            print(f"  [{q.get('category', '?'):>15}] {q['id']}: {q['question'][:70]}")
        return 0

    # 2. Initialise stores and retrievers from Settings
    from api.core.settings import get_settings
    from api.embeddings.service import EmbeddingService
    from api.llm.service import LLMService
    from api.retrieval.bm25 import BM25Retriever
    from api.retrieval.graph import GraphRetriever
    from api.retrieval.vector import VectorRetriever
    from api.stores.jsonl_chunk_store import JsonlChunkStore
    from api.stores.networkx_store import NetworkXGraphStore
    from api.stores.pinecone_store import PineconeVectorStore

    try:
        settings = get_settings()
    except Exception as exc:
        print(f"ERROR: could not load Settings — {exc}", file=sys.stderr)
        print("  Ensure api/.env is populated (see docs/env_generation_guide.md).", file=sys.stderr)
        return 1

    print(f"  storage   : {settings.local_storage_path}")
    print(f"  pinecone  : {settings.pinecone_index}\n")

    llm = LLMService(settings=settings)
    embedder = EmbeddingService(settings=settings)

    vector_store = PineconeVectorStore(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index,
    )
    graph_store = NetworkXGraphStore(
        persist_path=settings.local_storage_path / "graph.json",
    )
    chunk_store = JsonlChunkStore(root=settings.local_storage_path)

    vector_retriever = VectorRetriever(vector_store=vector_store, embedder=embedder)
    bm25_retriever = BM25Retriever(chunk_store=chunk_store)
    graph_retriever = GraphRetriever(
        graph_store=graph_store,
        chunk_store=chunk_store,
        llm=llm,
    )

    # 3. Run benchmark
    results = []
    for i, q in enumerate(questions, start=1):
        qid = q.get("id", f"q-{i:02d}")
        short_q = q["question"][:60].replace("\n", " ").strip()
        print(f"[{i:2d}/{len(questions)}] {qid}: {short_q}…", end=" ", flush=True)
        result = await _run_question(
            q,
            top_k=args.top_k,
            vector_retriever=vector_retriever,
            bm25_retriever=bm25_retriever,
            graph_retriever=graph_retriever,
            llm=llm,
            with_llm_judge=args.llm_judge,
        )
        from eval.metrics import unique_doc_count
        h_docs = unique_doc_count(result.hybrid.chunks)
        f_docs = unique_doc_count(result.flat.chunks)
        print(f"hybrid={h_docs}docs/{result.hybrid.latency_ms:.0f}ms  flat={f_docs}docs/{result.flat.latency_ms:.0f}ms")
        results.append(result)

    # 4. Aggregate and report
    from eval.metrics import aggregate
    agg = aggregate(results)
    print()
    _print_table(results)
    _print_summary(agg)

    # 5. Write JSON output
    output_path: Path
    if args.output:
        output_path = Path(args.output)
    else:
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = RESULTS_DIR / f"run_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _serialise(results, agg)
    with output_path.open("w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nResults written to: {output_path}")

    # 6. Close clients
    async with contextlib.AsyncExitStack() as stack:
        stack.push_async_callback(embedder.aclose)
        stack.push_async_callback(vector_store.aclose)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
