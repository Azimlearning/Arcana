"""NFR verification harness — P1 §1.11 perf + scalability targets.

Measures the *live, user-facing* non-functional targets against a running
Arcana backend and prints a PASS/FAIL table. These targets are end-to-end
latencies (time-to-first-token, full synthesis, ingest, concurrency), so they
must be measured over the wire against a real server with API keys configured
— they cannot be unit-tested in isolation.

What this does NOT cover (verified elsewhere, no live run needed):
  - NFR-PERF-04 (500-node graph render < 2s) → api/stores/tests/test_graph_perf.py
  - NFR-REL-01 (retriever degradation)       → api/retrieval/tests/test_hybrid.py
  - NFR-REL-02 (LLM provider fallback)        → api/llm/tests/test_service_fallback.py
  - NFR-COST-01 (token/hop budget guard)      → api/core/tests/test_budget.py

Usage
-----
    # plan only, no server needed
    uv run python -m eval.nfr_check --dry-run

    # measure against a running backend (needs api/.env keys + ingested corpus)
    uv run python -m eval.nfr_check --base-url http://localhost:8000 \
        --pdf eval/corpus/sample_20pg.pdf --concurrency 12
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from dataclasses import dataclass

# Targets straight from PRD §18.1 / §18.2.
TARGETS = {
    "NFR-PERF-01 time-to-first-token": 3.0,
    "NFR-PERF-02 full synthesis": 15.0,
    "NFR-PERF-03 20-page PDF ingest": 60.0,
}
CONCURRENCY_TARGET = (10, 15)  # NFR-SCAL-02 concurrent users


@dataclass
class Measure:
    name: str
    target_s: float
    measured_s: float | None
    note: str = ""

    @property
    def passed(self) -> bool | None:
        if self.measured_s is None:
            return None
        return self.measured_s <= self.target_s


async def _time_to_first_and_done(client, base_url: str, query: str) -> tuple[float, float]:
    """Stream POST /chat; return (time-to-first-frame, time-to-done)."""
    t0 = time.perf_counter()
    first: float | None = None
    async with client.stream(
        "POST", f"{base_url}/chat",
        json={"notebookId": "nfr", "message": query, "history": []},
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if line.startswith("event:") and first is None:
                first = time.perf_counter() - t0
            if line.startswith("event: done"):
                break
    done = time.perf_counter() - t0
    return (first if first is not None else done), done


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


async def _measure_ingest(client, base_url: str, pdf_path: str) -> float:
    # Read off the event loop so the upload timing isn't skewed by disk I/O.
    data = await asyncio.to_thread(_read_bytes, pdf_path)
    t0 = time.perf_counter()
    files = {"file": (os.path.basename(pdf_path), data, "application/pdf")}
    resp = await client.post(f"{base_url}/ingest", files=files, data={"notebook_id": "nfr"})
    resp.raise_for_status()
    return time.perf_counter() - t0


async def run(args) -> list[Measure]:
    import httpx

    results: list[Measure] = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        # PERF-03 ingest (optional — only if a PDF is supplied)
        if args.pdf:
            dt = await _measure_ingest(client, args.base_url, args.pdf)
            results.append(Measure("NFR-PERF-03 20-page PDF ingest", 60.0, dt))
        else:
            results.append(Measure("NFR-PERF-03 20-page PDF ingest", 60.0, None, "no --pdf supplied"))

        # PERF-01 / PERF-02 from a single chat turn
        ttft, synth = await _time_to_first_and_done(client, args.base_url, args.query)
        results.append(Measure("NFR-PERF-01 time-to-first-token", 3.0, ttft))
        results.append(Measure("NFR-PERF-02 full synthesis", 15.0, synth))

        # SCAL-02 concurrency: fire N turns, report success + p95
        n = args.concurrency
        t0 = time.perf_counter()
        outcomes = await asyncio.gather(
            *(_time_to_first_and_done(client, args.base_url, args.query) for _ in range(n)),
            return_exceptions=True,
        )
        wall = time.perf_counter() - t0
        ok = sum(1 for o in outcomes if not isinstance(o, Exception))
        results.append(
            Measure(
                f"NFR-SCAL-02 {n} concurrent users", 15.0, wall,
                note=f"{ok}/{n} succeeded; target {CONCURRENCY_TARGET[0]}-{CONCURRENCY_TARGET[1]} concurrent",
            )
        )
    return results


def _print_report(results: list[Measure]) -> int:
    print(f"\n{'NFR':<40} {'target':>8} {'measured':>10}  result")
    print("-" * 72)
    failures = 0
    for m in results:
        meas = f"{m.measured_s:.2f}s" if m.measured_s is not None else "—"
        if m.passed is None:
            verdict = "SKIP"
        elif m.passed:
            verdict = "PASS"
        else:
            verdict = "FAIL"
            failures += 1
        print(f"{m.name:<40} {m.target_s:>7.0f}s {meas:>10}  {verdict}  {m.note}")
    print("-" * 72)
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description="Arcana NFR verification (§1.11)")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--query", default="What are the main themes across my documents?")
    ap.add_argument("--pdf", default=None, help="path to a ~20-page PDF for the ingest measurement")
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--dry-run", action="store_true", help="print the plan without calling the server")
    args = ap.parse_args()

    if args.dry_run:
        print("NFR check plan (no server contacted):")
        for name, target in TARGETS.items():
            print(f"  - {name}: target <= {target:.0f}s")
        print(f"  - NFR-SCAL-02: {args.concurrency} concurrent /chat turns "
              f"(target {CONCURRENCY_TARGET[0]}-{CONCURRENCY_TARGET[1]})")
        print("  (PERF-04 / REL-01 / REL-02 / COST-01 are covered by pytest — see module docstring.)")
        return 0

    results = asyncio.run(run(args))
    failures = _print_report(results)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
