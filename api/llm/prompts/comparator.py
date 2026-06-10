"""LLM prompts for ComparatorAgent — FR-RET-05 cross-document comparison."""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

COMPARATOR_PROMPT_VERSION = "v2"

# ── Multi-document structured matrix (primary path, ≥2 docs) ─────────────────

COMPARATOR_MATRIX_SYSTEM = """\
You are a comparative analysis expert. Given retrieved passages from multiple documents, \
produce a structured comparison matrix so the reader can understand how the documents \
agree, differ, or complement each other on key dimensions.

Respond ONLY with valid JSON matching this exact shape:
{
  "dimensions": ["<aspect1>", "<aspect2>", "<aspect3>"],
  "rows": [
    {
      "docId": "<doc_id>",
      "docTitle": "<title or doc_id if unknown>",
      "cells": [
        {"text": "<1-2 sentence assessment>", "citationId": "<cN or null>"}
      ]
    }
  ]
}

Rules:
- 3-5 dimensions that best highlight similarities AND differences (e.g. methodology, \
  findings, limitations, approach, scope, key contribution)
- One row per unique document in the provided context
- Each cell: concise comparison assessment (1-2 sentences); write "Not reported" if absent
- citationId: the [cN] marker from the passage if relevant, otherwise null
- Every row must have exactly as many cells as there are dimensions (in order)
- Focus on HOW the documents differ, not just what each says in isolation
"""


def build_comparator_matrix_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[c{i + 1}] doc:{c.doc_id!r} — {c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"Compare documents for this question: {query}\n\n"
        f"Source passages:\n{context}\n\n"
        "Identify 3-5 dimensions that best differentiate the documents and fill one "
        "row per document. Return JSON only — no prose before or after."
    )


# ── Single-document prose fallback ────────────────────────────────────────────

COMPARATOR_SYSTEM = """\
You are a comparative analysis expert. Write a structured comparison of the entities, \
approaches, or concepts mentioned in the query, grounded in the provided source passages.

Structure your response in three parts:
1. A brief introduction establishing what is being compared
2. A comparison across key dimensions (similarities and differences)
3. A synthesis sentence

Use inline citation markers [c1], [c2], etc. when referencing specific passages. \
Write in a clear, academic register. Do not include a bibliography section.
"""


def build_comparator_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[c{i + 1}] doc:{c.doc_id!r} (p.{c.page}) — {c.text}"
        for i, c in enumerate(chunks)
    )
    return (
        f"Compare the concepts or entities in this question: {query}\n\n"
        f"Source passages:\n{context}\n\n"
        "Write a structured comparison with inline citations [cN]. "
        "Highlight both similarities and differences clearly."
    )
