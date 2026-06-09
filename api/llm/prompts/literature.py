"""LLM prompts for LiteratureAgent — papers x dimensions comparison matrix."""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

LITERATURE_PROMPT_VERSION = "v1"

LITERATURE_SYSTEM = """\
You are an academic literature analysis expert. Given retrieved passages from academic \
documents, produce a structured comparison matrix so researchers can compare papers \
across key dimensions at a glance.

Respond ONLY with valid JSON matching this exact shape:
{
  "dimensions": ["<aspect1>", "<aspect2>", "<aspect3>"],
  "rows": [
    {
      "docId": "<doc_id>",
      "docTitle": "<title>",
      "cells": [
        {"text": "<1-2 sentence assessment>", "citationId": "<cN or null>"}
      ]
    }
  ]
}

Rules:
- 3-5 dimensions that best differentiate the papers (methodology, dataset, results, \
  limitations, key contribution, etc.)
- One row per unique document in the context
- Each cell: concise assessment (1-2 sentences), never empty — write "Not reported" if absent
- citationId: the [cN] marker from the passage if relevant, otherwise null
- Every row must have exactly as many cells as there are dimensions (in order)
"""


def build_literature_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[c{i + 1}] doc:{c.doc_id!r} — {c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"Compare documents for this research question: {query}\n\n"
        f"Source passages:\n{context}\n\n"
        "Identify 3-5 key comparison dimensions and fill one row per document. "
        "Return JSON only — no prose before or after."
    )
