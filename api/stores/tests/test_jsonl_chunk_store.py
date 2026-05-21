"""JsonlChunkStore — upsert, dedupe-on-read, delete_by_doc, corrupt-line skip."""

from __future__ import annotations

import pytest

from api.stores.chunk_store import StoredChunk
from api.stores.jsonl_chunk_store import JsonlChunkStore


def _chunk(cid: str, doc_id: str, text: str, page: int = 1, offset: int = 0) -> StoredChunk:
    return StoredChunk(id=cid, doc_id=doc_id, text=text, page=page, char_offset=offset)


@pytest.fixture
def store(tmp_path):
    return JsonlChunkStore(root=tmp_path)


async def test_upsert_then_list(store):
    chunks = [_chunk("c1", "d1", "hello"), _chunk("c2", "d1", "world")]
    await store.upsert_many(chunks)
    out = await store.list_all()
    assert {c.id for c in out} == {"c1", "c2"}


async def test_upsert_then_get(store):
    await store.upsert_many([_chunk("c1", "d1", "hello")])
    got = await store.get("c1")
    assert got is not None and got.text == "hello"
    assert await store.get("missing") is None


async def test_upsert_replaces_by_id(store):
    """Two writes with the same id — list_all returns the newer one."""
    await store.upsert_many([_chunk("c1", "d1", "old")])
    await store.upsert_many([_chunk("c1", "d1", "new")])
    out = await store.list_all()
    assert len(out) == 1
    assert out[0].text == "new"


async def test_delete_by_doc(store):
    await store.upsert_many([
        _chunk("c1", "d1", "alpha"),
        _chunk("c2", "d1", "beta"),
        _chunk("c3", "d2", "gamma"),
    ])
    removed = await store.delete_by_doc("d1")
    assert removed == 2
    remaining = await store.list_all()
    assert {c.id for c in remaining} == {"c3"}


async def test_delete_missing_doc_returns_zero(store):
    await store.upsert_many([_chunk("c1", "d1", "x")])
    assert await store.delete_by_doc("does_not_exist") == 0


async def test_empty_upsert_is_noop(store):
    await store.upsert_many([])
    assert await store.list_all() == []


async def test_corrupt_lines_skipped(store, tmp_path):
    await store.upsert_many([_chunk("c1", "d1", "ok")])
    # Append a deliberately broken line.
    path = tmp_path / "chunks.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write("{this is not json\n")
        f.write('{"id": "c2", "doc_id": "d1", "text": "valid", "page": 1, "char_offset": 0}\n')
    out = await store.list_all()
    assert {c.id for c in out} == {"c1", "c2"}  # corrupt line dropped
