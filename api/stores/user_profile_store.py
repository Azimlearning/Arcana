"""Persistent per-user profile store (FR-USR-02).

Profiles are stored as individual JSON files under {root}/{uid}.json.
The store is safe for concurrent async access via a per-uid asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from api.core.logging import get_logger
from api.genui._generated import UpdateProfileRequest, UserPreferences, UserProfile

logger = get_logger(__name__)

_DEFAULT_PREFERENCES = UserPreferences(
    defaultMode="research",
    theme="system",
    citationStyle="apa",
    studyContext="",
)


class UserProfileStore:
    """JSON-file-backed store for per-user profiles."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, uid: str) -> asyncio.Lock:
        if uid not in self._locks:
            self._locks[uid] = asyncio.Lock()
        return self._locks[uid]

    def _path(self, uid: str) -> Path:
        return self._root / f"{uid}.json"

    async def get(self, uid: str, *, email: str | None = None) -> UserProfile:
        """Return the profile for *uid*, creating a default one if absent."""
        async with self._lock(uid):
            path = self._path(uid)
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                # Back-fill new fields introduced after initial save.
                prefs = raw.get("preferences", {})
                prefs.setdefault("citationStyle", "apa")
                prefs.setdefault("studyContext", "")
                raw.setdefault("updatedAt", raw.get("createdAt", datetime.now(UTC).isoformat()))
                return UserProfile(**raw)

            now = datetime.now(UTC).isoformat()
            profile = UserProfile(
                uid=uid,
                email=email,
                displayName=None,
                createdAt=now,
                updatedAt=now,
                preferences=_DEFAULT_PREFERENCES,
            )
            path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
            logger.info("profile.created", uid=uid)
            return profile

    async def upsert(self, uid: str, request: UpdateProfileRequest) -> UserProfile:
        """Merge *request* fields into the existing profile and persist."""
        async with self._lock(uid):
            path = self._path(uid)
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                prefs = raw.get("preferences", {})
                prefs.setdefault("citationStyle", "apa")
                prefs.setdefault("studyContext", "")
                raw.setdefault("updatedAt", raw.get("createdAt", datetime.now(UTC).isoformat()))
                profile = UserProfile(**raw)
            else:
                now = datetime.now(UTC).isoformat()
                profile = UserProfile(
                    uid=uid,
                    email=None,
                    displayName=None,
                    createdAt=now,
                    updatedAt=now,
                    preferences=_DEFAULT_PREFERENCES,
                )

            # Apply partial updates.
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
            updated = UserProfile(**data)
            path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
            logger.info("profile.updated", uid=uid)
            return updated
