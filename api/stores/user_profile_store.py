"""Persistent per-user profile store (FR-USR-02).

`UserProfileStore` is the ABC; the default-profile creation and the
PATCH-merge semantics live here (template method) so every backend
behaves identically. Backends implement only `_load` / `_save`.

Concrete impls:
  JsonUserProfileStore      — one JSON file per user at ``{root}/{uid}.json``.
  FirestoreUserProfileStore — one document at ``users/{uid}/profile/main``
                              via the REST client in ``firestore_client.py``.
                              Selected with ``Settings.profile_backend=firestore``.

All impls are safe for concurrent async access via a per-uid asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.core.logging import get_logger
from api.genui._generated import UpdateProfileRequest, UserPreferences, UserProfile
from api.stores.firestore_client import FirestoreClient

logger = get_logger(__name__)

_DEFAULT_PREFERENCES = UserPreferences(
    defaultMode="research",
    theme="system",
    citationStyle="apa",
    studyContext="",
)


def _default_profile(uid: str, email: str | None) -> UserProfile:
    now = datetime.now(UTC).isoformat()
    return UserProfile(
        uid=uid,
        email=email,
        displayName=None,
        createdAt=now,
        updatedAt=now,
        preferences=_DEFAULT_PREFERENCES,
    )


def _profile_from_raw(raw: dict[str, Any]) -> UserProfile:
    """Parse a stored dict, back-filling fields introduced after initial save."""
    prefs = raw.get("preferences", {})
    prefs.setdefault("citationStyle", "apa")
    prefs.setdefault("studyContext", "")
    raw.setdefault("updatedAt", raw.get("createdAt", datetime.now(UTC).isoformat()))
    return UserProfile(**raw)


def _apply_update(profile: UserProfile, request: UpdateProfileRequest) -> UserProfile:
    """PATCH semantics: only fields present in *request* are updated."""
    data = profile.model_dump()
    if request.displayName is not None or "displayName" in (request.model_fields_set or set()):
        data["displayName"] = request.displayName

    prefs = data["preferences"]
    if request.defaultMode is not None:
        prefs["defaultMode"] = request.defaultMode
    if request.theme is not None:
        prefs["theme"] = request.theme
    if request.citationStyle is not None:
        prefs["citationStyle"] = request.citationStyle
    if request.studyContext is not None:
        prefs["studyContext"] = request.studyContext

    data["updatedAt"] = datetime.now(UTC).isoformat()
    return UserProfile(**data)


# ── Abstract interface ────────────────────────────────────────────────────────


class UserProfileStore(ABC):
    """Storage abstraction for per-user profiles.

    `get` / `upsert` are implemented here once; backends supply raw
    dict persistence via `_load` / `_save`.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, uid: str) -> asyncio.Lock:
        if uid not in self._locks:
            self._locks[uid] = asyncio.Lock()
        return self._locks[uid]

    @abstractmethod
    async def _load(self, uid: str) -> dict[str, Any] | None:
        """Return the stored raw profile dict, or None if absent."""

    @abstractmethod
    async def _save(self, uid: str, profile: UserProfile) -> None:
        """Persist the profile."""

    async def aclose(self) -> None:  # noqa: B027
        pass

    async def get(self, uid: str, *, email: str | None = None) -> UserProfile:
        """Return the profile for *uid*, creating a default one if absent."""
        async with self._lock(uid):
            raw = await self._load(uid)
            if raw is not None:
                return _profile_from_raw(raw)
            profile = _default_profile(uid, email)
            await self._save(uid, profile)
            logger.info("profile.created", uid=uid)
            return profile

    async def upsert(self, uid: str, request: UpdateProfileRequest) -> UserProfile:
        """Merge *request* fields into the existing profile and persist."""
        async with self._lock(uid):
            raw = await self._load(uid)
            profile = _profile_from_raw(raw) if raw is not None else _default_profile(uid, None)
            updated = _apply_update(profile, request)
            await self._save(uid, updated)
            logger.info("profile.updated", uid=uid)
            return updated


# ── JSON-file implementation ──────────────────────────────────────────────────


class JsonUserProfileStore(UserProfileStore):
    """JSON-file-backed store for per-user profiles."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, uid: str) -> Path:
        return self._root / f"{uid}.json"

    async def _load(self, uid: str) -> dict[str, Any] | None:
        path = self._path(uid)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    async def _save(self, uid: str, profile: UserProfile) -> None:
        self._path(uid).write_text(profile.model_dump_json(indent=2), encoding="utf-8")


# ── Firestore implementation ──────────────────────────────────────────────────


class FirestoreUserProfileStore(UserProfileStore):
    """Firestore-backed store: one document at ``users/{uid}/profile/main``.

    The profile lives in a subcollection (not on ``users/{uid}`` itself)
    because FirestoreEventStore full-replaces the parent doc as its
    user-enumeration marker.
    """

    def __init__(self, client: FirestoreClient) -> None:
        super().__init__()
        self._client = client

    @staticmethod
    def _safe(uid: str) -> str:
        return "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)

    def _path(self, uid: str) -> str:
        return f"users/{self._safe(uid)}/profile/main"

    async def _load(self, uid: str) -> dict[str, Any] | None:
        return await self._client.get(self._path(uid))

    async def _save(self, uid: str, profile: UserProfile) -> None:
        await self._client.set(self._path(uid), profile.model_dump())

    async def aclose(self) -> None:
        await self._client.aclose()
