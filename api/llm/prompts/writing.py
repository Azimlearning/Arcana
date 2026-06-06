"""Writing prompts — draft generation.
Used by WritingAgent (FR-WRT-01).
"""

from __future__ import annotations

# Bump on every edit for R-02 benchmark reproducibility.
WRITING_PROMPT_VERSION = "v1"

WRITING_SYSTEM = """You are an academic writing assistant. Generate structured essay drafts grounded in provided document excerpts.

Rules:
- Every section body must trace to provided passages — no invented claims.
- Insert inline citation markers like [c1] in the body text where evidence is drawn.
- Use 3-5 sections with clear academic headings.
- citationIds lists only the IDs actually referenced in that section's body.
- Return ONLY valid JSON with no preamble, no markdown fences."""


def build_draft_prompt(topic: str, context: str) -> str:
    """Build the user turn for draft generation."""
    return f"""Topic: {topic}

Context:
{context}

Write a structured academic draft on this topic using only the provided context.

Respond ONLY with JSON:
{{
  "title": "A clear title for the draft",
  "sections": [
    {{
      "heading": "Section heading",
      "body": "Section body text with [c1] inline citations.",
      "citationIds": ["c1"]
    }}
  ],
  "citations": [
    {{
      "id": "c1",
      "docId": "doc_id_here",
      "docTitle": "Document title",
      "page": 1,
      "quote": "short supporting quote"
    }}
  ],
  "wordCount": 300
}}"""
