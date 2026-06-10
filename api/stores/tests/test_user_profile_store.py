"""Tests for UserProfileStore (FR-USR-02)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.genui._generated import UpdateProfileRequest, UserProfile
from api.stores.user_profile_store import UserProfileStore


@pytest.fixture
def store(tmp_path: Path) -> UserProfileStore:
    return UserProfileStore(root=tmp_path / "profiles")


@pytest.mark.asyncio
async def test_get_creates_default_profile(store: UserProfileStore) -> None:
    profile = await store.get("user-a")
    assert isinstance(profile, UserProfile)
    assert profile.uid == "user-a"
    assert profile.preferences.defaultMode == "research"
    assert profile.preferences.theme == "system"
    assert profile.preferences.citationStyle == "apa"
    assert profile.preferences.studyContext == ""


@pytest.mark.asyncio
async def test_get_stores_email_on_creation(store: UserProfileStore) -> None:
    profile = await store.get("user-b", email="b@example.com")
    assert profile.email == "b@example.com"


@pytest.mark.asyncio
async def test_get_returns_same_profile_on_second_call(store: UserProfileStore) -> None:
    p1 = await store.get("user-c")
    p2 = await store.get("user-c")
    assert p1.createdAt == p2.createdAt
    assert p1.uid == p2.uid


@pytest.mark.asyncio
async def test_upsert_updates_display_name(store: UserProfileStore) -> None:
    await store.get("user-d")
    updated = await store.upsert("user-d", UpdateProfileRequest(displayName="Alice"))
    assert updated.displayName == "Alice"


@pytest.mark.asyncio
async def test_upsert_updates_preferences(store: UserProfileStore) -> None:
    await store.get("user-e")
    updated = await store.upsert(
        "user-e",
        UpdateProfileRequest(defaultMode="study", citationStyle="mla"),
    )
    assert updated.preferences.defaultMode == "study"
    assert updated.preferences.citationStyle == "mla"
    assert updated.preferences.theme == "system"  # unchanged


@pytest.mark.asyncio
async def test_upsert_updates_study_context(store: UserProfileStore) -> None:
    await store.get("user-f")
    updated = await store.upsert("user-f", UpdateProfileRequest(studyContext="Big Data course"))
    assert updated.preferences.studyContext == "Big Data course"


@pytest.mark.asyncio
async def test_upsert_persists_to_disk(store: UserProfileStore, tmp_path: Path) -> None:
    store2 = UserProfileStore(root=tmp_path / "profiles")
    await store2.get("user-g")
    await store2.upsert("user-g", UpdateProfileRequest(theme="dark"))

    store3 = UserProfileStore(root=tmp_path / "profiles")
    profile = await store3.get("user-g")
    assert profile.preferences.theme == "dark"


@pytest.mark.asyncio
async def test_upsert_creates_profile_if_absent(store: UserProfileStore) -> None:
    profile = await store.upsert("new-user", UpdateProfileRequest(theme="light"))
    assert profile.uid == "new-user"
    assert profile.preferences.theme == "light"


@pytest.mark.asyncio
async def test_profile_json_has_correct_keys(store: UserProfileStore, tmp_path: Path) -> None:
    await store.get("user-h")
    path = tmp_path / "profiles" / "user-h.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert "uid" in data
    assert "preferences" in data
    assert "createdAt" in data
    assert "updatedAt" in data
