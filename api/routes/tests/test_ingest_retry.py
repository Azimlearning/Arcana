"""POST /ingest/retry/{doc_id} — pipeline retry for failed docs (FR-ING-08)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.auth import CurrentUser, get_current_user
from api.routes.ingest import IngestContext, get_ingest_context
from api.routes.ingest import router as ingest_router
from api.stores.doc_store import DocMetadata
from api.stores.errors import DocNotFound


def _meta(status: str = "failed") -> DocMetadata:
    return DocMetadata(
        id="test_doc",
        title="Test Doc",
        source_uri="upload/test.pdf",
        content_type="application/pdf",
        size_bytes=500,
        ingest_status=status,
        created_at=datetime.now(UTC),
    )


def _make_app(
    *,
    doc_meta=None,
    doc_bytes: bytes = b"FAKEPDF",
    chunk_count: int = 5,
    raise_meta=None,
    raise_bytes=None,
):
    app = FastAPI()
    app.include_router(ingest_router)

    doc_store = AsyncMock()
    if raise_meta is not None:
        doc_store.get_metadata.side_effect = raise_meta
    else:
        doc_store.get_metadata.return_value = doc_meta or _meta()

    if raise_bytes is not None:
        doc_store.get_bytes.side_effect = raise_bytes
    else:
        doc_store.get_bytes.return_value = doc_bytes

    chunk_store = AsyncMock()
    chunk_store.list_all.return_value = [
        AsyncMock(doc_id="test_doc") for _ in range(chunk_count)
    ]

    stores = AsyncMock()
    stores.doc = doc_store
    stores.chunks = chunk_store

    ctx = IngestContext(
        stores=stores,
        embedder=AsyncMock(),
        llm=AsyncMock(),
        graph_registry=None,
    )

    app.dependency_overrides[get_ingest_context] = lambda: ctx
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(uid="anon")

    return app


def test_retry_doc_not_found():
    app = _make_app(raise_meta=DocNotFound("not found"))
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/ingest/retry/test_doc")
    assert r.status_code == 404


def test_retry_doc_already_ready():
    app = _make_app(doc_meta=_meta("ready"))
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/ingest/retry/test_doc")
    assert r.status_code == 409


def test_retry_doc_pending_allowed():
    app = _make_app(doc_meta=_meta("pending"))
    client = TestClient(app, raise_server_exceptions=True)
    with patch("api.routes.ingest.ingest_pdf", new_callable=AsyncMock):
        r = client.post("/ingest/retry/test_doc")
    assert r.status_code == 200


def test_retry_no_stored_bytes():
    app = _make_app(raise_bytes=DocNotFound("no bytes"))
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/ingest/retry/test_doc")
    assert r.status_code == 404


def test_retry_happy_path():
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=True)
    with patch("api.routes.ingest.ingest_pdf", new_callable=AsyncMock) as mock_ingest:
        r = client.post("/ingest/retry/test_doc")
    assert r.status_code == 200
    data = r.json()
    assert data["docId"] == "test_doc"
    assert data["status"] == "ready"
    assert data["chunkCount"] == 5
    mock_ingest.assert_called_once()


def test_retry_pipeline_failure_returns_500():
    app = _make_app()
    client = TestClient(app, raise_server_exceptions=False)
    with patch("api.routes.ingest.ingest_pdf", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.side_effect = RuntimeError("pipeline failed")
        r = client.post("/ingest/retry/test_doc")
    assert r.status_code == 500
