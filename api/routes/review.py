"""POST /review — spaced-repetition card review endpoint.

Accepts a card review with a quality rating (0-5) and the card's current
schedule, applies the SM-2 algorithm, and returns the updated ScheduleState.

FR-LRN-02: spaced-repetition scheduling.
NFR-SEC-01: guarded by get_current_user.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    topic: str = Field(default="", max_length=200)
    deckId: str = Field(default="", max_length=200)


class ReviewResponse(BaseModel):
    cardId: str
    dueAt: str
    interval: int
    easeFactor: float
    repetitions: int


@router.post("", response_model=ReviewResponse, status_code=200)
async def review_card(
    body: ReviewRequest,
    http_request: Request,
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

    # Persist the review event so ProgressDashboard can compute per-topic stats.
    shared = getattr(http_request.app.state, "shared", {})
    review_store = shared.get("review_store")
    if review_store is not None:
        from api.stores.review_store import ReviewEvent
        event = ReviewEvent(
            card_id=body.cardId,
            deck_id=body.deckId or "default",
            topic=body.topic or "General",
            rating=body.rating,
            interval=next_state.interval,
            repetitions=next_state.repetitions,
            ease_factor=next_state.ease_factor,
            reviewed_at=datetime.now(UTC).isoformat(),
            due_at=next_state.due_at,
        )
        try:
            await review_store.record(current_user.uid, event)
        except Exception:
            logger.warning("review.persist_failed", card_id=body.cardId)

    return ReviewResponse(
        cardId=body.cardId,
        dueAt=next_state.due_at,
        interval=next_state.interval,
        easeFactor=next_state.ease_factor,
        repetitions=next_state.repetitions,
    )


@router.get("/progress", tags=["learning"])
async def get_progress(
    http_request: Request,
    notebook_id: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
) -> dict:
    """Return per-topic learning progress for the current user.

    Powers the ProgressDashboard component (FR-LRN-10). Filters to
    `notebook_id` if provided, otherwise returns global stats.
    """
    shared = getattr(http_request.app.state, "shared", {})
    review_store = shared.get("review_store")
    if review_store is None:
        return {"totalCards": 0, "masteredCards": 0, "streakDays": 0, "topics": [], "nextReviewAt": None}

    stats = await review_store.get_stats(current_user.uid, notebook_id=notebook_id)
    return {
        "notebookId": notebook_id or "all",
        "totalCards": stats.total_cards,
        "masteredCards": stats.mastered_cards,
        "streakDays": stats.streak_days,
        "topics": [
            {
                "topic": t.topic,
                "totalCards": t.total_cards,
                "masteredCards": t.mastered_cards,
                "dueCount": t.due_count,
                "retentionRate": t.retention_rate,
            }
            for t in stats.topics
        ],
        "nextReviewAt": stats.next_review_at,
    }
