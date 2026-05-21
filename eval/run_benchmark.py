"""Hybrid vs flat-RAG benchmark — P1 §1.12.

Real implementation:
  - Loads eval/questions.yaml (pre-registered).
  - Runs each question against TWO pipelines that share embeddings,
    corpus, and chunking (R-02 methodological guard) — only retrieval
    differs.
  - Computes answer accuracy, citation correctness, latency
    (eval/metrics.py).
  - Emits a tables-and-plots report (eval/report.py).

The slice ships this as a stub so `make bench` is a real command (not
a "not yet wired" placeholder) that documents the deferral. When the
benchmark lands, this file gains the actual driver.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "eval.run_benchmark: scaffold only.\n"
        "  Real benchmark runs hybrid vs flat-RAG on eval/questions.yaml.\n"
        "  Implementation: docs/checklist.md §1.12 (FYP 2 / P1).\n"
        "  Methodological guard (R-02): embeddings, corpus, chunking, and\n"
        "  the question set MUST be identical between the two runs."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
