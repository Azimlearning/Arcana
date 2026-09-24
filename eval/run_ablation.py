"""Retrieval ablation: separates the dense, sparse, and graph signals.

Answers the reviewer request for "ablation studies separating dense, sparse,
and graph signals" that `run_benchmark.py` cannot, because that script only
contrasts two arms (all-three vs graph-disabled).

Arms
----
    dense    vector only
    sparse   BM25 only
    graph    graph traversal only
    flat     vector + BM25            (the paper's baseline)
    hybrid   vector + BM25 + graph    (the system under test)

Every arm calls the same `hybrid_retrieve` with the same RRF constant and
the same top-k; a signal is disabled by substituting `NullRetriever`, so
nothing but the set of active signals varies. Corpus, chunking, and the
embedding model are fixed by construction, since all arms read the same
stores.

This is retrieval-only: no answer synthesis, so the reported numbers are
properties of retrieval alone and are not confounded with generation.

Metrics per question per arm
----------------------------
    distinct_docs   documents spanned by the retrieved set
    n_chunks        chunks returned
    latency_ms      wall-clock retrieval latency
    novel_vs_flat   chunks the arm returned that `flat` did not (hybrid only)

Aggregates add a Wilcoxon signed-rank test on the paired per-question
distinct-document counts, hybrid against flat, overall and per category.

Usage
-----
    uv run python -m eval.run_ablation
    uv run python -m eval.run_ablation --top-k 10 --output eval/results/ablation.json
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = REPO_ROOT / "eval" / "questions.yaml"
RESULTS_DIR = REPO_ROOT / "eval" / "results"

ARMS: dict[str, tuple[bool, bool, bool]] = {
    # name:   (vector, bm25, graph)
    "dense": (True, False, False),
    "sparse": (False, True, False),
    "graph": (False, False, True),
    "flat": (True, True, False),
    "hybrid": (True, True, True),
}


def _doc_of(chunk: object) -> str:
    for attr in ("doc_id", "document_id", "source_doc_id"):
        v = getattr(chunk, attr, None)
        if v:
            return str(v)
    cid = str(getattr(chunk, "id", ""))
    return cid.rsplit("_c_", 1)[0] if "_c_" in cid else cid


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--output", type=str, default="")
    args = ap.parse_args()

    from api.core.settings import get_settings
    from api.embeddings.service import EmbeddingService
    from api.llm.service import LLMService
    from api.retrieval.bm25 import BM25Retriever
    from api.retrieval.fusion import DEFAULT_RRF_K
    from api.retrieval.graph import GraphRetriever
    from api.retrieval.hybrid import hybrid_retrieve
    from api.retrieval.vector import VectorRetriever
    from api.stores.jsonl_chunk_store import JsonlChunkStore
    from api.stores.networkx_store import NetworkXGraphStore
    from api.stores.pinecone_store import PineconeVectorStore
    from eval.baseline_flat_rag import NullRetriever

    questions = yaml.safe_load(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
    settings = get_settings()

    llm = LLMService(settings=settings)
    embedder = EmbeddingService(settings=settings)
    vector_store = PineconeVectorStore(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index,
    )
    graph_path = settings.local_storage_path / "graphs" / "anon.json"
    graph_store = NetworkXGraphStore(persist_path=graph_path)
    chunk_store = JsonlChunkStore(root=settings.local_storage_path)

    real_vector = VectorRetriever(vector_store=vector_store, embedder=embedder)
    real_bm25 = BM25Retriever(chunk_store=chunk_store)
    real_graph = GraphRetriever(graph_store=graph_store, chunk_store=chunk_store, llm=llm)
    null = NullRetriever()

    g = getattr(graph_store, "_g", None)
    corpus_docs = {c.doc_id for c in await chunk_store.list_all()} if hasattr(chunk_store, "list_all") else set()
    print(f"questions : {len(questions)}   top-k: {args.top_k}   rrf_k: {DEFAULT_RRF_K}")
    print(f"graph     : {g.number_of_nodes() if g else 0} nodes / {g.number_of_edges() if g else 0} edges")
    print(f"corpus    : {len(corpus_docs)} documents")
    print(f"embed     : {settings.embedding_model}\n")

    rows: list[dict] = []
    try:
        for i, q in enumerate(questions, 1):
            qid = q.get("id", f"q-{i:02d}")
            cat = q.get("category", "?")
            question = " ".join(str(q["question"]).split())
            per_arm: dict[str, dict] = {}
            flat_chunk_ids: set[str] = set()

            for arm, (use_v, use_b, use_g) in ARMS.items():
                t0 = time.perf_counter()
                chunks = await hybrid_retrieve(
                    question,
                    top_k=args.top_k,
                    vector_retriever=real_vector if use_v else null,
                    bm25_retriever=real_bm25 if use_b else null,
                    graph_retriever=real_graph if use_g else null,
                    rrf_k=DEFAULT_RRF_K,
                    mode="hybrid",
                )
                dt = (time.perf_counter() - t0) * 1000
                ids = {str(getattr(c, "id", "")) for c in chunks}
                if arm == "flat":
                    flat_chunk_ids = ids
                per_arm[arm] = {
                    "distinct_docs": len({_doc_of(c) for c in chunks}),
                    "n_chunks": len(chunks),
                    "latency_ms": round(dt, 1),
                    "chunk_ids": sorted(ids),
                    "doc_ids": sorted({_doc_of(c) for c in chunks}),
                }

            per_arm["hybrid"]["novel_vs_flat"] = len(
                set(per_arm["hybrid"]["chunk_ids"]) - flat_chunk_ids
            )
            rows.append({"id": qid, "category": cat, "question": question, "arms": per_arm})
            print(
                f"[{i:2}/{len(questions)}] {qid:12} {cat:15} "
                + "  ".join(f"{a}={per_arm[a]['distinct_docs']}d" for a in ARMS)
                + f"  novel={per_arm['hybrid']['novel_vs_flat']}"
            )
    finally:
        async with contextlib.AsyncExitStack() as stack:
            stack.push_async_callback(embedder.aclose)
            stack.push_async_callback(vector_store.aclose)
            with contextlib.suppress(Exception):
                await llm.aclose()

    # ── Aggregate ────────────────────────────────────────────────────────
    def col(arm: str, field: str, cat: str | None = None) -> list[float]:
        return [
            r["arms"][arm][field]
            for r in rows
            if cat is None or r["category"] == cat
        ]

    cats = sorted({r["category"] for r in rows})
    summary: dict = {"overall": {}, "by_category": {}}
    for arm in ARMS:
        summary["overall"][arm] = {
            "mean_distinct_docs": round(statistics.fmean(col(arm, "distinct_docs")), 3),
            "mean_chunks": round(statistics.fmean(col(arm, "n_chunks")), 3),
            "median_latency_ms": round(statistics.median(col(arm, "latency_ms")), 1),
        }
    for cat in cats:
        summary["by_category"][cat] = {
            "n": len(col("hybrid", "distinct_docs", cat)),
            **{
                arm: round(statistics.fmean(col(arm, "distinct_docs", cat)), 3)
                for arm in ARMS
            },
        }

    try:
        from scipy.stats import wilcoxon

        def test(cat: str | None) -> dict:
            h, f = col("hybrid", "distinct_docs", cat), col("flat", "distinct_docs", cat)
            diffs = [a - b for a, b in zip(h, f, strict=True)]
            wins = sum(d > 0 for d in diffs)
            losses = sum(d < 0 for d in diffs)
            out = {
                "n": len(diffs),
                "mean_delta": round(statistics.fmean(diffs), 3),
                "wins": wins,
                "losses": losses,
                "ties": len(diffs) - wins - losses,
            }
            if any(diffs):
                stat, p = wilcoxon(h, f, zero_method="wilcox")
                out |= {"wilcoxon_statistic": float(stat), "p_value": float(p)}
            else:
                out |= {"wilcoxon_statistic": None, "p_value": None}
            return out

        summary["hybrid_vs_flat"] = {"overall": test(None)} | {
            c: test(c) for c in cats
        }
    except Exception as exc:  # noqa: BLE001
        summary["hybrid_vs_flat"] = {"error": str(exc)}

    print("\nmean distinct documents retrieved, by arm")
    for arm in ARMS:
        s = summary["overall"][arm]
        print(f"  {arm:8} {s['mean_distinct_docs']:5.2f} docs   {s['median_latency_ms']:8.1f} ms median")
    print("\nhybrid vs flat")
    for k, v in summary["hybrid_vs_flat"].items():
        if isinstance(v, dict) and "mean_delta" in v:
            p = v.get("p_value")
            print(
                f"  {k:16} n={v['n']:2}  delta={v['mean_delta']:+.2f}  "
                f"W/L/T={v['wins']}/{v['losses']}/{v['ties']}  "
                + (f"p={p:.4f}" if isinstance(p, float) else "p=n/a")
            )

    out_path = Path(args.output) if args.output else RESULTS_DIR / "ablation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "generated": datetime.now(UTC).isoformat(),
                "config": {
                    "top_k": args.top_k,
                    "rrf_k": DEFAULT_RRF_K,
                    "embedding_model": settings.embedding_model,
                    "graph_nodes": g.number_of_nodes() if g else 0,
                    "graph_edges": g.number_of_edges() if g else 0,
                    "corpus_documents": len(corpus_docs),
                },
                "questions": rows,
                "summary": summary,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWritten to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
