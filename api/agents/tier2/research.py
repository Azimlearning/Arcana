"""Research Agent — the slice's grounding workhorse.

Pipeline (PRD §12 Research):
  1. `hybrid_retrieve(query)` — vector + BM25 + (slice-empty) graph + RRF.
  2. `summarise_with_grounding` — LLM call against a citation-mandating
     synthesis prompt.
  3. `cite_sources` — parse the LLM's `[cN]` markers, map back to chunks,
     enrich with document titles from `DocStore`. Returns `CitedSummaryData`
     shaped as a plain dict that the UI Agent will validate against the
     generated Pydantic models in `api/genui/_generated.py`.

The citation parser lives here (and not next to the prompt template)
because parsing requires both the LLM output AND the source chunks —
it's the agent that holds both.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from api.agents.base import AgentResult, AgentState, BaseAgent
from api.core.logging import get_logger
from api.embeddings.service import EmbedderProtocol
from api.llm.prompts.synthesis import SYNTHESIS_SYSTEM, build_user_prompt
from api.llm.service import LLMService
from api.llm.types import Message
from api.retrieval.hybrid import hybrid_retrieve
from api.retrieval.types import RetrievedChunk, RetrieverProtocol
from api.stores.doc_store import DocStore
from api.stores.errors import DocNotFound

logger = get_logger(__name__)

# Matches [c1], [c2], ... case-sensitive. ASCII-locked for benchmark determinism.
_CITATION_RE = re.compile(r"\[c(\d+)\]", re.ASCII)

# Citation quote previews are trimmed to this length so we don't ship the
# whole chunk back through SSE (the renderer shows the quote inline).
_QUOTE_PREVIEW_CHARS = 280


class ResearchAgent(BaseAgent):
    """Tier-2 agent. Returns a `CitedSummaryData`-shaped payload."""

    name = "research"
    tier = 2

    def __init__(
        self,
        *,
        llm_service: LLMService,
        embedder: EmbedderProtocol,
        vector_retriever: RetrieverProtocol,
        bm25_retriever: RetrieverProtocol,
        graph_retriever: RetrieverProtocol,
        doc_store: DocStore,
    ) -> None:
        self._llm = llm_service
        self._embedder = embedder  # unused today; held for future P1 query rewrites
        self._vec = vector_retriever
        self._bm25 = bm25_retriever
        self._graph = graph_retriever
        self._doc = doc_store

    async def run(self, query: str, state: AgentState) -> AgentResult:
        try:
            chunks = await hybrid_retrieve(
                query,
                top_k=10,
                vector_retriever=self._vec,
                bm25_retriever=self._bm25,
                graph_retriever=self._graph,
                mode=state.retrieval_mode,  # type: ignore[arg-type]  # FR-RET-07
            )
        except Exception as e:
            logger.exception("research_agent.retrieval_failed")
            return self._fail(state, f"retrieval failed: {e}")

        if not chunks:
            return self._no_evidence(state)

        state.retrieved_ctx.extend(chunks)

        try:
            completion = await self._llm.complete(
                messages=[Message(role="user", content=build_user_prompt(query, chunks))],
                system=SYNTHESIS_SYSTEM,
                budget=state.budget,
            )
        except Exception as e:
            logger.exception("research_agent.llm_failed")
            return self._fail(state, f"LLM call failed: {e}")

        segments, citations = _parse_segments_and_citations(completion.text, chunks)
        citations = await self._enrich_titles(citations)

        payload: dict[str, Any] = {
            "summary": completion.text,
            "segments": [
                {"text": s["text"], "citationIds": s["citationIds"]} for s in segments
            ],
            "citations": citations,
        }
        result = AgentResult(agent_name=self.name, payload=payload, status="ok")
        state.agent_results[self.name] = result
        return result

    # ── Failure paths ─────────────────────────────────────────────
    def _no_evidence(self, state: AgentState) -> AgentResult:
        payload = {
            "summary": "I couldn't find anything relevant in your documents.",
            "segments": [
                {"text": "No evidence in the corpus matches this query.", "citationIds": []}
            ],
            "citations": [],
        }
        result = AgentResult(
            agent_name=self.name,
            payload=payload,
            status="partial",
            error="hybrid_retrieve returned 0 chunks",
        )
        state.agent_results[self.name] = result
        return result

    def _fail(self, state: AgentState, msg: str) -> AgentResult:
        payload = {
            "summary": f"Sorry, I hit an error before I could answer: {msg}",
            "segments": [{"text": "Research agent failed.", "citationIds": []}],
            "citations": [],
        }
        result = AgentResult(
            agent_name=self.name, payload=payload, status="failed", error=msg
        )
        state.agent_results[self.name] = result
        return result

    # ── Title enrichment ─────────────────────────────────────────
    async def _enrich_titles(
        self, citations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Resolve doc titles via DocStore. Caches per doc_id so we don't
        re-fetch the same metadata for citations of the same document."""
        title_cache: dict[str, str] = {}
        for cit in citations:
            doc_id = cit["docId"]
            if doc_id not in title_cache:
                try:
                    meta = await self._doc.get_metadata(doc_id)
                    title_cache[doc_id] = meta.title
                except DocNotFound:
                    title_cache[doc_id] = doc_id  # fall back to id so UI shows something
                except Exception as e:  # don't fail the whole turn over a title fetch
                    logger.warning(
                        "research_agent.title_enrich_failed",
                        doc_id=doc_id,
                        error=str(e),
                    )
                    title_cache[doc_id] = doc_id
            cit["docTitle"] = title_cache[doc_id]
        return citations


