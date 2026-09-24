"""Diagnostic: what entities does a query extract, and do they exist in the graph?

Graph retrieval scores chunks starting from query entities that resolve to a
node id. If the extractor emits a slug the graph does not carry, the graph
arm contributes nothing and the hybrid pipeline silently degrades to flat.
This prints, per benchmark question, which extracted entities hit and which
miss, and for each miss the nearest node ids by token overlap.

Usage:
    uv run python -m eval.probe_entities --limit 8
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def tokens(slug: str) -> set[str]:
    return {t for t in slug.split("_") if t}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()

    from api.core.settings import get_settings
    from api.ingestion.extractor import extract_entities
    from api.llm.service import LLMService
    from api.stores.networkx_store import NetworkXGraphStore

    settings = get_settings()
    graph = NetworkXGraphStore(
        persist_path=settings.local_storage_path / "graphs" / "anon.json"
    )
    g = getattr(graph, "_g", None)
    node_ids = list(g.nodes()) if g is not None else []
    node_tokens = {n: tokens(n) for n in node_ids}
    print(f"graph: {len(node_ids)} nodes\n")

    questions = yaml.safe_load(
        (REPO_ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8")
    )["questions"][: args.limit]

    llm = LLMService(settings=settings)
    hit_total = miss_total = 0
    try:
        for q in questions:
            text = " ".join(str(q["question"]).split())
            try:
                ex = await extract_entities(
                    text=text, chunk_id="query", doc_id="query", llm=llm
                )
            except Exception as e:  # noqa: BLE001
                print(f"{q['id']}: EXTRACT FAILED {e}")
                continue
            hits, misses = [], []
            for n in ex.nodes:
                if n.id in node_tokens:
                    hits.append(n.id)
                    continue
                # Same path the retriever takes: exact, then approximate.
                alias = await graph.resolve_nodes(n.id)
                if alias:
                    hits.append(f"{n.id} ~ {alias[0].id}")
                else:
                    misses.append(n.id)
            hit_total += len(hits)
            miss_total += len(misses)
            print(f"{q['id']}  hits={len(hits)} misses={len(misses)}")
            if hits:
                print(f"   hit : {', '.join(hits[:6])}")
            for m in misses[:4]:
                mt = tokens(m)
                near = sorted(
                    (
                        (len(mt & nt) / max(1, len(mt | nt)), n)
                        for n, nt in node_tokens.items()
                        if mt & nt
                    ),
                    reverse=True,
                )[:3]
                pretty = ", ".join(f"{n} ({s:.2f})" for s, n in near) or "no overlap"
                print(f"   miss: {m}  ->  {pretty}")
    finally:
        with contextlib.suppress(Exception):
            await llm.aclose()

    total = hit_total + miss_total
    print(f"\nquery entities resolved: {hit_total}/{total}"
          + (f" ({hit_total / total:.0%})" if total else ""))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
