"""LLM prompts for AnnotationAgent — claim-extraction and coverage gap analysis."""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

ANNOTATION_PROMPT_VERSION = "v1"

ANNOTATION_SYSTEM = """\
You annotate and map the coverage of academic source passages on a given topic. \
Identify what claims and subtopics the sources cover, and what is missing or \
underexplored given the query.

Respond ONLY with valid JSON matching this exact shape:
{
  "summary": "<one sentence overall assessment of coverage quality>",
  "gaps": [
    {"label": "<missing subtopic>", "description": "<what is not covered and why it matters>", "severity": "high|medium|low"}
  ],
  "coveredTopics": ["<covered subtopic 1>", "<covered subtopic 2>"]
}

Rules:
- 2-4 gaps maximum; severity "high" only for gaps central to answering the query
- 3-8 covered topics as short noun phrases
- "summary" should note whether coverage is strong, partial, or shallow
"""


def build_annotation_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[c{i + 1}] doc:{c.doc_id!r} — {c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"Annotate the coverage of: {query}\n\n"
        f"Source passages:\n{context}\n\n"
        "Identify what topics are covered and what is missing. "
        "Return JSON only — no prose before or after."
    )
