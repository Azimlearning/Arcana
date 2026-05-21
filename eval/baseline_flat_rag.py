"""Flat-RAG baseline — P1 §1.12.

Loads the same corpus + embeddings + chunking as the hybrid run, but
disables the graph retriever (FR-RET-04 / R-02). Slice ships a stub.
"""

from __future__ import annotations


def main() -> int:
    print("eval.baseline_flat_rag: stub. Implementation lands in P1 §1.12.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
