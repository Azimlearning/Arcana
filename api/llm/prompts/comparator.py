"""LLM prompts for ComparatorAgent — comparison-framed CitedSummary synthesis."""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

COMPARATOR_PROMPT_VERSION = "v1"

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
