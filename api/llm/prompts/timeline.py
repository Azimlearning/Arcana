"""LLM prompts for TimelineAgent — chronological CitedSummary synthesis."""

from __future__ import annotations

from api.retrieval.types import RetrievedChunk

TIMELINE_PROMPT_VERSION = "v1"

TIMELINE_SYSTEM = """\
You are a science-history expert. Organise information from source passages into a \
clear chronological narrative about the development, discovery, or evolution of the \
queried topic.

Structure your response as a timeline narrative:
- Open with the earliest known event or founding idea
- Progress chronologically through key milestones, developments, or turning points
- Close with the current state or most recent development in the sources

Use inline citation markers [c1], [c2], etc. when referencing specific passages. \
Include dates or time periods wherever the sources mention them. Write in a clear, \
informative register.
"""


def build_timeline_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(
        f"[c{i + 1}] doc:{c.doc_id!r} (p.{c.page}) — {c.text}"
        for i, c in enumerate(chunks)
    )
    return (
        f"Describe the chronological development of: {query}\n\n"
        f"Source passages:\n{context}\n\n"
        "Organise the information chronologically with inline citations [cN]. "
        "Include dates and periods where the sources mention them."
    )
