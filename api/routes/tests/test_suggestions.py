"""GET /suggestions — seed question generation from corpus."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.suggestions import _cache
from api.routes.suggestions import router as suggestions_router
from api.stores.doc_store import DocMetadata


def _doc(doc_id: str = "doc1", title: str = "Paper on RAG") -> DocMetadata:
    return DocMetadata(
        id=doc_id,
        title=title,
        source_uri=f"upload/{doc_id}.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        ingest_status="ready",
        created_at=datetime.now(UTC),
    )


def _make_app(*, docs=None, llm_response: str = '["Q1", "Q2", "Q3"]'):
    app = FastAPI()
    app.include_router(suggestions_router)

    doc_store = AsyncMock()
    doc_store.list_documents.return_value = docs if docs is not None else []

    llm = AsyncMock()
    llm.complete.return_value = llm_response

    app.state.shared = {"doc_store": doc_store, "llm": llm}
    return app, doc_store, llm


@pytest.fixture(autouse=True)
def _reset_cache():
    _cache.update({"suggestions": [], "ts": 0.0, "doc_count": 0})
    yield
    _cache.update({"suggestions": [], "ts": 0.0, "doc_count": 0})


def test_no_docs_returns_empty():
    app, _, _ = _make_app(docs=[])
    client = TestClient(app, raise_server_exceptions=True)
    r = client.get("/suggestions")
    assert r.status_code == 200
    assert r.json() == {"suggestions": []}


def test_with_docs_returns_three_questions():
    app, _, llm = _make_app(
        docs=[_doc()],
        llm_response='["What is RAG?", "How does RAG compare to BM25?", "What are RAG limitations?"]',
    )
    client = TestClient(app, raise_server_exceptions=True)
    r = client.get("/suggestions")
    assert r.status_code == 200
    data = r.json()
    assert len(data["suggestions"]) == 3
    assert data["suggestions"][0] == "What is RAG?"
    llm.complete.assert_called_once()


def test_no_shared_state_returns_empty():
    app = FastAPI()
    app.include_router(suggestions_router)
    client = TestClient(app, raise_server_exceptions=True)
    r = client.get("/suggestions")
    assert r.status_code == 200
    assert r.json() == {"suggestions": []}


def test_llm_failure_returns_empty():
    app, _, llm = _make_app(docs=[_doc()])
    llm.complete.side_effect = RuntimeError("LLM down")
    client = TestClient(app, raise_server_exceptions=True)
    r = client.get("/suggestions")
    assert r.status_code == 200
    assert r.json() == {"suggestions": []}


def test_malformed_llm_response_returns_empty():
    app, _, _ = _make_app(docs=[_doc()], llm_response="I can't generate that right now.")
    client = TestClient(app, raise_server_exceptions=True)
    r = client.get("/suggestions")
    assert r.status_code == 200
    assert r.json() == {"suggestions": []}


def test_llm_called_once_when_cached():
    app, _, llm = _make_app(docs=[_doc()])
    client = TestClient(app, raise_server_exceptions=True)
    client.get("/suggestions")
    client.get("/suggestions")
    assert llm.complete.call_count == 1


def test_multiple_docs_passed_to_llm():
    docs = [_doc(f"doc{i}", f"Paper {i}") for i in range(5)]
    app, _, llm = _make_app(docs=docs)
    client = TestClient(app, raise_server_exceptions=True)
    client.get("/suggestions")
    call_args = llm.complete.call_args
    prompt = call_args[0][0][0].content
    assert "Paper 0" in prompt
    assert "Paper 4" in prompt
