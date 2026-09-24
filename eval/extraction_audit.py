"""Knowledge-graph extraction audit: is an extracted relation supported by its source text?

Motivation
----------
A component grounded in a spurious edge is grounded in nothing, and the
failure is invisible in the interface: a contradiction alert built on a
mis-extracted relation looks exactly like a correct one. This script is
the operational detector for that failure.

Procedure
---------
1. Sample `--n` edges uniformly at random from the persisted graph, under
   a fixed `--seed` so the sample is reproducible.
2. Recover candidate source text. Edges do not carry a chunk id (only
   nodes record `mentioned_in_chunks`), so the source is taken as the
   chunks in which BOTH endpoints are mentioned. An edge with no such
   chunk is recorded as `no_shared_chunk` and counted against precision,
   since it asserts a relation no single passage supports.
3. Judge each sampled edge against its source text with a fixed rubric:
   SUPPORTED  the passage states or directly implies the relation
   UNSUPPORTED the passage does not support it
   UNCLEAR    the passage is ambiguous or the relation is vacuous
4. Report precision with a Wilson 95% interval, overall and by relation
   type, and write every judgement to CSV so a human can re-check any
   subsample and so the annotation is auditable rather than asserted.

Usage
-----
    uv run python -m eval.extraction_audit --n 150 --seed 20260907
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "eval" / "results"

RUBRIC = """You audit knowledge-graph extraction. You are given a passage from a \
research paper and one relation triple that a system extracted from it.

Answer with exactly one word on the first line:
SUPPORTED   - the passage states the relation, or directly implies it
UNSUPPORTED - the passage does not support the relation
UNCLEAR     - the passage is ambiguous, or the relation is vacuous or tautological

Then one short sentence of justification on the second line.

Judge only whether THIS passage supports THIS triple. Do not use outside \
knowledge. A triple that is true in general but absent from the passage is \
UNSUPPORTED."""


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--max-chars", type=int, default=1400)
    args = ap.parse_args()

    from api.core.settings import get_settings
    from api.llm.service import LLMService
    from api.llm.types import Message
    from api.stores.jsonl_chunk_store import JsonlChunkStore
    from api.stores.networkx_store import NetworkXGraphStore

    settings = get_settings()
    graph_path = settings.local_storage_path / "graphs" / "anon.json"
    graph_store = NetworkXGraphStore(persist_path=graph_path)
    g = getattr(graph_store, "_g", None)
    if g is None or g.number_of_edges() == 0:
        print(f"No graph at {graph_path}", file=sys.stderr)
        return 1

    chunk_store = JsonlChunkStore(root=settings.local_storage_path)
    all_chunks = {c.id: c for c in await chunk_store.list_all()}

    edges = [(u, v, k) for u, v, k in g.edges(keys=True)]
    rng = random.Random(args.seed)
    sample = rng.sample(edges, min(args.n, len(edges)))

    print(f"graph   : {g.number_of_nodes()} nodes / {g.number_of_edges()} edges")
    print(f"sample  : {len(sample)} edges, seed={args.seed}")
    print(f"chunks  : {len(all_chunks)}\n")

    llm = LLMService(settings=settings)
    rows: list[dict] = []
    verdict_counts: Counter[str] = Counter()
    by_type: dict[str, Counter] = defaultdict(Counter)

    try:
        for i, (u, v, rtype) in enumerate(sample, 1):
            un, vn = g.nodes[u], g.nodes[v]
            u_chunks = set(un.get("mentioned_in_chunks") or [])
            v_chunks = set(vn.get("mentioned_in_chunks") or [])
            shared = sorted(u_chunks & v_chunks)
            triple = f"({un.get('label', u)}) -[{rtype}]-> ({vn.get('label', v)})"

            if not shared:
                verdict, why, src_id, passage = "NO_SHARED_CHUNK", "no passage mentions both endpoints", "", ""
            else:
                src_id = shared[0]
                ch = all_chunks.get(src_id)
                passage = (getattr(ch, "text", "") or "")[: args.max_chars]
                if not passage:
                    verdict, why = "NO_SHARED_CHUNK", "source chunk text unavailable"
                else:
                    prompt = f"PASSAGE:\n{passage}\n\nTRIPLE:\n{triple}\n\nVerdict:"
                    try:
                        comp = await llm.complete(
                            messages=[Message(role="user", content=prompt)],
                            system=RUBRIC,
                            max_tokens=90,
                        )
                        out = (getattr(comp, "text", "") or "").strip()
                        m = re.search(r"\b(SUPPORTED|UNSUPPORTED|UNCLEAR)\b", out.upper())
                        verdict = m.group(1) if m else "UNCLEAR"
                        why = " ".join(out.split("\n")[1:])[:200] or out[:200]
                    except Exception as exc:  # noqa: BLE001
                        verdict, why = "ERROR", f"{type(exc).__name__}: {exc}"[:200]

            verdict_counts[verdict] += 1
            by_type[str(rtype)][verdict] += 1
            rows.append(
                {
                    "n": i,
                    "src": u,
                    "rel": rtype,
                    "dst": v,
                    "triple": triple,
                    "verdict": verdict,
                    "justification": why,
                    "source_chunk": src_id,
                    "passage_excerpt": passage[:300].replace("\n", " "),
                }
            )
            if i % 10 == 0 or i == len(sample):
                print(f"  [{i:3}/{len(sample)}] " + "  ".join(f"{k}={v}" for k, v in verdict_counts.most_common()))
    finally:
        with contextlib.suppress(Exception):
            await llm.aclose()
        with contextlib.suppress(Exception):
            await chunk_store.aclose()

    judged = sum(verdict_counts[k] for k in ("SUPPORTED", "UNSUPPORTED", "UNCLEAR", "NO_SHARED_CHUNK"))
    supported = verdict_counts["SUPPORTED"]
    lo, hi = wilson(supported, judged)

    print(f"\nprecision (SUPPORTED / all judged): {supported}/{judged} = {supported / judged:.3f}")
    print(f"Wilson 95% CI: [{lo:.3f}, {hi:.3f}]")
    print("\nby relation type (top 12 by frequency):")
    for rtype, c in sorted(by_type.items(), key=lambda kv: -sum(kv[1].values()))[:12]:
        n = sum(c.values())
        print(f"  {rtype[:26]:28} n={n:3}  supported={c['SUPPORTED']:3}  unsupported={c['UNSUPPORTED']:3}  unclear={c['UNCLEAR']:3}  no_src={c['NO_SHARED_CHUNK']:3}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / "extraction_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    json_path = RESULTS_DIR / "extraction_audit.json"
    json_path.write_text(
        json.dumps(
            {
                "generated": datetime.now(UTC).isoformat(),
                "graph_nodes": g.number_of_nodes(),
                "graph_edges": g.number_of_edges(),
                "sample_size": len(sample),
                "seed": args.seed,
                "verdicts": dict(verdict_counts),
                "precision": supported / judged if judged else None,
                "wilson_95": [lo, hi],
                "by_relation_type": {k: dict(v) for k, v in by_type.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nPer-edge judgements -> {csv_path}\nSummary -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
