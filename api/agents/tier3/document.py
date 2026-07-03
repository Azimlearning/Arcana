"""DocumentAgent - Tier 3. Single-document structured overview (CornellNotes).

Provides a focused, structured summary of a specific document from the corpus.
Distinct from LearningAgent (topic-focused) -- DocumentAgent is document-focused.

Intent "document" -> CornellNotes (studio panel)
Audio-overview queries ("audio overview", "podcast", ...) -> AudioSummary
(studio panel): a spoken-style transcript with chapter segments; durations
are estimated at ~150 wpm. TTS synthesis is P2 — `audioUrl` stays null and
the renderer shows the transcript with a "generation pending" player state.
"""

from __future__ import annotations

import json
import re

from api.agents.base import AgentResult, AgentState, BaseAgent, tool
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


_AUDIO_KEYWORDS = ("audio overview", "audio summary", "podcast", "listen to", "narrate")

_AUDIO_SYSTEM = (
    "You are a podcast script writer. Given excerpts from documents, write a spoken-style "
    "overview a listener could follow without seeing the text.\n\n"
    "Respond ONLY with valid JSON (no prose, no markdown):\n"
    "{\n"
    '  "title": "episode title",\n'
    '  "transcript": "the full spoken script, 200-400 words, plain conversational prose",\n'
    '  "segments": [ {"label": "chapter/topic label"} ]\n'
    "}\n\n"
    "Give 2-5 segments in the order they appear in the transcript."
)

# Spoken-word pace used to estimate segment timings until TTS lands (P2).
_WORDS_PER_SECOND = 150 / 60


def _is_audio_query(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in _AUDIO_KEYWORDS)


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

    @tool(agent="document", tier=3)
    async def document_overview(self, query: str) -> dict:
        """Produce a structured Cornell-notes overview of a document or topic."""
        return await self.run_as_tool(query)

    async def run(self, query: str, state: AgentState) -> AgentResult:
        chunks = await hybrid_retrieve(
            query,
            top_k=10,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No document content retrieved",
            )

        ctx = "\n\n".join(f"[c{i + 1}] {c.text[:500]}" for i, c in enumerate(chunks[:8]))

        if _is_audio_query(query):
            return await self._audio_summary(query, ctx, chunks)

        try:
            completion = await self._llm.complete(
                [Message(role="user", content=f"Cornell Notes for: {query}\n\nExcerpts:\n{ctx}")],
                system=_DOCUMENT_SYSTEM,
            )
            raw = completion.text
        except Exception as exc:
            return AgentResult(agent_name=self.name, payload={}, status="failed", error=str(exc))

        data = _parse_json(raw, {"topic": query, "notes": [], "summary": ""})

        citations = []
        seen: set[str] = set()
        for i, c in enumerate(chunks[:8]):
            if c.doc_id not in seen:
                seen.add(c.doc_id)
                citations.append(
                    {
                        "id": f"c{i + 1}",
                        "docId": c.doc_id,
                        "docTitle": getattr(c, "doc_title", None) or c.doc_id,
                        "page": None,
                        "quote": c.text[:120],
                    }
                )

        return AgentResult(
            agent_name=self.name,
            payload={
                "block_type": "CornellNotes",
                "data": {
                    "topic": data.get("topic", query),
                    "notes": data.get("notes", []),
                    "summary": data.get("summary", ""),
                    "citations": citations,
                },
            },
            status="ok",
        )

    async def _audio_summary(self, query: str, ctx: str, chunks: list) -> AgentResult:
        """AudioSummary payload: spoken-style transcript + estimated segment
        timings. `audioUrl` stays None until TTS synthesis lands (P2)."""
        try:
            completion = await self._llm.complete(
                [Message(role="user", content=f"Audio overview of: {query}\n\nExcerpts:\n{ctx}")],
                system=_AUDIO_SYSTEM,
            )
            raw = completion.text
        except Exception as exc:
            return AgentResult(agent_name=self.name, payload={}, status="failed", error=str(exc))

        data = _parse_json(raw, {"title": query[:80], "transcript": "", "segments": []})
        transcript = str(data.get("transcript") or "")
        duration = int(len(transcript.split()) / _WORDS_PER_SECOND) if transcript else 0

        raw_segments = [s for s in (data.get("segments") or []) if isinstance(s, dict)]
        segments = []
        if raw_segments and duration > 0:
            per_segment = duration / len(raw_segments)
            for i, seg in enumerate(raw_segments):
                segments.append(
                    {
                        "label": str(seg.get("label") or f"Part {i + 1}"),
                        "startSec": round(i * per_segment, 1),
                        "endSec": round((i + 1) * per_segment, 1),
                    }
                )

        citations = []
        seen: set[str] = set()
        for i, c in enumerate(chunks[:8]):
            if c.doc_id not in seen:
                seen.add(c.doc_id)
                citations.append(
                    {
                        "id": f"c{i + 1}",
                        "docId": c.doc_id,
                        "docTitle": getattr(c, "doc_title", None) or c.doc_id,
                        "page": None,
                        "quote": c.text[:120],
                    }
                )

        return AgentResult(
            agent_name=self.name,
            payload={
                "block_type": "AudioSummary",
                "data": {
                    "title": str(data.get("title") or query[:80]),
                    "audioUrl": None,
                    "durationSec": duration,
                    "transcript": transcript,
                    "segments": segments,
                    "voice": None,
                    "citations": citations,
                },
            },
            status="ok",
        )
