"""GET /profile + PUT /profile — persistent user profile (FR-USR-02).

Both endpoints are auth-guarded. GET returns the current user's profile,
creating a default one on first access. PUT accepts a partial update and
returns the merged profile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request

from api.core.auth import CurrentUser, get_current_user
from api.genui._generated import UpdateProfileRequest, UserProfile

if TYPE_CHECKING:
    from api.stores.user_profile_store import UserProfileStore

router = APIRouter()


def get_profile_store() -> UserProfileStore:
    """Placeholder dependency — api/main.py overrides with the real store."""
    raise HTTPException(
        status_code=503,
        detail="Profile store not configured. api.main.create_app() wires this at startup.",
    )


@router.get("/profile", response_model=UserProfile)
async def get_profile(
    http_request: Request,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> UserProfile:
    """Return the authenticated user's profile (creates default on first call)."""
    store: UserProfileStore = http_request.app.state.shared["profile_store"]
    return await store.get(user.uid, email=user.email)


@router.put("/profile", response_model=UserProfile)
async def update_profile(
    body: UpdateProfileRequest,
    http_request: Request,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> UserProfile:
    """Partially update the authenticated user's profile."""
    store: UserProfileStore = http_request.app.state.shared["profile_store"]
    return await store.upsert(user.uid, body)
