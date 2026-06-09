"""LLM prompts for ContradictionAgent — cross-source disagreement detection."""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

CONTRADICTION_PROMPT_VERSION = "v1"

CONTRADICTION_SYSTEM = """\
You detect where academic sources disagree on a concept or claim. Given passages from \
multiple documents, identify genuine contradictions — places where one source explicitly \
or implicitly contradicts another on the same point.

Respond ONLY with valid JSON matching this exact shape:
{
  "concept": "<the contested concept or claim, 3-10 words>",
  "summary": "<one sentence describing the nature of the disagreement>",
  "claims": [
    {
      "docId": "<doc_id>",
      "docTitle": "<title>",
      "stance": "<3-8 word summary of this source's position>",
      "quote": "<verbatim supporting quote from the passage, max 200 characters>"
    }
  ]
}

Rules:
- Only report genuine contradictions — opposing factual claims, not mere phrasing differences
- Include 2-4 claims (one per disagreeing source); stop at 4
- If no real contradiction exists, return: {"concept": "<query topic>", "summary": "No direct contradiction found in the retrieved passages.", "claims": []}
- Quotes must be verbatim (or very close) — no paraphrase
"""


def build_contradiction_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[c{i + 1}] doc:{c.doc_id!r} — {c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"Find contradictions across sources on: {query}\n\n"
        f"Source passages:\n{context}\n\n"
        "Identify where sources directly disagree. "
        "Return JSON only — no prose before or after."
    )
