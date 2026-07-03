"""FirestoreNotebookStore — behaviour against a respx-mocked Firestore REST API.

Verifies the NotebookStore contract (create/list/get/delete/increment) and
the structural per-user isolation of the ``users/{uid}/notebooks/{id}``
document layout (FR-USR-03, FR-USR-06).
"""

from __future__ import annotations

import json
import re

import httpx
import respx

from api.stores.firestore_client import FIRESTORE_BASE_URL, FirestoreClient
from api.stores.notebook_store import FirestoreNotebookStore

_DOCS = f"{FIRESTORE_BASE_URL}/projects/test-proj/databases/(default)/documents"


class StubTokens:
    async def token(self) -> str:
        return "test-token"


def _store() -> FirestoreNotebookStore:
    return FirestoreNotebookStore(
        FirestoreClient(project_id="test-proj", token_provider=StubTokens())
    )


def _nb_fields(
    nb_id: str = "nb1",
    *,
    user_id: str = "u1",
    title: str = "My notebook",
    updated_at: str = "2026-07-01T10:00:00+00:00",
    doc_count: int = 0,
) -> dict:
    return {
        "id": {"stringValue": nb_id},
        "userId": {"stringValue": user_id},
        "title": {"stringValue": title},
        "createdAt": {"stringValue": "2026-07-01T00:00:00+00:00"},
        "updatedAt": {"stringValue": updated_at},
        "docCount": {"integerValue": str(doc_count)},
    }


# ── create ────────────────────────────────────────────────────────────


@respx.mock
async def test_create_writes_document_under_user_path():
    route = respx.patch(url__regex=rf"{re.escape(_DOCS)}/users/u1/notebooks/[0-9a-f-]+").mock(
        return_value=httpx.Response(200, json={})
    )
    store = _store()
    try:
        nb = await store.create(user_id="u1", title="  My notebook  ")
    finally:
        await store.aclose()
    assert nb.title == "My notebook"
    assert nb.doc_count == 0
    body = json.loads(route.calls.last.request.content)
    assert body["fields"]["userId"] == {"stringValue": "u1"}
    assert body["fields"]["title"] == {"stringValue": "My notebook"}


@respx.mock
async def test_create_defaults_empty_title_to_untitled():
    respx.patch(url__regex=rf"{re.escape(_DOCS)}/users/u1/notebooks/.+").mock(
        return_value=httpx.Response(200, json={})
    )
    store = _store()
    try:
        nb = await store.create(user_id="u1", title="   ")
    finally:
        await store.aclose()
    assert nb.title == "Untitled"


@respx.mock
async def test_create_sanitises_user_id_in_path():
    route = respx.patch(url__regex=rf"{re.escape(_DOCS)}/users/we_ird_uid/notebooks/.+").mock(
        return_value=httpx.Response(200, json={})
    )
    store = _store()
    try:
        await store.create(user_id="we/ird uid", title="t")
    finally:
        await store.aclose()
    assert route.called


# ── list ──────────────────────────────────────────────────────────────


@respx.mock
async def test_list_returns_sorted_by_updated_at_desc():
    respx.get(f"{_DOCS}/users/u1/notebooks").mock(
        return_value=httpx.Response(
            200,
            json={
                "documents": [
                    {
                        "name": f"{_DOCS}/users/u1/notebooks/old",
                        "fields": _nb_fields("old", updated_at="2026-07-01T00:00:00+00:00"),
                    },
                    {
                        "name": f"{_DOCS}/users/u1/notebooks/new",
                        "fields": _nb_fields("new", updated_at="2026-07-03T00:00:00+00:00"),
                    },
                ]
            },
        )
    )
    store = _store()
    try:
        notebooks = await store.list("u1")
    finally:
        await store.aclose()
    assert [nb.id for nb in notebooks] == ["new", "old"]


@respx.mock
async def test_list_empty_for_new_user():
    respx.get(f"{_DOCS}/users/u1/notebooks").mock(return_value=httpx.Response(200, json={}))
    store = _store()
    try:
        assert await store.list("u1") == []
    finally:
        await store.aclose()


# ── get ───────────────────────────────────────────────────────────────


@respx.mock
async def test_get_parses_notebook():
    respx.get(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(200, json={"name": "...", "fields": _nb_fields(doc_count=4)})
    )
    store = _store()
    try:
        nb = await store.get(user_id="u1", notebook_id="nb1")
    finally:
        await store.aclose()
    assert nb is not None
    assert nb.id == "nb1"
    assert nb.doc_count == 4


@respx.mock
async def test_get_returns_none_when_missing():
    respx.get(f"{_DOCS}/users/u1/notebooks/nope").mock(return_value=httpx.Response(404, json={}))
    store = _store()
    try:
        assert await store.get(user_id="u1", notebook_id="nope") is None
    finally:
        await store.aclose()


@respx.mock
async def test_get_is_scoped_to_requesting_user():
    # Same notebook id, different user — the path (and thus the mock) differs.
    respx.get(f"{_DOCS}/users/u2/notebooks/nb1").mock(return_value=httpx.Response(404, json={}))
    store = _store()
    try:
        assert await store.get(user_id="u2", notebook_id="nb1") is None
    finally:
        await store.aclose()


# ── delete ────────────────────────────────────────────────────────────


@respx.mock
async def test_delete_returns_true_and_deletes_when_present():
    respx.get(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(200, json={"name": "...", "fields": _nb_fields()})
    )
    delete = respx.delete(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(200, json={})
    )
    store = _store()
    try:
        assert await store.delete(user_id="u1", notebook_id="nb1") is True
    finally:
        await store.aclose()
    assert delete.called


@respx.mock
async def test_delete_returns_false_when_missing():
    respx.get(f"{_DOCS}/users/u1/notebooks/nope").mock(return_value=httpx.Response(404, json={}))
    store = _store()
    try:
        assert await store.delete(user_id="u1", notebook_id="nope") is False
    finally:
        await store.aclose()


# ── increment_doc_count ───────────────────────────────────────────────


@respx.mock
async def test_increment_doc_count_read_modify_write():
    respx.get(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(200, json={"name": "...", "fields": _nb_fields(doc_count=2)})
    )
    patch = respx.patch(f"{_DOCS}/users/u1/notebooks/nb1").mock(
        return_value=httpx.Response(200, json={})
    )
    store = _store()
    try:
        await store.increment_doc_count(user_id="u1", notebook_id="nb1")
    finally:
        await store.aclose()
    body = json.loads(patch.calls.last.request.content)
    assert body["fields"]["docCount"] == {"integerValue": "3"}
    # updatedAt refreshed past the stored value
    assert body["fields"]["updatedAt"]["stringValue"] > "2026-07-01T10:00:00+00:00"


@respx.mock
async def test_increment_doc_count_noop_when_missing():
    respx.get(f"{_DOCS}/users/u1/notebooks/nope").mock(return_value=httpx.Response(404, json={}))
    store = _store()
    try:
        await store.increment_doc_count(user_id="u1", notebook_id="nope")  # no raise
    finally:
        await store.aclose()
