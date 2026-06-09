"""POST /feedback/rating and POST /feedback/sus — FR-ANL-03, R-03."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from api.analytics.event_store import EventStore, FeedbackRating, SurveySubmission, compute_sus
from api.core.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _get_event_store(request: Request) -> EventStore:
    return request.app.state.shared["event_store"]  # type: ignore[no-any-return]


# ── /feedback/rating ─────────────────────────────────────────────────────────


class RatingRequest(BaseModel):
    sessionId: str
    blockId: str
    rating: str = Field(pattern=r"^(up|down)$")
    blockType: str


@router.post("/rating", status_code=200)
async def post_rating(
    body: RatingRequest,
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, bool]:
    store: EventStore = _get_event_store(request)
    await store.append_feedback(
        FeedbackRating(
            session_id=body.sessionId,
            block_id=body.blockId,
            user_id=user.uid,
            rating=body.rating,
            block_type=body.blockType,
            timestamp=datetime.now(UTC).isoformat(),
        )
    )
    return {"ok": True}


# ── /feedback/sus ─────────────────────────────────────────────────────────────


class SurveyRequest(BaseModel):
    sessionId: str
    responses: list[int] = Field(min_length=10, max_length=10)
    taskDescription: str = ""


class SurveyResponse(BaseModel):
    ok: bool
    susScore: float


@router.post("/sus", status_code=200)
async def post_sus(
    body: SurveyRequest,
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SurveyResponse:
    sus_score = compute_sus(body.responses)
    store: EventStore = _get_event_store(request)
    await store.append_survey(
        SurveySubmission(
            session_id=body.sessionId,
            user_id=user.uid,
            timestamp=datetime.now(UTC).isoformat(),
            responses=body.responses,
            sus_score=sus_score,
            task_description=body.taskDescription,
        )
    )
    return SurveyResponse(ok=True, susScore=sus_score)
