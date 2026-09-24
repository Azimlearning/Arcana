"""Run entity/relation extraction over chunks already in the chunk store.

Ingestion embeds and extracts in one pass. If extraction fails part-way
through a corpus, for example because an LLM provider runs out of credit,
re-running ingestion would pay for the embeddings a second time and would
still leave the vector index and the graph covering different documents.
That mismatch is not merely wasteful: an ablation run against it compares a
dense arm that can see every document with a graph arm that can see only
some, which understates the graph signal for a reason unrelated to the
graph.

This script closes the gap. It reads chunks straight from the chunk store,
runs extraction only for documents whose entities are not already in the
graph, and merges the results into the same graph file the benchmark reads.

Usage
-----
    uv run python -m eval.extract_only --status
    uv run python -m eval.extract_only --limit-docs 2      # try a couple first
    uv run python -m eval.extract_only
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="report coverage and exit")
    ap.add_argument("--limit-docs", type=int, default=0)
    ap.add_argument("--save-every", type=int, default=25, help="persist the graph every N chunks")
    args = ap.parse_args()

    from api.core.logging import configure_logging
    from api.core.settings import get_settings
    from api.ingestion.extractor import extract_entities
    from api.ingestion.pipeline import _merge_extraction
    from api.llm.service import LLMService
    from api.stores.jsonl_chunk_store import JsonlChunkStore
    from api.stores.networkx_store import NetworkXGraphStore

    configure_logging()
    settings = get_settings()
    storage = settings.local_storage_path
    graph_path = storage / "graphs" / "anon.json"
    graph = NetworkXGraphStore(persist_path=graph_path)
    chunks_store = JsonlChunkStore(root=storage)
    chunks = await chunks_store.list_all()

    g = getattr(graph, "_g", None)
    covered: set[str] = set()
    if g is not None:
        for _, attrs in g.nodes(data=True):
            for cid in attrs.get("mentioned_in_chunks") or []:
                covered.add(str(cid))

    by_doc: dict[str, list] = defaultdict(list)
    for c in chunks:
        by_doc[c.doc_id].append(c)

    print(f"graph   : {g.number_of_nodes() if g else 0} nodes / "
          f"{g.number_of_edges() if g else 0} edges  ({graph_path})")
    print(f"chunks  : {len(chunks)} across {len(by_doc)} documents\n")

    pending: list[tuple[str, list]] = []
    for doc_id, doc_chunks in sorted(by_doc.items()):
        missing = [c for c in doc_chunks if c.id not in covered]
        state = "covered" if not missing else f"{len(missing)}/{len(doc_chunks)} missing"
        print(f"  {'OK ' if not missing else '-> '} {doc_id[:52]:54} {state}")
        if missing:
            pending.append((doc_id, missing))

    total_missing = sum(len(m) for _, m in pending)
    print(f"\n{len(pending)} document(s) need extraction, {total_missing} chunk(s)")
    if args.status or not pending:
        await chunks_store.aclose()
        return 0

    if args.limit_docs:
        pending = pending[: args.limit_docs]

    llm = LLMService(settings=settings)
    done = failed = 0
    t0 = time.perf_counter()
    try:
        for doc_id, missing in pending:
            print(f"\n--> {doc_id[:60]}  ({len(missing)} chunks)")
            for n, ch in enumerate(missing, 1):
                try:
                    extraction = await extract_entities(
                        text=ch.text, chunk_id=ch.id, doc_id=doc_id, llm=llm
                    )
                    await _merge_extraction(extraction, graph=graph)
                    done += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    if failed <= 3 or failed % 50 == 0:
                        print(f"    chunk {n}: {type(exc).__name__}: {str(exc)[:130]}")
                    # A provider that is out of credit fails on every call;
                    # stop rather than burning through the whole corpus.
                    if failed >= 20 and done == 0:
                        print("\nAborting: 20 consecutive failures with no successes.")
                        raise SystemExit(2)
                if (done + failed) % args.save_every == 0:
                    with contextlib.suppress(Exception):
                        graph.save()
                    print(f"    {n}/{len(missing)}  graph: "
                          f"{g.number_of_nodes()} nodes / {g.number_of_edges()} edges")
            with contextlib.suppress(Exception):
                graph.save()
    finally:
        with contextlib.suppress(Exception):
            graph.save()
        with contextlib.suppress(Exception):
            await llm.aclose()
        with contextlib.suppress(Exception):
            await chunks_store.aclose()

    print(f"\nextracted {done}, failed {failed}, in {time.perf_counter() - t0:.0f}s")
    print(f"graph now: {g.number_of_nodes()} nodes / {g.number_of_edges()} edges")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
