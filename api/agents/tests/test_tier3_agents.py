"""Slice 19 -- Tier-3 agent unit tests: CitationAgent, VisualAgent, DocumentAgent."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.agents.base import AgentState
from api.agents.tier3.citation import CitationAgent, _format_citation, _infer_year
from api.agents.tier3.document import DocumentAgent
from api.agents.tier3.visual import VisualAgent
from api.retrieval.types import RetrievedChunk
from api.stores.doc_store import DocMetadata, DocStore, IngestStatus

# ─── helpers ──────────────────────────────────────────────────────────────────


def _state() -> AgentState:
    return AgentState(query="test", notebook_id="nb1", user_id="user1")


def _meta(
    doc_id: str = "d1",
    title: str = "Attention Is All You Need 2017",
    source_uri: str = "https://arxiv.org/abs/1706.03762",
    extra: dict | None = None,
) -> DocMetadata:
    return DocMetadata(
        id=doc_id, title=title, source_uri=source_uri,
        content_type="application/pdf", size_bytes=0,
        ingest_status="ready", created_at=datetime(2017, 1, 1),
        extra=extra or {},
    )


def _chunk(doc_id: str = "d1", text: str = "Some text about attention.") -> RetrievedChunk:
    return RetrievedChunk(id="c1", doc_id=doc_id, text=text, page=1, score=0.9, source="vector")


def _retrievers(chunks: list[RetrievedChunk] | None = None):
    v = MagicMock()
    v.retrieve = AsyncMock(return_value=chunks or [])
    b = MagicMock()
    b.retrieve = AsyncMock(return_value=[])
    g = MagicMock()
    g.retrieve = AsyncMock(return_value=[])
    return v, b, g


class _StubDocStore(DocStore):
    def __init__(self, docs: list[DocMetadata]) -> None:
        self._docs = docs

    async def put(
        self, doc_id: str, raw: bytes, *, content_type: str,
        title: str, source_uri: str, ingest_status: IngestStatus = "pending",
    ) -> DocMetadata:
        return _meta(doc_id, title, source_uri)

    async def get_bytes(self, doc_id: str) -> bytes:
        raise NotImplementedError

    async def get_metadata(self, doc_id: str) -> DocMetadata:
        return next(d for d in self._docs if d.id == doc_id)

    async def update_status(
        self, doc_id: str, status: IngestStatus, *, extra_update: dict | None = None
    ) -> DocMetadata:
        return next(d for d in self._docs if d.id == doc_id)

    async def list_documents(self) -> list[DocMetadata]:
        return list(self._docs)

    async def aclose(self) -> None:
        pass


# ─── _infer_year ──────────────────────────────────────────────────────────────


def test_infer_year_from_title():
    assert _infer_year(_meta(title="BERT Pre-training 2019")) == 2019


def test_infer_year_from_uri():
    assert _infer_year(_meta(title="Paper", source_uri="https://example.com/2021/paper")) == 2021


def test_infer_year_none():
    assert _infer_year(_meta(title="No Year Paper", source_uri="https://example.com/p")) is None


# ─── _format_citation ─────────────────────────────────────────────────────────


def test_format_apa():
    meta = _meta(extra={"authors": "Vaswani, A., Shazeer, N."})
    formatted, bibtex = _format_citation(meta, "apa")
    assert "Vaswani" in formatted
    assert "2017" in formatted
    assert "@misc" in bibtex


def test_format_mla():
    meta = _meta(extra={"authors": "LeCun, Yann"})
    formatted, _ = _format_citation(meta, "mla")
    assert "LeCun" in formatted


def test_format_ieee():
    meta = _meta(extra={"authors": "Goodfellow, Ian"})
    formatted, _ = _format_citation(meta, "ieee")
    assert "Goodfellow" in formatted


def test_format_unknown_authors():
    formatted, bibtex = _format_citation(_meta(title="Paper 2020"), "apa")
    assert "Unknown Author" in formatted
    assert "@misc" in bibtex


# ─── CitationAgent ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_citation_preview_happy():
    agent = CitationAgent(doc_store=_StubDocStore([_meta()]))
    r = await agent.run("format the citation", _state())
    assert r.status == "ok"
    assert r.payload["block_type"] == "CitationPreview"
    assert r.payload["data"]["docId"] == "d1"
    assert r.payload["data"]["style"] == "apa"
    assert "2017" in r.payload["data"]["formatted"]


@pytest.mark.asyncio
async def test_citation_preview_no_docs():
    agent = CitationAgent(doc_store=_StubDocStore([]))
    r = await agent.run("format the citation", _state())
    assert r.status == "partial"
    assert r.payload["block_type"] == "CitationPreview"


@pytest.mark.asyncio
async def test_bibliography_export():
    docs = [_meta("d1", "Paper One 2020"), _meta("d2", "Paper Two 2021")]
    agent = CitationAgent(doc_store=_StubDocStore(docs))
    r = await agent.run("generate bibliography", _state())
    assert r.status == "ok"
    assert r.payload["block_type"] == "BibliographyExport"
    assert len(r.payload["data"]["entries"]) == 2
    assert "@misc" in r.payload["data"]["bibtexAll"]


@pytest.mark.asyncio
async def test_bibliography_bibtex_keyword():
    agent = CitationAgent(doc_store=_StubDocStore([_meta()]))
    r = await agent.run("export bibtex", _state())
    assert r.payload["block_type"] == "BibliographyExport"


@pytest.mark.asyncio
async def test_citation_style_mla():
    agent = CitationAgent(doc_store=_StubDocStore([_meta(extra={"authors": "Brown, T."})]))
    r = await agent.run("give mla citation", _state())
    assert r.payload["data"]["style"] == "mla"


@pytest.mark.asyncio
async def test_citation_store_failure():
    class _FailStore(_StubDocStore):
        async def list_documents(self) -> list[DocMetadata]:
            raise RuntimeError("db error")

    agent = CitationAgent(doc_store=_FailStore([]))
    r = await agent.run("cite all", _state())
    assert r.status == "failed"
    assert "db error" in (r.error or "")


# ─── VisualAgent ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_visual_concept_map():
    v, b, g = _retrievers([_chunk()])
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=json.dumps({
        "rootConcept": "Transformer",
        "nodes": [{"id": "n0", "label": "Transformer", "description": "model", "level": 0}],
        "links": [],
    }))
    agent = VisualAgent(llm_service=llm, vector_retriever=v, bm25_retriever=b, graph_retriever=g)
    r = await agent.run("concept map of transformers", _state())
    assert r.status == "ok"
    assert r.payload["block_type"] == "ConceptMap"
    assert r.payload["data"]["rootConcept"] == "Transformer"
    assert len(r.payload["data"]["nodes"]) == 1


@pytest.mark.asyncio
async def test_visual_comparison_chart():
    v, b, g = _retrievers([_chunk()])
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=json.dumps({
        "title": "Model Comparison", "chartType": "bar",
        "labels": ["accuracy"], "series": [{"name": "A", "values": [4]}], "unit": None,
    }))
    agent = VisualAgent(llm_service=llm, vector_retriever=v, bm25_retriever=b, graph_retriever=g)
    r = await agent.run("comparison chart for models", _state())
    assert r.status == "ok"
    assert r.payload["block_type"] == "ComparisonChart"
    assert r.payload["data"]["title"] == "Model Comparison"


@pytest.mark.asyncio
async def test_visual_fallback_concept_on_generic_visual():
    v, b, g = _retrievers([_chunk()])
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=json.dumps({
        "rootConcept": "Attention", "nodes": [], "links": [],
    }))
    agent = VisualAgent(llm_service=llm, vector_retriever=v, bm25_retriever=b, graph_retriever=g)
    r = await agent.run("visualize the attention mechanism", _state())
    assert r.payload["block_type"] == "ConceptMap"


@pytest.mark.asyncio
async def test_visual_no_chunks():
    v, b, g = _retrievers([])
    llm = MagicMock()
    agent = VisualAgent(llm_service=llm, vector_retriever=v, bm25_retriever=b, graph_retriever=g)
    r = await agent.run("concept map", _state())
    assert r.status == "failed"


# ─── DocumentAgent ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_document_agent_happy():
    v, b, g = _retrievers([_chunk(text="This paper proposes a new attention mechanism.")])
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=json.dumps({
        "topic": "My Paper",
        "notes": [{"cue": "Main contribution", "content": "New attention.", "citationIds": ["c1"]}],
        "summary": "Key summary.",
    }))
    agent = DocumentAgent(llm_service=llm, vector_retriever=v, bm25_retriever=b, graph_retriever=g)
    r = await agent.run("summarize this document", _state())
    assert r.status == "ok"
    assert r.payload["block_type"] == "CornellNotes"
    assert r.payload["data"]["topic"] == "My Paper"
    assert len(r.payload["data"]["notes"]) == 1
    assert len(r.payload["data"]["citations"]) == 1


@pytest.mark.asyncio
async def test_document_agent_no_chunks():
    v, b, g = _retrievers([])
    llm = MagicMock()
    agent = DocumentAgent(llm_service=llm, vector_retriever=v, bm25_retriever=b, graph_retriever=g)
    r = await agent.run("summarize document", _state())
    assert r.status == "failed"


@pytest.mark.asyncio
async def test_document_agent_llm_failure():
    v, b, g = _retrievers([_chunk()])
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=RuntimeError("llm timeout"))
    agent = DocumentAgent(llm_service=llm, vector_retriever=v, bm25_retriever=b, graph_retriever=g)
    r = await agent.run("summarize document", _state())
    assert r.status == "failed"
    assert "llm timeout" in (r.error or "")
