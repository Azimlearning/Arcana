"""Persistent review-event store for spaced-repetition progress (FR-LRN-10).

One JSONL file per user: `{root}/{uid}.jsonl`. Each line records one card
review so the ProgressDashboard can compute per-topic retention, mastery,
and streak without re-reading the entire flashcard corpus.

Wire contract for one event line:
  {"cardId": "...", "deckId": "...", "topic": "...", "rating": 4,
   "interval": 7, "repetitions": 2, "easeFactor": 2.5,
   "reviewedAt": "2026-06-11T12:34:00Z", "dueAt": "2026-06-18"}
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from api.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReviewEvent:
    card_id: str
    deck_id: str
    topic: str
    rating: int          # 0-5
    interval: int        # days until next review
    repetitions: int
    ease_factor: float
    reviewed_at: str     # ISO 8601 datetime
    due_at: str          # ISO 8601 date


@dataclass
class TopicStats:
    topic: str
    total_cards: int
    mastered_cards: int  # interval >= 21 days
    due_count: int
    retention_rate: float  # 0-1


@dataclass
class ProgressStats:
    total_cards: int
    mastered_cards: int
    streak_days: int
    topics: list[TopicStats]
    next_review_at: str | None  # ISO date of earliest due card, or None


class JsonlReviewStore:
    """Per-user JSONL review event log."""

    def __init__(self, *, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    def _path(self, uid: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in uid)[:128]
        return self._root / f"{safe or 'anon'}.jsonl"

    async def _lock(self, uid: str) -> asyncio.Lock:
        async with self._meta_lock:
            if uid not in self._locks:
                self._locks[uid] = asyncio.Lock()
        return self._locks[uid]

    async def record(self, uid: str, event: ReviewEvent) -> None:
        path = self._path(uid)
        line = json.dumps(asdict(event), ensure_ascii=False) + "\n"
        lock = await self._lock(uid)
        async with lock:
            try:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
            except OSError:
                logger.warning("review_store.write_failed", uid=uid)

    async def get_stats(self, uid: str, notebook_id: str | None = None) -> ProgressStats:
        """Compute progress stats from the review log for `uid`.

        If `notebook_id` is given, filters to events where deckId starts
        with `notebook_id`. Most callers pass None to get global stats.
        """
        path = self._path(uid)
        if not path.exists():
            return ProgressStats(0, 0, 0, [], None)

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ProgressStats(0, 0, 0, [], None)

        # Parse events; keep only the LATEST review per cardId.
        latest: dict[str, ReviewEvent] = {}
        reviewed_dates: set[str] = set()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ev = ReviewEvent(**obj)
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

            if notebook_id and not ev.deck_id.startswith(notebook_id):
                continue

            # Keep latest review per card (highest reviewed_at)
            prev = latest.get(ev.card_id)
            if prev is None or ev.reviewed_at > prev.reviewed_at:
                latest[ev.card_id] = ev

            # Track review date for streak calculation
            day = ev.reviewed_at[:10]  # "YYYY-MM-DD"
            reviewed_dates.add(day)

        if not latest:
            return ProgressStats(0, 0, 0, [], None)

        today = date.today()

        # Per-card stats
        total = len(latest)
        mastered = sum(1 for e in latest.values() if e.interval >= 21)

        # Next review = earliest due_at across all cards
        due_dates = [e.due_at for e in latest.values() if e.due_at >= today.isoformat()]
        next_review_at = min(due_dates) if due_dates else None

        # Per-topic breakdown
        by_topic: dict[str, list[ReviewEvent]] = {}
        for ev in latest.values():
            by_topic.setdefault(ev.topic, []).append(ev)

        topics: list[TopicStats] = []
        for topic, evs in by_topic.items():
            t_total = len(evs)
            t_mastered = sum(1 for e in evs if e.interval >= 21)
            t_due = sum(1 for e in evs if e.due_at <= today.isoformat())
            t_retention = t_mastered / t_total if t_total else 0.0
            topics.append(TopicStats(
                topic=topic,
                total_cards=t_total,
                mastered_cards=t_mastered,
                due_count=t_due,
                retention_rate=round(t_retention, 3),
            ))

        # Streak: count consecutive days ending today (or yesterday if today not reviewed yet)
        streak = _compute_streak(reviewed_dates, today)

        return ProgressStats(
            total_cards=total,
            mastered_cards=mastered,
            streak_days=streak,
            topics=sorted(topics, key=lambda t: t.topic),
            next_review_at=next_review_at,
        )


def _compute_streak(reviewed_dates: set[str], today: date) -> int:
    """Count consecutive days reviewed ending at today or yesterday."""
    if not reviewed_dates:
        return 0
    streak = 0
    check = today
    while check.isoformat() in reviewed_dates:
        streak += 1
        check = date.fromordinal(check.toordinal() - 1)
    if streak == 0:
        # Accept yesterday as the tail of a streak (user hasn't reviewed today yet)
        yesterday = date.fromordinal(today.toordinal() - 1)
        check = yesterday
        while check.isoformat() in reviewed_dates:
            streak += 1
            check = date.fromordinal(check.toordinal() - 1)
    return streak
