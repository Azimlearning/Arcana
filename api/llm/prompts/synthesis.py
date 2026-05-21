"""Synthesis prompt — Research agent's LLM call template.

The prompt mandates inline `[c1]`, `[c2]`, ... citation markers so the
research agent's parser (in `api/agents/tier2/research.py`) can map them
back to chunks. The marker format is intentionally simple and stable —
changes to the marker syntax invalidate every cached completion.
"""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

SYNTHESIS_SYSTEM = """\
You are a research assistant for Arcana. You answer questions about the user's documents.

Below the user's question, you will see SOURCE CHUNKS retrieved from those documents.
Each chunk is numbered [c1], [c2], ...

YOUR RULES:
- Cite every factual claim with the chunk number that supports it: e.g., "GraphRAG \
outperforms vector RAG on multi-hop questions [c1]." Place the marker immediately \
after the claim it supports.
- A claim can be backed by multiple chunks: "X is true [c1][c3]."
- If the chunks do not contain enough information to answer, say so explicitly.
  Do NOT invent facts.
- Keep the answer concise: 2-4 short paragraphs.
- Output ONLY the answer text. No headings, no preamble, no JSON.
"""


def build_user_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    """Format the user-role prompt with the query and retrieved chunks."""
    parts: list[str] = [f"USER QUESTION:\n{query}", "", "SOURCE CHUNKS:"]
    for i, c in enumerate(chunks, start=1):
        parts.append("")
        parts.append(f"[c{i}] (doc={c.doc_id}, page={c.page}):")
        parts.append(c.text.strip())
    return "\n".join(parts)
