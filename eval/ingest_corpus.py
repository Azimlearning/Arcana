"""Ingest eval/corpus/ WITH entity extraction, into the stores the benchmark reads.

Differs from `eval/ingest_demo.py` in two ways that matter for the
hybrid-vs-flat benchmark:

  1. It passes an `LLMService` into `ingest_pdf`, so `extract_entities()`
     actually runs. `ingest_demo` leaves `llm=None`, which silently skips
     extraction and leaves the graph empty — which is why a hybrid run
     driven off that script is indistinguishable from the flat baseline.

  2. It persists the graph to `{storage}/graphs/anon.json`, which is the
     path `eval/run_benchmark.py` reads. `ingest_demo` writes
     `{storage}/graph.json`, which the benchmark never opens.

Usage
-----
    # smoke: one document, confirms the whole chain before committing spend
    uv run python -m eval.ingest_corpus --limit 1

    # full corpus, resetting prior state first
    uv run python -m eval.ingest_corpus --reset

    # resume without re-ingesting documents already in the doc store
    uv run python -m eval.ingest_corpus --skip-existing
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import re
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from api.core.logging import configure_logging, get_logger
from api.core.settings import REPO_ROOT, get_settings
from api.embeddings.service import EmbeddingService
from api.ingestion.pipeline import ingest_pdf
from api.ingestion.stores_bundle import Stores
from api.llm.service import LLMService
from api.stores.filesystem_doc_store import FilesystemDocStore
from api.stores.jsonl_chunk_store import JsonlChunkStore
from api.stores.networkx_store import NetworkXGraphStore
from api.stores.pinecone_store import PineconeVectorStore

CORPUS_DIR = REPO_ROOT / "eval" / "corpus"
_ID_SANITIZE = re.compile(r"[^A-Za-z0-9_\-]")


def _doc_id_for(path: Path) -> str:
    stem = _ID_SANITIZE.sub("_", path.stem).strip("_") or "doc"
    return stem[:128]


async def _reset(storage: Path, vector: PineconeVectorStore) -> dict:
    """Remove prior corpus state so the benchmark corpus is exactly eval/corpus/.

    Deletes only the vectors whose chunk ids are in the current chunk
    store, so nothing outside this project's own prior ingest is touched.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report: dict = {"backup": None, "vectors_deleted": 0}

    chunks_path = storage / "chunks.jsonl"
    old_ids: list[str] = []
    if chunks_path.exists():
        store = JsonlChunkStore(root=storage)
        try:
            old_ids = [c.id for c in await store.list_all()]
        finally:
            await store.aclose()

    if old_ids:
        for i in range(0, len(old_ids), 500):
            await vector.delete(old_ids[i : i + 500])
        report["vectors_deleted"] = len(old_ids)

    backup = storage.parent / f"local_storage_backup_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    for name in ("chunks.jsonl", "docs", "graphs", "graph.json"):
        src = storage / name
        if src.exists():
            dst = backup / name
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
                shutil.rmtree(src)
            else:
                shutil.copy2(src, dst)
                src.unlink()
    report["backup"] = str(backup)
    return report


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="ingest at most N PDFs")
    ap.add_argument("--reset", action="store_true", help="clear prior corpus state first")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    configure_logging()
    logger = get_logger("eval.ingest_corpus")
    settings = get_settings()
    storage = settings.local_storage_path

    pdfs = sorted(CORPUS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {CORPUS_DIR}", file=sys.stderr)
        return 1
    if args.limit:
        pdfs = pdfs[: args.limit]

    graph_path = storage / "graphs" / "anon.json"
    graph_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"corpus   : {len(pdfs)} PDF(s) from {CORPUS_DIR}")
    print(f"storage  : {storage}")
    print(f"graph    : {graph_path}   <- the path run_benchmark reads")
    print(f"pinecone : {settings.pinecone_index}")
    print(f"embed    : {settings.embedding_model}\n")

    vector = PineconeVectorStore(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index,
    )

    if args.reset:
        rep = await _reset(storage, vector)
        print(f"reset: {rep['vectors_deleted']} vectors deleted, backup -> {rep['backup']}\n")
        graph_path.parent.mkdir(parents=True, exist_ok=True)

    stores = Stores(
        doc=FilesystemDocStore(root=storage),
        vector=vector,
        graph=NetworkXGraphStore(persist_path=graph_path),
        chunks=JsonlChunkStore(root=storage),
    )
    embedder = EmbeddingService(settings=settings)
    llm = LLMService(settings=settings)

    summary: list[dict] = []
    failures = 0
    t_all = time.perf_counter()

    already: set[str] = set()
    if args.skip_existing:
        try:
            already = {m.id for m in await stores.doc.list_documents()}
        except Exception as exc:  # noqa: BLE001
            print(f"could not list existing documents ({exc}); ingesting all")
        print(f"skip-existing: {len(already)} document(s) already ingested\n")

    try:
        for i, pdf_path in enumerate(pdfs, 1):
            doc_id = _doc_id_for(pdf_path)
            if doc_id in already:
                print(f"[{i:2}/{len(pdfs)}] skip (already ingested) {doc_id[:48]}")
                continue
            print(f"[{i:2}/{len(pdfs)}] {pdf_path.name[:56]}")
            t0 = time.perf_counter()
            try:
                meta = await ingest_pdf(
                    doc_id=doc_id,
                    raw=pdf_path.read_bytes(),
                    title=pdf_path.name,
                    source_uri=str(pdf_path),
                    stores=stores,
                    embedder=embedder,
                    llm=llm,
                )
                dt = time.perf_counter() - t0
                g = getattr(stores.graph, "_g", None)
                nn, ne = (g.number_of_nodes(), g.number_of_edges()) if g is not None else (-1, -1)
                print(
                    f"          OK  {dt:6.1f}s  status={meta.ingest_status}"
                    f"  graph so far: {nn} nodes / {ne} edges"
                )
                summary.append(
                    {
                        "doc_id": doc_id,
                        "file": pdf_path.name,
                        "seconds": round(dt, 1),
                        "status": str(meta.ingest_status),
                        "graph_nodes_cumulative": nn,
                        "graph_edges_cumulative": ne,
                    }
                )
                # Persist after every document so a crash costs one doc, not all.
                with contextlib.suppress(Exception):
                    stores.graph.save()
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"          FAIL: {type(e).__name__}: {e}")
                logger.exception("ingest_corpus.failed", file=pdf_path.name)
    finally:
        async with contextlib.AsyncExitStack() as stack:
            stack.push_async_callback(embedder.aclose)
            stack.push_async_callback(stores.vector.aclose)
            stack.push_async_callback(stores.doc.aclose)
            stack.push_async_callback(stores.chunks.aclose)
            with contextlib.suppress(Exception):
                await llm.aclose()
            with contextlib.suppress(Exception):
                stores.graph.save()

    out = REPO_ROOT / "eval" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ingest_summary.json").write_text(
        json.dumps(
            {
                "generated": datetime.now(UTC).isoformat(),
                "corpus_dir": str(CORPUS_DIR),
                "documents": summary,
                "failures": failures,
                "total_seconds": round(time.perf_counter() - t_all, 1),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nDone. {len(summary)}/{len(pdfs)} ingested, {failures} failed.")
    print(f"Summary -> {out / 'ingest_summary.json'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
