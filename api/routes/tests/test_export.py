"""/export routes — bibliography (BibTeX/RIS) + report (PDF/DOCX). FR-EXP-01/02/08."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.export import router as export_router


class _Doc:
    def __init__(self, id_: str, title: str, uri: str) -> None:
        self.id = id_
        self.title = title
        self.source_uri = uri
        self.created_at = datetime(2026, 6, 22, tzinfo=UTC)


class _StubDocStore:
    async def list_documents(self):
        return [
            _Doc("doc_a", "GraphRAG & Retrieval", "https://x.org/a"),
            _Doc("doc_b", "Vector Search", "https://x.org/b"),
        ]


def _client(doc_store=None) -> TestClient:
    app = FastAPI()
    app.include_router(export_router)
    app.state.shared = {"doc_store": doc_store if doc_store is not None else _StubDocStore()}
    return TestClient(app)


def test_bibliography_bibtex():
    resp = _client().get("/export/bibliography?format=bibtex")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-bibtex")
    assert "@misc{" in resp.text
    assert "GraphRAG" in resp.text
    assert "attachment" in resp.headers["content-disposition"]


def test_bibliography_ris():
    resp = _client().get("/export/bibliography?format=ris")
    assert resp.status_code == 200
    assert "TY  - GEN" in resp.text


def test_bibliography_rejects_bad_format():
    assert _client().get("/export/bibliography?format=xml").status_code == 422


def test_report_pdf():
    resp = _client().get("/export/report?format=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")
    assert "arcana-report.pdf" in resp.headers["content-disposition"]


def test_report_docx():
    resp = _client().get("/export/report?format=docx")
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # zip magic
    assert "wordprocessingml" in resp.headers["content-type"]


def test_report_rejects_bad_format():
    assert _client().get("/export/report?format=txt").status_code == 422
