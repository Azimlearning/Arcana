"""LiteratureAgent — papers x dimensions matrix tests."""

from __future__ import annotations

from api.agents.base import AgentState
from api.agents.tier2.literature import (
    LiteratureAgent,
    _parse_literature_response,
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


def _make_agent(llm_text: str, chunks: list[RetrievedChunk]) -> LiteratureAgent:
    r = _StubRetriever(chunks)
    return LiteratureAgent(
        llm_service=_StubLLM(response_text=llm_text),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )


_GOOD_RESPONSE = """\
{
  "dimensions": ["Methodology", "Dataset", "Key result"],
  "rows": [
    {
      "docId": "doc1",
      "docTitle": "RAG Paper",
      "cells": [
        {"text": "Dense retrieval", "citationId": "c1"},
        {"text": "NQ benchmark", "citationId": null},
        {"text": "SOTA on OpenQA", "citationId": null}
      ]
    }
  ]
}
"""


# ---- Unit tests: parser -----------------------------------------------------


def test_strip_fences():
    raw = "```json\n{\"a\": 1}\n```"
    assert _strip_fences(raw) == '{"a": 1}'


def test_parse_happy_path():
    chunks = [_chunk("c1", "doc1", "Dense retrieval over NQ.")]
    result = _parse_literature_response(_GOOD_RESPONSE, chunks=chunks, query="RAG methods")
    assert result["block_type"] == "LiteratureMatrix"
    data = result["data"]
    assert data["dimensions"] == ["Methodology", "Dataset", "Key result"]
    assert len(data["rows"]) == 1
    assert data["rows"][0]["docId"] == "doc1"
    assert len(data["rows"][0]["cells"]) == 3


def test_parse_broken_json_returns_defaults():
    chunks = [_chunk("c1", "doc1", "text")]
    result = _parse_literature_response("not json", chunks=chunks, query="q")
    assert result["block_type"] == "LiteratureMatrix"
    assert result["data"]["dimensions"] == ["Methodology", "Key finding", "Limitations"]


def test_parse_pads_missing_cells():
    raw = """\
{
  "dimensions": ["A", "B", "C"],
  "rows": [{"docId": "d1", "docTitle": "T", "cells": [{"text": "x", "citationId": null}]}]
}"""
    chunks = [_chunk("c1", "d1", "text")]
    result = _parse_literature_response(raw, chunks=chunks, query="q")
    cells = result["data"]["rows"][0]["cells"]
    assert len(cells) == 3
    assert cells[1]["text"] == "Not reported"


def test_parse_deduplicates_doc_ids():
    raw = """\
{
  "dimensions": ["A"],
  "rows": [
    {"docId": "d1", "docTitle": "T1", "cells": [{"text": "x", "citationId": null}]},
    {"docId": "d1", "docTitle": "T1 dup", "cells": [{"text": "y", "citationId": null}]}
  ]
}"""
    chunks = [_chunk("c1", "d1", "text")]
    result = _parse_literature_response(raw, chunks=chunks, query="q")
    assert len(result["data"]["rows"]) == 1


# ---- Integration tests: agent.run -------------------------------------------


async def test_run_returns_literature_matrix():
    chunks = [_chunk("c1", "doc1", "RAG retrieval technique.")]
    agent = _make_agent(_GOOD_RESPONSE, chunks)
    state = AgentState(query="compare RAG methods")
    result = await agent.run("compare RAG methods", state=state)

    assert result.status == "ok"
    assert result.payload["block_type"] == "LiteratureMatrix"
    assert len(state.retrieved_ctx) == 1


async def test_run_fails_when_no_chunks():
    agent = _make_agent(_GOOD_RESPONSE, [])
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"


async def test_run_fails_when_llm_raises():
    r = _StubRetriever([_chunk("c1", "d1", "text")])
    agent = LiteratureAgent(
        llm_service=_StubLLM(raise_exc=RuntimeError("err")),  # type: ignore[arg-type]
        vector_retriever=r,
        bm25_retriever=r,
        graph_retriever=r,
    )
    state = AgentState(query="q")
    result = await agent.run("q", state=state)
    assert result.status == "failed"
    assert "LLM call failed" in (result.error or "")
