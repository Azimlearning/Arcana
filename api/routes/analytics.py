"""GET /analytics/export — research data export — FR-ANL-01, R-03."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from api.analytics.event_store import EventStore
from api.core.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_event_store(request: Request) -> EventStore:
    return request.app.state.shared["event_store"]  # type: ignore[no-any-return]


@router.get("/export")
async def export_analytics(
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    all_users: bool = False,
) -> dict[str, Any]:
    """Export analytics data.

    By default returns the authenticated user's own data.
    `?all_users=true` dumps all users — intended for the researcher running
    the study on their own machine (no separate admin role in P1).
    """
    store: EventStore = _get_event_store(request)
    if all_users:
        return await store.export_all()
    return await store.export_user(user.uid)
