"""ComparatorAgent — cross-document comparison tests (FR-RET-05)."""

from __future__ import annotations

import json

from api.agents.base import AgentState
from api.agents.tier2.comparator import (
    ComparatorAgent,
    _parse_matrix_response,
    _strip_fences,
)
from api.llm.types import Completion, Usage
from api.retrieval.types import RetrievedChunk

# ---- Helpers ----------------------------------------------------------------


def _chunk(cid: str, doc_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(id=cid, doc_id=doc_id, text=text, page=1, score=0.9, source="vector")


class _StubLLM:
    def __init__(self, response_text: str = "", raise_exc: Exception | None = None):
        self._response = response_text
        self._raise = raise_exc

    async def complete(self, messages, *, system=None, max_tokens=None, budget=None, tools=None):
        if self._raise:
            raise self._raise
        return Completion(
            text=self._response,
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=50),
            model="stub",
            provider="stub",
        )


class _StubRetriever:
    def __init__(self, results: list[RetrievedChunk]):
        self._results = results

    async def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        return self._results[:top_k]


def _make_agent(llm_text: str, chunks: list[RetrievedChunk]) -> ComparatorAgent:
    r = _StubRetriever(chunks)
    return ComparatorAgent(
        llm_service=_StubLLM(response_text=llm_text),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )


_MATRIX_JSON = json.dumps({
    "dimensions": ["Methodology", "Key findings", "Limitations"],
    "rows": [
        {
            "docId": "doc1",
            "docTitle": "RAG paper",
            "cells": [
                {"text": "Dense retrieval", "citationId": "c1"},
                {"text": "Improves factuality", "citationId": None},
                {"text": "Latency cost", "citationId": None},
            ],
        },
        {
            "docId": "doc2",
            "docTitle": "RLHF paper",
            "cells": [
                {"text": "Human feedback loop", "citationId": "c2"},
                {"text": "Better alignment", "citationId": None},
                {"text": "Expensive annotation", "citationId": None},
            ],
        },
    ],
})

_PROSE_RESPONSE = (
    "RAG and RLHF differ fundamentally. [c1] "
    "RAG relies on retrieved documents, whereas RLHF [c2] uses human preference signals."
)


# ---- Multi-doc matrix tests (primary path, FR-RET-05) -----------------------


async def test_run_multi_doc_returns_literature_matrix():
    chunks = [
        _chunk("c1", "doc1", "RAG retrieval pipeline."),
        _chunk("c2", "doc2", "RLHF human feedback loop."),
    ]
    agent = _make_agent(_MATRIX_JSON, chunks)
    state = AgentState(query="compare RAG and RLHF")
    result = await agent.run("compare RAG and RLHF", state=state)

    assert result.status == "ok"
    assert result.payload.get("block_type") == "LiteratureMatrix"
    data = result.payload["data"]
    assert data["query"] == "compare RAG and RLHF"
    assert len(data["dimensions"]) == 3
    assert len(data["rows"]) == 2
    assert len(state.retrieved_ctx) == 2


async def test_run_multi_doc_matrix_default_dimensions_on_bad_json():
    """Malformed JSON → defensive fallback synthesises rows from chunks."""
    chunks = [
        _chunk("c1", "doc1", "text A"),
        _chunk("c2", "doc2", "text B"),
    ]
    agent = _make_agent("not valid json at all", chunks)
    state = AgentState(query="compare X and Y")
    result = await agent.run("compare X and Y", state=state)

    assert result.status == "ok"
    assert result.payload.get("block_type") == "LiteratureMatrix"
    data = result.payload["data"]
    assert data["dimensions"] == ["Approach", "Key findings", "Limitations"]
    assert len(data["rows"]) == 2  # one row synthesised per doc


async def test_run_multi_doc_matrix_json_in_fences():
    chunks = [_chunk("c1", "doc1", "A"), _chunk("c2", "doc2", "B")]
    fenced = f"```json\n{_MATRIX_JSON}\n```"
    agent = _make_agent(fenced, chunks)
    state = AgentState(query="compare")
    result = await agent.run("compare", state=state)
    assert result.payload.get("block_type") == "LiteratureMatrix"


async def test_run_multi_doc_matrix_fails_when_llm_raises():
    r = _StubRetriever([_chunk("c1", "d1", "t"), _chunk("c2", "d2", "u")])
    agent = ComparatorAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("err")),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )
    state = AgentState(query="compare")
    result = await agent.run("compare", state=state)
    assert result.status == "failed"


# ---- Single-doc prose fallback tests ----------------------------------------


async def test_run_single_doc_falls_back_to_cited_summary():
    chunks = [_chunk("c1", "doc1", "only one document here")]
    agent = _make_agent(_PROSE_RESPONSE, chunks)
    state = AgentState(query="explain RAG")
    result = await agent.run("explain RAG", state=state)

    assert result.status == "ok"
    assert "summary" in result.payload
    assert "block_type" not in result.payload


async def test_run_no_citations_when_no_markers_single_doc():
    chunks = [_chunk("c1", "d1", "text")]
    agent = _make_agent("A pure comparison with no citation markers.", chunks)
    state = AgentState(query="compare x and y")
    result = await agent.run("compare x and y", state=state)

    assert result.status == "ok"
    assert result.payload["citations"] == []
    assert len(result.payload["segments"]) == 1


async def test_run_partial_status_when_no_chunks():
    agent = _make_agent("any response", [])
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "partial"


async def test_run_prose_fails_when_llm_raises():
    r = _StubRetriever([_chunk("c1", "d1", "text")])
    agent = ComparatorAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("err")),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"


# ---- _parse_matrix_response unit tests -------------------------------------


def test_parse_matrix_full_json():
    chunks = [_chunk("c1", "doc1", "t"), _chunk("c2", "doc2", "u")]
    result = _parse_matrix_response(_MATRIX_JSON, chunks=chunks, query="compare")
    assert result["block_type"] == "LiteratureMatrix"
    data = result["data"]
    assert len(data["rows"]) == 2
    assert len(data["dimensions"]) == 3
    assert data["rows"][0]["docId"] == "doc1"
    assert len(data["rows"][0]["cells"]) == 3


def test_parse_matrix_strips_fences():
    fenced = f"```json\n{_MATRIX_JSON}\n```"
    stripped = _strip_fences(fenced)
    assert stripped == _MATRIX_JSON


def test_parse_matrix_pads_short_cells():
    short = json.dumps({
        "dimensions": ["A", "B", "C"],
        "rows": [{"docId": "d1", "docTitle": "D1", "cells": [{"text": "x", "citationId": None}]}],
    })
    chunks = [_chunk("c1", "d1", "t"), _chunk("c2", "d2", "u")]
    result = _parse_matrix_response(short, chunks=chunks, query="q")
    row = result["data"]["rows"][0]
    assert len(row["cells"]) == 3
    assert row["cells"][1]["text"] == "Not reported"


def test_parse_matrix_deduplicates_rows():
    dup = json.dumps({
        "dimensions": ["A"],
        "rows": [
            {"docId": "same", "docTitle": "T", "cells": [{"text": "first", "citationId": None}]},
            {"docId": "same", "docTitle": "T", "cells": [{"text": "dup", "citationId": None}]},
        ],
    })
    chunks = [_chunk("c1", "same", "t"), _chunk("c2", "other", "u")]
    result = _parse_matrix_response(dup, chunks=chunks, query="q")
    assert len(result["data"]["rows"]) == 1
