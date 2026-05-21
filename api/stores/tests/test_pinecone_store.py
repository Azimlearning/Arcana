"""PineconeVectorStore — REST behaviour via respx.

We test request shape (URL, headers, body) and response parsing without
touching the real network.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from api.stores.errors import VectorStoreError
from api.stores.pinecone_store import PINECONE_CONTROL_URL, PineconeVectorStore
from api.stores.vector_store import VectorItem


def _describe_response(host: str = "test-host.svc.test.pinecone.io") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "name": "arcana",
            "dimension": 3072,
            "metric": "cosine",
            "host": host,
            "status": {"ready": True, "state": "Ready"},
        },
    )


async def _store(host: str | None = None) -> PineconeVectorStore:
    return PineconeVectorStore(api_key="pcsk-test", index_name="arcana", host=host)


# ── Host resolution ───────────────────────────────────────────────
@respx.mock
async def test_describe_resolves_host_lazily():
    describe = respx.get(f"{PINECONE_CONTROL_URL}/indexes/arcana").mock(
        return_value=_describe_response()
    )
    upsert = respx.post("https://test-host.svc.test.pinecone.io/vectors/upsert").mock(
        return_value=httpx.Response(200, json={"upsertedCount": 1})
    )
    store = await _store()
    try:
        await store.upsert([VectorItem(id="v1", vector=[0.1] * 3072)])
    finally:
        await store.aclose()
    assert describe.call_count == 1
    assert upsert.called
    headers = upsert.calls.last.request.headers
    assert headers["Api-Key"] == "pcsk-test"


@respx.mock
async def test_host_resolution_cached_across_calls():
    describe = respx.get(f"{PINECONE_CONTROL_URL}/indexes/arcana").mock(
        return_value=_describe_response()
    )
    respx.post("https://test-host.svc.test.pinecone.io/vectors/upsert").mock(
        return_value=httpx.Response(200, json={"upsertedCount": 1})
    )
    respx.post("https://test-host.svc.test.pinecone.io/query").mock(
        return_value=httpx.Response(200, json={"matches": []})
    )
    store = await _store()
    try:
        await store.upsert([VectorItem(id="v1", vector=[0.1] * 3072)])
        await store.query([0.2] * 3072)
    finally:
        await store.aclose()
    assert describe.call_count == 1  # described once, reused for both data ops


@respx.mock
async def test_explicit_host_skips_describe():
    # No describe route registered — if the code tries to call it, respx raises.
    upsert = respx.post("https://explicit-host.pinecone.io/vectors/upsert").mock(
        return_value=httpx.Response(200, json={"upsertedCount": 1})
    )
    store = await _store(host="explicit-host.pinecone.io")
    try:
        await store.upsert([VectorItem(id="v1", vector=[0.1] * 3072)])
    finally:
        await store.aclose()
    assert upsert.called


@respx.mock
async def test_describe_404_raises_clear_error():
    respx.get(f"{PINECONE_CONTROL_URL}/indexes/arcana").mock(
        return_value=httpx.Response(404, text="index not found")
    )
    store = await _store()
    try:
        with pytest.raises(VectorStoreError) as exc:
            await store.upsert([VectorItem(id="v1", vector=[0.1] * 3072)])
    finally:
        await store.aclose()
    assert "describe failed HTTP 404" in str(exc.value)


# ── Upsert / query / delete ───────────────────────────────────────
@respx.mock
async def test_upsert_request_body():
    respx.get(f"{PINECONE_CONTROL_URL}/indexes/arcana").mock(return_value=_describe_response())
    route = respx.post("https://test-host.svc.test.pinecone.io/vectors/upsert").mock(
        return_value=httpx.Response(200, json={"upsertedCount": 2})
    )
    store = await _store()
    try:
        await store.upsert([
            VectorItem(id="v1", vector=[0.1, 0.2], metadata={"doc_id": "d1"}),
            VectorItem(id="v2", vector=[0.3, 0.4], metadata={"doc_id": "d2"}),
        ])
    finally:
        await store.aclose()
    body = json.loads(route.calls.last.request.content)
    assert body["vectors"][0]["id"] == "v1"
    assert body["vectors"][0]["values"] == [0.1, 0.2]
    assert body["vectors"][0]["metadata"] == {"doc_id": "d1"}
    assert body["vectors"][1]["id"] == "v2"


@respx.mock
async def test_query_returns_typed_hits():
    respx.get(f"{PINECONE_CONTROL_URL}/indexes/arcana").mock(return_value=_describe_response())
    respx.post("https://test-host.svc.test.pinecone.io/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "matches": [
                    {"id": "v1", "score": 0.95, "metadata": {"doc_id": "d1"}},
                    {"id": "v2", "score": 0.80, "metadata": {"doc_id": "d2"}},
                ]
            },
        )
    )
    store = await _store()
    try:
        hits = await store.query([0.1] * 3072, top_k=2)
    finally:
        await store.aclose()
    assert [h.id for h in hits] == ["v1", "v2"]
    assert hits[0].score == 0.95
    assert hits[0].metadata == {"doc_id": "d1"}


@respx.mock
async def test_query_passes_filter():
    respx.get(f"{PINECONE_CONTROL_URL}/indexes/arcana").mock(return_value=_describe_response())
    route = respx.post("https://test-host.svc.test.pinecone.io/query").mock(
        return_value=httpx.Response(200, json={"matches": []})
    )
    store = await _store()
    try:
        await store.query([0.1] * 3072, top_k=5, filter={"doc_id": {"$eq": "d1"}})
    finally:
        await store.aclose()
    body = json.loads(route.calls.last.request.content)
    assert body["filter"] == {"doc_id": {"$eq": "d1"}}
    assert body["topK"] == 5


@respx.mock
async def test_delete_request_body():
    respx.get(f"{PINECONE_CONTROL_URL}/indexes/arcana").mock(return_value=_describe_response())
    route = respx.post("https://test-host.svc.test.pinecone.io/vectors/delete").mock(
        return_value=httpx.Response(200, json={})
    )
    store = await _store()
    try:
        await store.delete(["v1", "v2"])
    finally:
        await store.aclose()
    body = json.loads(route.calls.last.request.content)
    assert body["ids"] == ["v1", "v2"]


@respx.mock
async def test_upsert_empty_short_circuits():
    # No describe route — would error if called.
    store = await _store(host="should-not-call.pinecone.io")
    try:
        await store.upsert([])
    finally:
        await store.aclose()


@respx.mock
async def test_data_5xx_raises_vector_store_error():
    respx.get(f"{PINECONE_CONTROL_URL}/indexes/arcana").mock(return_value=_describe_response())
    respx.post("https://test-host.svc.test.pinecone.io/query").mock(
        return_value=httpx.Response(503, text="upstream gone")
    )
    store = await _store()
    try:
        with pytest.raises(VectorStoreError) as exc:
            await store.query([0.1] * 3072)
    finally:
        await store.aclose()
    assert "query" in str(exc.value)
