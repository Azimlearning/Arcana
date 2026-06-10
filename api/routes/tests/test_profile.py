"""GET /profile + PUT /profile route tests (FR-USR-02)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.auth import CurrentUser, get_current_user
from api.routes.profile import router as profile_router
from api.stores.user_profile_store import UserProfileStore

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_app(store: UserProfileStore, uid: str = "test-uid") -> FastAPI:
    app = FastAPI()
    app.include_router(profile_router)
    app.state.shared = {"profile_store": store}
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        uid=uid, email=f"{uid}@test.com"
    )
    return app


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_get_profile_returns_default(tmp_path: Path) -> None:
    store = UserProfileStore(root=tmp_path / "profiles")
    client = TestClient(_make_app(store))
    resp = client.get("/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["uid"] == "test-uid"
    assert data["preferences"]["defaultMode"] == "research"
    assert data["preferences"]["citationStyle"] == "apa"


def test_get_profile_idempotent(tmp_path: Path) -> None:
    store = UserProfileStore(root=tmp_path / "profiles")
    client = TestClient(_make_app(store))
    r1 = client.get("/profile").json()
    r2 = client.get("/profile").json()
    assert r1["createdAt"] == r2["createdAt"]


def test_put_profile_updates_display_name(tmp_path: Path) -> None:
    store = UserProfileStore(root=tmp_path / "profiles")
    client = TestClient(_make_app(store))
    resp = client.put("/profile", json={"displayName": "Alice"})
    assert resp.status_code == 200
    assert resp.json()["displayName"] == "Alice"


def test_put_profile_updates_preferences(tmp_path: Path) -> None:
    store = UserProfileStore(root=tmp_path / "profiles")
    client = TestClient(_make_app(store))
    resp = client.put("/profile", json={"defaultMode": "study", "citationStyle": "ieee"})
    assert resp.status_code == 200
    prefs = resp.json()["preferences"]
    assert prefs["defaultMode"] == "study"
    assert prefs["citationStyle"] == "ieee"
    assert prefs["theme"] == "system"  # unset fields unchanged


def test_put_profile_updates_study_context(tmp_path: Path) -> None:
    store = UserProfileStore(root=tmp_path / "profiles")
    client = TestClient(_make_app(store))
    resp = client.put("/profile", json={"studyContext": "Distributed systems thesis"})
    assert resp.status_code == 200
    assert resp.json()["preferences"]["studyContext"] == "Distributed systems thesis"


def test_profile_isolated_per_user(tmp_path: Path) -> None:
    store = UserProfileStore(root=tmp_path / "profiles")
    client_a = TestClient(_make_app(store, uid="alice"))
    client_b = TestClient(_make_app(store, uid="bob"))
    client_a.put("/profile", json={"displayName": "Alice"})
    client_b.put("/profile", json={"displayName": "Bob"})
    assert client_a.get("/profile").json()["displayName"] == "Alice"
    assert client_b.get("/profile").json()["displayName"] == "Bob"
