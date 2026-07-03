"""WritingAgent - Tier 2. Generates grounded academic draft sections.

Produces DraftEditor payloads (Slice 4, FR-WRT-01) and, for originality
queries, PlagiarismReport payloads (24/24 catalog close, FR-UI-02).

Pipeline:
  1. hybrid_retrieve(query) - grounds all material (invariant #1).
  2. build_draft_prompt() - LLM generates a structured draft.
  3. _parse_draft_response() - defensive parser normalises output.
  4. Returns payload with block_type="DraftEditor".

Plagiarism path (keyword-gated, deterministic — no LLM call):
  trigram overlap between the submitted passage and each retrieved corpus
  chunk → per-chunk similarity flags → originality score. The AI-likelihood
  figure is a self-repetition heuristic (repeated 4-grams), not a trained
  detector — honest-degradation labelling happens in the renderer.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent, tool
from api.core.logging import get_logger
from api.llm.prompts.writing import WRITING_PROMPT_VERSION, WRITING_SYSTEM, build_draft_prompt
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrieverProtocol

logger = get_logger(__name__)


class WritingAgent(BaseAgent):
    """Tier-2 specialist that generates grounded academic draft sections."""

    name = "writing"
    tier = 2

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

    @tool(agent="writing", tier=2)
    async def draft_writing(self, query: str) -> dict:
        """Draft structured academic prose grounded in retrieved evidence."""
        return await self.run_as_tool(query)

    async def run(self, query: str, state: AgentState) -> AgentResult:
        # 1. Ground before generating (invariant #1).
        chunks = await hybrid_retrieve(
            query,
            top_k=8,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            logger.warning("writing.no_chunks", query=query[:80])
            return AgentResult(
                agent_name=self.name,
                payload={},
                status="failed",
                error="No documents retrieved for draft generation.",
            )

        # Originality/plagiarism check path — deterministic, no LLM.
        if _is_plagiarism_query(query):
            payload = _build_plagiarism_report(query, chunks)
            return AgentResult(agent_name=self.name, payload=payload, status="ok")

        ctx_text = "\n\n".join(f"[{c.id}] (doc:{c.doc_id}, p.{c.page}) {c.text}" for c in chunks)

        payload = await self._generate_draft(query, ctx_text)
        return AgentResult(agent_name=self.name, payload=payload, status="ok")

    async def _generate_draft(self, topic: str, ctx_text: str) -> dict[str, Any]:
        messages = [Message(role="user", content=build_draft_prompt(topic, ctx_text))]
        try:
            completion = await self._llm.complete(messages, system=WRITING_SYSTEM, max_tokens=2000)
            raw = completion.text
        except Exception as exc:
            logger.exception("writing.llm_failed")
            return _error_draft_payload(topic, str(exc))

        return _parse_draft_response(raw, topic=topic)


# ── Response parsing ──────────────────────────────────────────────────────


def _strip_fences(text: str) -> str:
    fence = chr(96) * 3
    if text.startswith(fence):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
    if text.rstrip().endswith(fence):
        text = text.rstrip()[: -len(fence)].rstrip()
    return text.strip()


def _extract_json(text: str) -> dict[str, Any]:
    text = _strip_fences(text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "writing.parse_failed", raw_preview=text[:120], version=WRITING_PROMPT_VERSION
        )
        return {}


def _safe_source(raw: Any, fallback_id: str = "c1") -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"id": fallback_id, "docId": "", "docTitle": "Unknown", "page": None, "quote": ""}
    return {
        "id": str(raw.get("id") or fallback_id),
        "docId": str(raw.get("docId") or ""),
        "docTitle": str(raw.get("docTitle") or "Unknown"),
        "page": raw.get("page"),
        "quote": str(raw.get("quote") or ""),
    }


def _parse_draft_response(raw: str, *, topic: str) -> dict[str, Any]:
    parsed = _extract_json(raw)
    title = str(parsed.get("title") or topic[:80])

    raw_sections = parsed.get("sections") or []
    sections: list[dict[str, Any]] = []
    if isinstance(raw_sections, list):
        for s in raw_sections:
            if not isinstance(s, dict):
                continue
            sections.append(
                {
                    "heading": str(s.get("heading") or ""),
                    "body": str(s.get("body") or ""),
                    "citationIds": [str(c) for c in (s.get("citationIds") or []) if c],
                }
            )

    raw_citations = parsed.get("citations") or []
    citations: list[dict[str, Any]] = []
    if isinstance(raw_citations, list):
        for cit in raw_citations:
            if isinstance(cit, dict):
                citations.append(_safe_source(cit))

    word_count_raw = parsed.get("wordCount")
    if isinstance(word_count_raw, (int, float)):
        word_count = int(word_count_raw)
    else:
        word_count = sum(len(s["body"].split()) for s in sections)

    return {
        "block_type": "DraftEditor",
        "data": {
            "title": title,
            "sections": sections,
            "citations": citations,
            "wordCount": word_count,
        },
    }


# ── Plagiarism / originality check (deterministic — FR-UI-02 catalog close) ──

_PLAGIARISM_KEYWORDS = ("plagiar", "originality", "ai content", "ai-generated", "ai generated")

# Chunks whose trigram overlap with the passage exceeds this become flags.
_SIMILARITY_FLAG_THRESHOLD = 0.15
_MAX_FLAGS = 5


def _is_plagiarism_query(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in _PLAGIARISM_KEYWORDS)


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _trigram_similarity(passage: str, chunk_text: str) -> float:
    """|shared trigrams| / |passage trigrams| — how much of the passage
    re-appears verbatim(ish) in the chunk."""
    passage_grams = _ngrams(passage, 3)
    if not passage_grams:
        return 0.0
    return len(passage_grams & _ngrams(chunk_text, 3)) / len(passage_grams)


def _self_repetition(passage: str) -> float:
    """Crude AI-likelihood proxy: share of repeated 4-grams inside the
    passage itself. NOT a trained detector — labelled as heuristic in the
    renderer (honest degradation, NFR-REL-01)."""
    words = re.findall(r"[a-z0-9']+", passage.lower())
    total = max(len(words) - 3, 0)
    if total == 0:
        return 0.0
    grams = [tuple(words[i : i + 4]) for i in range(total)]
    repeated = total - len(set(grams))
    return min(repeated / total, 1.0)


def _build_plagiarism_report(query: str, chunks: list[Any]) -> dict[str, Any]:
    scored = sorted(
        ((c, _trigram_similarity(query, c.text)) for c in chunks),
        key=lambda pair: pair[1],
        reverse=True,
    )
    flags: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    for i, (chunk, sim) in enumerate(scored[:_MAX_FLAGS], start=1):
        if sim < _SIMILARITY_FLAG_THRESHOLD:
            break
        flags.append(
            {
                "excerpt": chunk.text[:200],
                "matchSource": getattr(chunk, "doc_title", None) or chunk.doc_id,
                "docId": chunk.doc_id,
                "similarity": round(sim, 3),
                "flagKind": "similarity",
            }
        )
        citations.append(
            {
                "id": f"c{i}",
                "docId": chunk.doc_id,
                "docTitle": getattr(chunk, "doc_title", None) or chunk.doc_id,
                "page": chunk.page,
                "quote": chunk.text[:120],
            }
        )

    max_similarity = scored[0][1] if scored else 0.0
    return {
        "block_type": "PlagiarismReport",
        "data": {
            "draftTitle": query[:80],
            "originalityScore": round(max(0.0, 1.0 - max_similarity), 3),
            "aiLikelihood": round(_self_repetition(query), 3),
            "flags": flags,
            "checkedAt": datetime.now(UTC).isoformat(),
            "citations": citations,
        },
    }


def _error_draft_payload(topic: str, error: str) -> dict[str, Any]:
    return {
        "block_type": "DraftEditor",
        "data": {
            "title": topic[:80],
            "sections": [],
            "citations": [],
            "wordCount": 0,
        },
        "_error": error,
    }
