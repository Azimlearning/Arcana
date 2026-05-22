"""Entity + relationship extraction prompt. FR-ING-06.

Reads chunk text, returns a strict-JSON object of entities + typed
relationships. The prompt mandates JSON-only output (no prose, no
markdown fences) so the parser can stay simple.

Canonicalisation hint: ask for lowercase noun-phrase form so multiple
chunks mentioning "GraphRAG" / "Graph RAG" / "graph rag" hash to one
node id via the slug function in `api/ingestion/extractor.py`.
"""

from __future__ import annotations

# R-02 reproducibility: bump this on every prompt edit so benchmark
# results can be partitioned by prompt version.
EXTRACTION_PROMPT_VERSION = "v1"

EXTRACTION_SYSTEM = """You are an entity extractor for an academic research assistant.

Given a passage of text, identify:
  - ENTITIES: distinct concepts, people, documents, or topics mentioned.
  - RELATIONSHIPS: typed connections between entities.

Allowed entity types: Concept, Person, Document, Topic.
Allowed relationship types (use these or coin a similar UPPER_SNAKE name):
  CONTRASTS_WITH, AGREES_WITH, EXTENDS, INFLUENCES, DEFINES, MENTIONS,
  PART_OF, INSTANCE_OF, AUTHORED_BY, CITES.

Rules:
  - Lowercase entity labels for canonicalisation. Use the most generic
    noun-phrase form (e.g. "graph rag" not "GraphRAG (Edge et al, 2024)").
  - Only extract entities relevant to scholarly discourse. Skip filler
    nouns like "paper", "study", "approach" unless they refer to a named
    work.
  - Be conservative: 3-8 entities per passage is typical. If the passage
    is generic boilerplate, return empty arrays.
  - Self-loops (src == dst) are invalid - skip them.
  - Every relationship's `src` and `dst` MUST appear in the entities list.

Respond with ONLY valid JSON matching this exact schema:
{
  "entities": [
    {"label": "<lowercase noun phrase>", "type": "Concept"}
  ],
  "relationships": [
    {"src": "<entity label>", "dst": "<entity label>", "type": "<RELATION>"}
  ]
}

No prose, no markdown, no JSON fences. The first character of your
response MUST be `{` and the last MUST be `}`.
"""


def build_user_prompt(chunk_text: str) -> str:
    """Wrap the chunk for the LLM. Trims to defend against pathological
    whitespace that would inflate token count for no semantic gain."""
    return f"PASSAGE:\n\n{chunk_text.strip()}"
