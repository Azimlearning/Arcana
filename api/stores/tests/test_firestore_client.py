"""FirestoreClient — REST behaviour via respx (mirrors test_pinecone_store.py).

Request shape (URL, auth header, body encoding) and response parsing are
tested without touching the network or google-auth: tests inject a stub
TokenProvider so ServiceAccountTokenProvider (which needs a real key) is
never constructed.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from api.stores.firestore_client import (
    FIRESTORE_BASE_URL,
    FirestoreClient,
    FirestoreError,
    decode_fields,
    encode_fields,
    from_firestore_value,
    to_firestore_value,
)

_DOCS = f"{FIRESTORE_BASE_URL}/projects/test-proj/databases/(default)/documents"


class StubTokens:
    def __init__(self, value: str = "test-token") -> None:
        self.value = value
        self.calls = 0

    async def token(self) -> str:
        self.calls += 1
        return self.value


def _client() -> FirestoreClient:
    return FirestoreClient(project_id="test-proj", token_provider=StubTokens())


# ── Value codec ───────────────────────────────────────────────────────


def test_codec_roundtrip_scalars():
    for value in ["hello", 42, 3.14, True, False, None]:
        assert from_firestore_value(to_firestore_value(value)) == value


def test_codec_bool_not_confused_with_int():
    assert to_firestore_value(True) == {"booleanValue": True}
    assert to_firestore_value(1) == {"integerValue": "1"}


def test_codec_roundtrip_nested():
    data = {
        "title": "Notebook",
        "docCount": 3,
        "tags": ["a", "b"],
        "meta": {"pinned": True, "weight": 0.5, "none": None},
    }
    assert decode_fields(encode_fields(data)) == data


def test_codec_rejects_unsupported_type():
    with pytest.raises(FirestoreError):
        to_firestore_value(object())


def test_codec_rejects_unknown_wire_shape():
    with pytest.raises(FirestoreError):
        from_firestore_value({"geoPointValue": {}})


def test_codec_decodes_timestamp_as_string():
    assert from_firestore_value({"timestampValue": "2026-07-03T00:00:00Z"}) == (
        "2026-07-03T00:00:00Z"
    )


# ── Document operations ───────────────────────────────────────────────


@respx.mock
async def test_get_decodes_fields_and_sends_bearer():
    route = respx.get(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "projects/test-proj/databases/(default)/documents/users/u1/notebooks/nb1",
                "fields": {"title": {"stringValue": "T"}, "docCount": {"integerValue": "2"}},
            },
        )
    )
    client = _client()
    try:
        data = await client.get("users/u1/notebooks/nb1")
    finally:
        await client.aclose()
    assert data == {"title": "T", "docCount": 2}
    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"


@respx.mock
async def test_get_returns_none_on_404():
    respx.get(f"{_DOCS}/users/u1/notebooks/missing").mock(
        return_value=httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})
    )
    client = _client()
    try:
        assert await client.get("users/u1/notebooks/missing") is None
    finally:
        await client.aclose()


@respx.mock
async def test_set_patches_encoded_fields():
    route = respx.patch(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(200, json={"name": "..."})
    )
    client = _client()
    try:
        await client.set("users/u1/notebooks/nb1", {"title": "T", "docCount": 0})
    finally:
        await client.aclose()
    import json

    body = json.loads(route.calls.last.request.content)
    assert body == {"fields": {"title": {"stringValue": "T"}, "docCount": {"integerValue": "0"}}}


@respx.mock
async def test_delete_hits_document_url():
    route = respx.delete(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(200, json={})
    )
    client = _client()
    try:
        await client.delete("users/u1/notebooks/nb1")
    finally:
        await client.aclose()
    assert route.called


@respx.mock
async def test_list_paginates_until_no_token():
    def _page(request: httpx.Request) -> httpx.Response:
        if "pageToken" not in str(request.url):
            return httpx.Response(
                200,
                json={
                    "documents": [
                        {"name": f"{_DOCS}/users/u1/notebooks/a", "fields": {}},
                    ],
                    "nextPageToken": "tok2",
                },
            )
        return httpx.Response(
            200,
            json={
                "documents": [
                    {"name": f"{_DOCS}/users/u1/notebooks/b", "fields": {}},
                ]
            },
        )

    route = respx.get(f"{_DOCS}/users/u1/notebooks").mock(side_effect=_page)
    client = _client()
    try:
        docs = await client.list("users/u1/notebooks")
    finally:
        await client.aclose()
    assert [doc_id for doc_id, _ in docs] == ["a", "b"]
    assert route.call_count == 2


@respx.mock
async def test_list_empty_collection():
    respx.get(f"{_DOCS}/users/u1/notebooks").mock(return_value=httpx.Response(200, json={}))
    client = _client()
    try:
        assert await client.list("users/u1/notebooks") == []
    finally:
        await client.aclose()


@respx.mock
async def test_http_error_raises_firestore_error():
    respx.get(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}})
    )
    client = _client()
    try:
        with pytest.raises(FirestoreError, match="403"):
            await client.get("users/u1/notebooks/nb1")
    finally:
        await client.aclose()
