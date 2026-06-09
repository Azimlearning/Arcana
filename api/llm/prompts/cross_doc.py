"""LLM prompts for CrossDocAgent — serendipitous cross-document insight extraction."""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

CROSS_DOC_PROMPT_VERSION = "v1"

CROSS_DOC_SYSTEM = """\
You surface non-obvious connections between academic documents. Given passages from \
multiple documents, find a serendipitous insight that links two of them in a way not \
apparent from reading either document in isolation.

Respond ONLY with valid JSON matching this exact shape:
{
  "insight": "<the non-obvious insight, 1-2 sentences>",
  "connection": "<how the two documents connect, 1 sentence>",
  "docAId": "<id of first document>",
  "docATitle": "<title of first document>",
  "docBId": "<id of second document>",
  "docBTitle": "<title of second document>",
  "citations": [
    {
      "id": "c1",
      "docId": "<doc_id>",
      "docTitle": "<title>",
      "page": null,
      "quote": "<verbatim supporting quote, max 200 characters>"
    }
  ]
}

Rules:
- Choose the two documents whose connection is most surprising and intellectually valuable
- The insight should be something a researcher might miss without reading both
- Include 1-3 citations (short verbatim quotes) supporting the connection
- docAId and docBId must appear verbatim as they do in the source passages
"""


def build_cross_doc_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[c{i + 1}] doc:{c.doc_id!r} — {c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"Find a cross-document insight for the topic: {query}\n\n"
        f"Source passages from multiple documents:\n{context}\n\n"
        "Identify the most surprising non-obvious connection between two documents. "
        "Return JSON only — no prose before or after."
    )
