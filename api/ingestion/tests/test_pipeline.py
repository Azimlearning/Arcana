"""End-to-end ingest pipeline against stubbed stores + embedder.

Asserts status transitions, vector upsert shape, chunk attribution, and
the failure path (status flipped to 'failed' on any exception)."""

from __future__ import annotations

import pymupdf
import pytest

from api.core.errors import IngestFailed
from api.embeddings.types import EmbeddingProviderError
from api.ingestion.pipeline import ingest_pdf
from api.ingestion.stores_bundle import Stores
from api.stores.errors import GraphStoreError
from api.stores.filesystem_doc_store import FilesystemDocStore
from api.stores.jsonl_chunk_store import JsonlChunkStore
from api.stores.networkx_store import NetworkXGraphStore
from api.stores.vector_store import VectorHit, VectorItem, VectorStore

# ── Stub stores / embedder ─────────────────────────────────────────


class _MemoryVectorStore(VectorStore):
    dimension = 16

    def __init__(self) -> None:
        self.items: list[VectorItem] = []

    async def upsert(self, items):
        self.items.extend(items)

    async def query(self, vector, *, top_k=10, filter=None) -> list[VectorHit]:
        raise GraphStoreError("not used in ingestion tests")

    async def delete(self, ids):
        self.items = [i for i in self.items if i.id not in ids]

    async def aclose(self):
        return None


class _StubEmbedder:
    def __init__(self, *, dimension: int = 16, fail: bool = False) -> None:
        self.dimension = dimension
        self._fail = fail
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._fail:
            raise EmbeddingProviderError("stub", "boom")
        return [[float(i)] * self.dimension for i, _ in enumerate(texts)]


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def stores(tmp_path):
    return Stores(
        doc=FilesystemDocStore(root=tmp_path),
        vector=_MemoryVectorStore(),
        graph=NetworkXGraphStore(),
        chunks=JsonlChunkStore(root=tmp_path),
    )


def _build_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()


# ── Happy path ─────────────────────────────────────────────────────


async def test_ingest_pdf_end_to_end(stores):
    raw = _build_pdf("Arcana ingests this body into vectors. " * 20)
    embedder = _StubEmbedder()
    meta = await ingest_pdf(
        doc_id="doc_001",
        raw=raw,
        title="Test.pdf",
        source_uri="/tmp/Test.pdf",
        stores=stores,
        embedder=embedder,
    )
    assert meta.ingest_status == "ready"
    assert meta.id == "doc_001"
    assert isinstance(stores.vector, _MemoryVectorStore)
    assert len(stores.vector.items) >= 1
    # Every upserted item carries the metadata we'll need for citations.
    for item in stores.vector.items:
        assert item.metadata["doc_id"] == "doc_001"
        assert "text" in item.metadata
        assert "page" in item.metadata
        assert len(item.vector) == embedder.dimension


async def test_ingested_doc_persisted_and_listable(stores):
    raw = _build_pdf("Body for listing test.")
    embedder = _StubEmbedder()
    await ingest_pdf(
        doc_id="doc_002",
        raw=raw,
        title="L.pdf",
        source_uri="/tmp/L.pdf",
        stores=stores,
        embedder=embedder,
    )
    docs = await stores.doc.list_documents()
    assert {d.id for d in docs} == {"doc_002"}
    assert docs[0].ingest_status == "ready"
    # Bytes still retrievable end-to-end.
    assert await stores.doc.get_bytes("doc_002") == raw


# ── Failure paths ──────────────────────────────────────────────────


async def test_empty_pdf_marks_failed(stores):
    embedder = _StubEmbedder()
    with pytest.raises(IngestFailed):
        await ingest_pdf(
            doc_id="doc_bad",
            raw=b"not a pdf",
            title="bad.pdf",
            source_uri="bad",
            stores=stores,
            embedder=embedder,
        )
    meta = await stores.doc.get_metadata("doc_bad")
    assert meta.ingest_status == "failed"


async def test_scanned_pdf_marks_failed(stores):
    """A PDF with no text content should fail loudly until OCR (P1)."""
    doc = pymupdf.open()
    doc.new_page()
    raw = doc.tobytes()
    doc.close()
    embedder = _StubEmbedder()
    with pytest.raises(IngestFailed):
        await ingest_pdf(
            doc_id="doc_scanned",
            raw=raw,
            title="scan.pdf",
            source_uri="scan",
            stores=stores,
            embedder=embedder,
        )
    meta = await stores.doc.get_metadata("doc_scanned")
    assert meta.ingest_status == "failed"


async def test_embedder_failure_marks_failed(stores):
    raw = _build_pdf("Body that would embed fine but the stub explodes.")
    embedder = _StubEmbedder(fail=True)
    with pytest.raises(IngestFailed):
        await ingest_pdf(
            doc_id="doc_emb_fail",
            raw=raw,
            title="x.pdf",
            source_uri="x",
            stores=stores,
            embedder=embedder,
        )
    meta = await stores.doc.get_metadata("doc_emb_fail")
    assert meta.ingest_status == "failed"


async def test_chunk_ids_idempotent_on_reingest(stores):
    raw = _build_pdf("Determinism check. " * 10)
    embedder = _StubEmbedder()
    await ingest_pdf(doc_id="doc_idem", raw=raw, title="t", source_uri="s",
                     stores=stores, embedder=embedder)
    first_ids = sorted(item.id for item in stores.vector.items)

    # Wipe vectors only; rerun ingestion on the same bytes.
    stores.vector.items.clear()
    await ingest_pdf(doc_id="doc_idem", raw=raw, title="t", source_uri="s",
                     stores=stores, embedder=embedder)
    second_ids = sorted(item.id for item in stores.vector.items)
    assert first_ids == second_ids
