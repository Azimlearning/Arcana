"""FirestoreEventStore + FirestoreUserProfileStore — respx-mocked REST behaviour.

Covers the append/export event flows (FR-ANL-01/03) and the profile
get/upsert PATCH-merge semantics (FR-USR-02) against the Firestore
document layout (``users/{uid}/...``).
"""

from __future__ import annotations

import json
import re

import httpx
import respx

from api.analytics.event_store import ActivityEvent, FirestoreEventStore, TurnEvent
from api.genui._generated import UpdateProfileRequest
from api.stores.firestore_client import FIRESTORE_BASE_URL, FirestoreClient
from api.stores.user_profile_store import FirestoreUserProfileStore

_DOCS = f"{FIRESTORE_BASE_URL}/projects/test-proj/databases/(default)/documents"


class StubTokens:
    async def token(self) -> str:
        return "test-token"


def _client() -> FirestoreClient:
    return FirestoreClient(project_id="test-proj", token_provider=StubTokens())


def _turn(user_id: str = "u1") -> TurnEvent:
    return TurnEvent(
        session_id="s1",
        user_id=user_id,
        timestamp="2026-07-03T01:00:00+00:00",
        query="q",
        mode="research",
        intent="research",
    )


# ── FirestoreEventStore ───────────────────────────────────────────────


@respx.mock
async def test_append_turn_writes_marker_then_event():
    marker = respx.patch(f"{_DOCS}/users/u1").mock(return_value=httpx.Response(200, json={}))
    event = respx.patch(url__regex=rf"{re.escape(_DOCS)}/users/u1/turns/[0-9a-f-]+").mock(
        return_value=httpx.Response(200, json={})
    )
    store = FirestoreEventStore(_client())
    try:
        await store.append_turn(_turn())
        await store.append_turn(_turn())
    finally:
        await store.aclose()
    assert marker.call_count == 1  # marker upserted once per process per user
    assert event.call_count == 2
    body = json.loads(event.calls.last.request.content)
    assert body["fields"]["query"] == {"stringValue": "q"}
    assert body["fields"]["agents_triggered"] == {"arrayValue": {"values": []}}


@respx.mock
async def test_append_activity_event_sanitises_uid():
    respx.patch(f"{_DOCS}/users/we_ird").mock(return_value=httpx.Response(200, json={}))
    event = respx.patch(url__regex=rf"{re.escape(_DOCS)}/users/we_ird/events/.+").mock(
        return_value=httpx.Response(200, json={})
    )
    store = FirestoreEventStore(_client())
    try:
        await store.append_event(
            ActivityEvent(
                user_id="we/ird",
                timestamp="2026-07-03T01:00:00+00:00",
                category="ingestion",
                action="document_added",
            )
        )
    finally:
        await store.aclose()
    assert event.called


@respx.mock
async def test_export_user_reads_all_four_kinds_sorted():
    def _collection(kind: str, rows: list[dict]) -> None:
        respx.get(f"{_DOCS}/users/u1/{kind}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "documents": [
                        {
                            "name": f"{_DOCS}/users/u1/{kind}/doc{i}",
                            "fields": {"timestamp": {"stringValue": row["timestamp"]}},
                        }
                        for i, row in enumerate(rows)
                    ]
                },
            )
        )

    _collection("turns", [{"timestamp": "2026-07-02"}, {"timestamp": "2026-07-01"}])
    _collection("feedback", [])
    _collection("surveys", [])
    _collection("events", [])
    store = FirestoreEventStore(_client())
    try:
        out = await store.export_user("u1")
    finally:
        await store.aclose()
    assert [r["timestamp"] for r in out["turns"]] == ["2026-07-01", "2026-07-02"]
    assert set(out) == {"turns", "feedback", "surveys", "events"}


@respx.mock
async def test_export_all_enumerates_users_via_markers():
    respx.get(f"{_DOCS}/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "documents": [
                    {"name": f"{_DOCS}/users/u1", "fields": {"uid": {"stringValue": "u1"}}},
                    {"name": f"{_DOCS}/users/u2", "fields": {"uid": {"stringValue": "u2"}}},
                ]
            },
        )
    )
    for uid in ("u1", "u2"):
        for kind in ("turns", "feedback", "surveys", "events"):
            respx.get(f"{_DOCS}/users/{uid}/{kind}").mock(return_value=httpx.Response(200, json={}))
    store = FirestoreEventStore(_client())
    try:
        out = await store.export_all()
    finally:
        await store.aclose()
    assert sorted(out) == ["u1", "u2"]


# ── FirestoreUserProfileStore ─────────────────────────────────────────


@respx.mock
async def test_profile_get_creates_default_when_absent():
    respx.get(f"{_DOCS}/users/u1/profile/main").mock(return_value=httpx.Response(404, json={}))
    save = respx.patch(f"{_DOCS}/users/u1/profile/main").mock(
        return_value=httpx.Response(200, json={})
    )
    store = FirestoreUserProfileStore(_client())
    try:
        profile = await store.get("u1", email="u1@example.com")
    finally:
        await store.aclose()
    assert profile.uid == "u1"
    assert profile.email == "u1@example.com"
    assert profile.preferences.defaultMode == "research"
    assert save.called


@respx.mock
async def test_profile_upsert_merges_partial_update():
    existing = {
        "uid": {"stringValue": "u1"},
        "email": {"nullValue": None},
        "displayName": {"nullValue": None},
        "createdAt": {"stringValue": "2026-07-01T00:00:00+00:00"},
        "updatedAt": {"stringValue": "2026-07-01T00:00:00+00:00"},
        "preferences": {
            "mapValue": {
                "fields": {
                    "defaultMode": {"stringValue": "research"},
                    "theme": {"stringValue": "system"},
                    "citationStyle": {"stringValue": "apa"},
                    "studyContext": {"stringValue": ""},
                }
            }
        },
    }
    respx.get(f"{_DOCS}/users/u1/profile/main").mock(
        return_value=httpx.Response(200, json={"name": "...", "fields": existing})
    )
    save = respx.patch(f"{_DOCS}/users/u1/profile/main").mock(
        return_value=httpx.Response(200, json={})
    )
    store = FirestoreUserProfileStore(_client())
    try:
        updated = await store.upsert("u1", UpdateProfileRequest(theme="dark"))
    finally:
        await store.aclose()
    assert updated.preferences.theme == "dark"
    assert updated.preferences.defaultMode == "research"  # untouched field kept
    body = json.loads(save.calls.last.request.content)
    prefs = body["fields"]["preferences"]["mapValue"]["fields"]
    assert prefs["theme"] == {"stringValue": "dark"}