# ─── Citation parser (Option 1 per slice plan: lives next to the agent) ──


def _parse_segments_and_citations(
    text: str, chunks: list[RetrievedChunk]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Walk LLM output, extract `[cN]` markers, build `segments` + `citations`
    payload entries (camelCase keys to match the wire schema).

    Returns dicts (not Pydantic models) so the UI Agent can do the final
    validation against `CitedSummaryData` from `_generated.py`.
    """
    citations = _build_citations(text, chunks)
    segments = _build_segments(text)
    return segments, citations


def _build_citations(text: str, chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    """One Citation per UNIQUE valid [cN] index that appears in the text."""
    seen: set[int] = set()
    ordered_indices: list[int] = []
    for m in _CITATION_RE.finditer(text):
        idx = int(m.group(1))
        if idx not in seen and 1 <= idx <= len(chunks):
            seen.add(idx)
            ordered_indices.append(idx)
    citations: list[dict[str, Any]] = []
    for idx in ordered_indices:
        chunk = chunks[idx - 1]
        citations.append(
            {
                "id": f"c{idx}",
                "docId": chunk.doc_id,
                "docTitle": chunk.doc_id,  # _enrich_titles overwrites
                "page": chunk.page,
                "quote": _truncate(chunk.text, _QUOTE_PREVIEW_CHARS),
            }
        )
    return citations


def _build_segments(text: str) -> list[dict[str, Any]]:
    """Split text into citation-bearing segments.

    Rule of thumb: each segment carries the text since the last citation
    cluster plus the citations that follow. Adjacent markers like
    `[c1][c2]` attach to the same segment (the text before them).
    Trailing text without citations becomes a final uncited segment."""
    segments: list[dict[str, Any]] = []
    pos = 0
    for m in _CITATION_RE.finditer(text):
        between = text[pos : m.start()]
        cite_id = f"c{m.group(1)}"
        if between.strip():
            # New segment with text + this citation.
            segments.append({"text": between.strip(), "citationIds": [cite_id]})
        else:
            # Empty between — extend the previous segment's citation list.
            if segments:
                segments[-1] = {
                    "text": segments[-1]["text"],
                    "citationIds": [*segments[-1]["citationIds"], cite_id],
                }
        pos = m.end()
    trailing = text[pos:].strip()
    if trailing:
        segments.append({"text": trailing, "citationIds": []})
    return segments


def _truncate(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# Convenience re-export so a future LangGraph wrapper can construct
# StoredChunk → RetrievedChunk lists without re-importing here.
__all__: Iterable[str] = (
    "ResearchAgent",
    "_build_citations",
    "_build_segments",
    "_parse_segments_and_citations",
)
