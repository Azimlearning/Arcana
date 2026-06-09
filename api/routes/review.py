"""POST /review — spaced-repetition card review endpoint.

Accepts a card review with a quality rating (0-5) and the card's current
schedule, applies the SM-2 algorithm, and returns the updated ScheduleState.

FR-LRN-02: spaced-repetition scheduling.
NFR-SEC-01: guarded by get_current_user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.core.auth import CurrentUser, get_current_user
from api.core.logging import get_logger
from api.learning.sm2 import ScheduleState, advance, from_wire

logger = get_logger(__name__)

router = APIRouter(prefix="/review", tags=["learning"])


class _ScheduleIn(BaseModel):
    """Wire representation of the current card schedule (camelCase)."""
    dueAt: str
    interval: int
    easeFactor: float
    repetitions: int


class ReviewRequest(BaseModel):
    cardId: str = Field(..., min_length=1)
    rating: int = Field(..., ge=0, le=5, description="0=blackout … 5=perfect")
    currentSchedule: _ScheduleIn | None = None


class ReviewResponse(BaseModel):
    cardId: str
    dueAt: str
    interval: int
    easeFactor: float
    repetitions: int


@router.post("", response_model=ReviewResponse, status_code=200)
async def review_card(
    body: ReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> ReviewResponse:
    """Apply one SM-2 review step to a flashcard.

    The client sends the card's current schedule (or null for first review)
    and the quality rating. The server applies SM-2 and returns the next
    schedule so the client can persist it in the FlashcardDeck payload.
    """
    try:
        state: ScheduleState | None = (
            from_wire(body.currentSchedule.model_dump(by_alias=False))
            if body.currentSchedule is not None
            else None
        )
        next_state = advance(state, body.rating)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    logger.info(
        "review.applied",
        user=current_user.uid,
        card=body.cardId,
        rating=body.rating,
        next_due=next_state.due_at,
    )

    return ReviewResponse(
        cardId=body.cardId,
        dueAt=next_state.due_at,
        interval=next_state.interval,
        easeFactor=next_state.ease_factor,
        repetitions=next_state.repetitions,
    )
