"""FilesystemDocStore — put/get bytes, metadata roundtrip, listing,
status updates, path-traversal safety."""

from __future__ import annotations

import pytest

from api.stores.doc_store import DocMetadata
from api.stores.errors import DocNotFound, DocStoreError
from api.stores.filesystem_doc_store import FilesystemDocStore


@pytest.fixture
def store(tmp_path):
    return FilesystemDocStore(root=tmp_path)


async def test_put_and_get_roundtrip(store):
    raw = b"This is a fake PDF body."
    meta = await store.put(
        "doc_001",
        raw,
        content_type="application/pdf",
        title="GraphRAG.pdf",
        source_uri="/tmp/GraphRAG.pdf",
    )
    assert meta.id == "doc_001"
    assert meta.size_bytes == len(raw)
    assert meta.ingest_status == "pending"
    assert meta.content_type == "application/pdf"
    assert meta.title == "GraphRAG.pdf"

    bytes_back = await store.get_bytes("doc_001")
    meta_back = await store.get_metadata("doc_001")
    assert bytes_back == raw
    assert isinstance(meta_back, DocMetadata)
    assert meta_back.title == "GraphRAG.pdf"
    assert meta_back.size_bytes == len(raw)


async def test_update_status_persists(store):
    await store.put(
        "doc_001", b"x", content_type="text/plain", title="t", source_uri="s",
    )
    updated = await store.update_status("doc_001", "ready")
    assert updated.ingest_status == "ready"
    fetched = await store.get_metadata("doc_001")
    assert fetched.ingest_status == "ready"


async def test_get_missing_raises_doc_not_found(store):
    with pytest.raises(DocNotFound):
        await store.get_bytes("nope")
    with pytest.raises(DocNotFound):
        await store.get_metadata("nope")
    with pytest.raises(DocNotFound):
        await store.update_status("nope", "ready")


async def test_list_documents_returns_all(store):
    await store.put("doc_a", b"a", content_type="text/plain", title="A", source_uri="s")
    await store.put("doc_b", b"bb", content_type="text/plain", title="B", source_uri="s")
    docs = await store.list_documents()
    assert {d.id for d in docs} == {"doc_a", "doc_b"}


async def test_list_documents_skips_corrupt_sidecar(store, tmp_path):
    await store.put("doc_a", b"a", content_type="text/plain", title="A", source_uri="s")
    # Hand-write a corrupt sidecar — listing should skip rather than crash.
    (tmp_path / "docs" / "doc_corrupt.json").write_text("{not-json", encoding="utf-8")
    docs = await store.list_documents()
    assert {d.id for d in docs} == {"doc_a"}


async def test_corrupt_metadata_on_direct_get_raises_clearly(store, tmp_path):
    await store.put("doc_a", b"a", content_type="text/plain", title="A", source_uri="s")
    (tmp_path / "docs" / "doc_a.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(DocStoreError):
        await store.get_metadata("doc_a")


@pytest.mark.parametrize("bad_id", [
    # path traversal
    "../escape",
    "subdir/file",
    "back\\slash",
    "",
    ".",
    "..",
    ".hidden",
    "null\x00byte",
    # Windows pathology
    "CON",
    "PRN.bin",
    "C:foo",
    "trailing.",
    "trailing ",
    # NTFS-reserved
    "name:colon",
    "name|pipe",
    "name?question",
    "name*star",
    "name<lt",
    "name>gt",
    "name\"quote",
    # unicode RTL override
    "name‮evil",
    # too long
    "x" * 129,
])
async def test_invalid_doc_id_rejected(store, bad_id):
    with pytest.raises(DocStoreError):
        await store.put(bad_id, b"x", content_type="text/plain", title="t", source_uri="s")


@pytest.mark.parametrize("good_id", [
    "doc_001",
    "DOC-A1",
    "x",
    "x" * 128,
    "1234567890",
    "snake_case-and-kebab",
])
async def test_valid_doc_ids_accepted(store, good_id):
    meta = await store.put(good_id, b"x", content_type="text/plain", title="t", source_uri="s")
    assert meta.id == good_id
