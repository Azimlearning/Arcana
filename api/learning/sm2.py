"""SM-2 spaced-repetition scheduling algorithm.

SM-2 (SuperMemo 2) is the classic interval-based algorithm used by Anki.
Input: current ScheduleState + quality rating (0-5).
Output: next ScheduleState (dueAt, interval, easeFactor, repetitions).

Rating conventions:
  0 - complete blackout
  1 - wrong answer, but correct felt familiar
  2 - wrong, but correct was easy once shown
  3 - hard; correct answer required significant effort
  4 - correct with some hesitation
  5 - perfect recall, no hesitation

Rating 0-2 fails the card (repetitions reset, interval = 1 day).
Rating 3-5 passes the card (interval grows, ease factor adjusts).

Reference: Wozniak (1990). SuperMemo 2 algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

_EASE_MIN = 1.3
_EASE_DEFAULT = 2.5
_INITIAL_INTERVAL_PASS = 1
_SECOND_INTERVAL_PASS = 6


@dataclass(frozen=True)
class ScheduleState:
    """Wire-compatible scheduling state for one flashcard."""

    due_at: str        # ISO 8601 date string (YYYY-MM-DD)
    interval: int      # days until next review
    ease_factor: float # SM-2 ease factor; starts at 2.5
    repetitions: int   # consecutive passes (resets on fail)


def initial_state(today: date | None = None) -> ScheduleState:
    """Return ScheduleState for a brand-new card (never reviewed)."""
    d = today or date.today()
    return ScheduleState(
        due_at=d.isoformat(),
        interval=0,
        ease_factor=_EASE_DEFAULT,
        repetitions=0,
    )


def advance(
    state: ScheduleState | None,
    rating: int,
    today: date | None = None,
) -> ScheduleState:
    """Apply one SM-2 review step and return the next ScheduleState.

    Args:
        state:  Current state. None is treated as a brand-new card.
        rating: 0-5 quality rating (see module docstring).
        today:  Override for the current date (useful in tests).

    Raises:
        ValueError: If rating is outside [0, 5].
    """
    if not (0 <= rating <= 5):
        raise ValueError(f"rating must be 0-5, got {rating}")

    d = today or date.today()

    if state is None:
        state = initial_state(d)

    ease = state.ease_factor
    reps = state.repetitions

    # Ease factor update applied regardless of pass/fail.
    ease = max(_EASE_MIN, ease + 0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))

    if rating < 3:
        # Fail: reset repetition streak; review again tomorrow.
        new_reps = 0
        new_interval = 1
    else:
        # Pass: advance interval per SM-2 schedule.
        if reps == 0:
            new_interval = _INITIAL_INTERVAL_PASS
        elif reps == 1:
            new_interval = _SECOND_INTERVAL_PASS
        else:
            new_interval = max(1, round(state.interval * ease))
        new_reps = reps + 1

    due = d + timedelta(days=new_interval)
    return ScheduleState(
        due_at=due.isoformat(),
        interval=new_interval,
        ease_factor=round(ease, 4),
        repetitions=new_reps,
    )


def is_due(state: ScheduleState, today: date | None = None) -> bool:
    """Return True if the card is due for review on or before today."""
    d = today or date.today()
    try:
        due = date.fromisoformat(state.due_at)
    except ValueError:
        return True  # corrupt date treated as due
    return due <= d


def to_wire(state: ScheduleState) -> dict:
    """Convert to camelCase wire representation for the frontend schema."""
    return {
        "dueAt": state.due_at,
        "interval": state.interval,
        "easeFactor": state.ease_factor,
        "repetitions": state.repetitions,
    }


def from_wire(d: dict) -> ScheduleState:
    """Parse a camelCase wire dict into a ScheduleState."""
    return ScheduleState(
        due_at=str(d.get("dueAt", date.today().isoformat())),
        interval=int(d.get("interval", 0)),
        ease_factor=float(d.get("easeFactor", _EASE_DEFAULT)),
        repetitions=int(d.get("repetitions", 0)),
    )
