"""DocumentAgent - Tier 3. Single-document structured overview (CornellNotes).

Provides a focused, structured summary of a specific document from the corpus.
Distinct from LearningAgent (topic-focused) -- DocumentAgent is document-focused.

Intent "document" -> CornellNotes (studio panel)
"""

from __future__ import annotations

import json
import re

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrieverProtocol

logger = get_logger(__name__)

_DOCUMENT_SYSTEM = (
    "You are an academic note-taker. Given excerpts from a document, produce structured Cornell Notes.\n\n"
    "Respond ONLY with valid JSON (no prose, no markdown):\n"
    "{\n"
    '  "topic": "document or paper topic",\n'
    '  "notes": [\n'
    '    {"cue": "keyword or question", "content": "1-3 sentence answer", "citationIds": ["c1"]}\n'
    "  ],\n"
    '  "summary": "2-3 sentence bottom summary paragraph"\n'
    "}\n\n"
    "Generate 5-8 notes. Cues are concise keywords or questions. Content is explanatory prose."
)


def _parse_json(raw: str, default: dict) -> dict:
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("document_agent.json_parse_failed", raw_len=len(raw))
        return default


class DocumentAgent(BaseAgent):
    """Tier-3 output agent. Produces a CornellNotes overview of a queried document."""

    name = "document"
    tier = 3

    def __init__(
        self,
        *,
        llm_service: LLMService,
        vector_retriever: RetrieverProtocol,
        bm25_retriever: RetrieverProtocol,
        graph_retriever: RetrieverProtocol,
    ) -> None:
        self._llm = llm_service
        self._vector = vector_retriever
        self._bm25 = bm25_retriever
        self._graph = graph_retriever

    async def run(self, query: str, state: AgentState) -> AgentResult:
        chunks = await hybrid_retrieve(
            query, top_k=10,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            return AgentResult(
                agent_name=self.name, payload={}, status="failed",
                error="No document content retrieved",
            )

        ctx = "\n\n".join(f"[c{i + 1}] {c.text[:500]}" for i, c in enumerate(chunks[:8]))
        try:
            raw = await self._llm.complete(
                [Message(role="user", content=f"Cornell Notes for: {query}\n\nExcerpts:\n{ctx}")],
                system=_DOCUMENT_SYSTEM,
            )
        except Exception as exc:
            return AgentResult(agent_name=self.name, payload={}, status="failed", error=str(exc))

        data = _parse_json(raw, {"topic": query, "notes": [], "summary": ""})

        citations = []
        seen: set[str] = set()
        for i, c in enumerate(chunks[:8]):
            if c.doc_id not in seen:
                seen.add(c.doc_id)
                citations.append({
                    "id": f"c{i + 1}",
                    "docId": c.doc_id,
                    "docTitle": getattr(c, "doc_title", None) or c.doc_id,
                    "page": None,
                    "quote": c.text[:120],
                })

        return AgentResult(
            agent_name=self.name,
            payload={"block_type": "CornellNotes", "data": {
                "topic": data.get("topic", query),
                "notes": data.get("notes", []),
                "summary": data.get("summary", ""),
                "citations": citations,
            }},
            status="ok",
        )
