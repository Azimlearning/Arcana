"""VisualAgent - Tier 3. Concept map and comparison chart generation.

Transforms retrieved context into visual representations using the LLM.

Intent "visual" / "concept" -> ConceptMap (studio panel)
Intent "chart" / "compare visually" -> ComparisonChart (chat panel)
Default -> ConceptMap
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

_CONCEPT_MAP_SYSTEM = (
    "You are an academic knowledge visualizer. Given research excerpts, extract a concept map.\n\n"
    "Respond ONLY with valid JSON (no prose, no markdown):\n"
    "{\n"
    '  "rootConcept": "central concept string",\n'
    '  "nodes": [\n'
    '    {"id": "n1", "label": "concept", "description": "one sentence", "level": 0}\n'
    "  ],\n"
    '  "links": [\n'
    '    {"source": "n1", "target": "n2", "label": "influences"}\n'
    "  ]\n"
    "}\n\n"
    "Rules: 6-12 nodes. Root is level 0, direct relations level 1, secondary level 2."
)

_CHART_SYSTEM = (
    "You are an academic data visualizer. Given research on multiple papers or topics, "
    "extract comparison data.\n\n"
    "Respond ONLY with valid JSON (no prose, no markdown):\n"
    "{\n"
    '  "title": "Comparison title",\n'
    '  "chartType": "bar",\n'
    '  "labels": ["dimension1", "dimension2"],\n'
    '  "series": [\n'
    '    {"name": "Paper A", "values": [3, 4]}\n'
    "  ],\n"
    '  "unit": null\n'
    "}\n\n"
    "Rules: max 4 labels, max 5 series, numeric values 1-5 scale, chartType 'bar' or 'radar'."
)

_CHART_KEYWORDS = frozenset({
    "chart", "bar chart", "radar chart", "scatter",
    "compare visually", "comparison chart", "visual comparison",
})
_CONCEPT_KEYWORDS = frozenset({
    "concept map", "concept", "diagram", "visualize", "mind map", "visual",
})


def _parse_json(raw: str, default: dict) -> dict:
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("visual_agent.json_parse_failed", raw_len=len(raw))
        return default


def _citations(chunks) -> list[dict]:
    seen: set[str] = set()
    out = []
    for i, c in enumerate(chunks[:6]):
        if c.doc_id not in seen:
            seen.add(c.doc_id)
            out.append({
                "id": f"c{i + 1}",
                "docId": c.doc_id,
                "docTitle": getattr(c, "doc_title", None) or c.doc_id,
                "page": None,
                "quote": c.text[:120],
            })
    return out


class VisualAgent(BaseAgent):
    """Tier-3 output agent. Generates concept maps and comparison charts."""

    name = "visual_agent"
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
        q = query.lower()
        if any(kw in q for kw in _CHART_KEYWORDS):
            return await self._comparison_chart(query, state)
        return await self._concept_map(query, state)

    # -- private -----------------------------------------------------------

    async def _concept_map(self, query: str, state: AgentState) -> AgentResult:
        chunks = await hybrid_retrieve(
            query, top_k=8,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            return AgentResult(
                agent_name=self.name, payload={}, status="failed",
                error="No context retrieved for concept map",
            )

        ctx = "\n\n".join(c.text[:400] for c in chunks[:6])
        try:
            raw = await self._llm.complete(
                [Message(role="user", content=f"Concept map for: {query}\n\n{ctx}")],
                system=_CONCEPT_MAP_SYSTEM,
            )
        except Exception as exc:
            return AgentResult(agent_name=self.name, payload={}, status="failed", error=str(exc))

        data = _parse_json(raw, {"rootConcept": query, "nodes": [], "links": []})
        if not data.get("nodes"):
            data["nodes"] = [{"id": "n0", "label": query, "description": "", "level": 0}]

        return AgentResult(
            agent_name=self.name,
            payload={"block_type": "ConceptMap", "data": {
                "rootConcept": data.get("rootConcept", query),
                "nodes": data.get("nodes", []),
                "links": data.get("links", []),
                "citations": _citations(chunks),
            }},
            status="ok",
        )

    async def _comparison_chart(self, query: str, state: AgentState) -> AgentResult:
        chunks = await hybrid_retrieve(
            query, top_k=12,
            vector_retriever=self._vector,
            bm25_retriever=self._bm25,
            graph_retriever=self._graph,
        )
        state.retrieved_ctx.extend(chunks)

        if not chunks:
            return AgentResult(
                agent_name=self.name, payload={}, status="failed",
                error="No context retrieved for chart",
            )

        ctx = "\n\n".join(c.text[:400] for c in chunks[:8])
        try:
            raw = await self._llm.complete(
                [Message(role="user", content=f"Comparison chart for: {query}\n\n{ctx}")],
                system=_CHART_SYSTEM,
            )
        except Exception as exc:
            return AgentResult(agent_name=self.name, payload={}, status="failed", error=str(exc))

        data = _parse_json(raw, {"title": query, "chartType": "bar", "labels": [], "series": []})

        return AgentResult(
            agent_name=self.name,
            payload={"block_type": "ComparisonChart", "data": {
                "title": data.get("title", query),
                "chartType": data.get("chartType", "bar"),
                "labels": data.get("labels", []),
                "series": data.get("series", []),
                "unit": data.get("unit"),
                "citations": _citations(chunks),
            }},
            status="ok",
        )
