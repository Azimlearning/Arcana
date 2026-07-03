"""Analytics event store — FR-ANL-01, FR-ANL-03, R-03.

Three event types recorded per user:
  TurnEvent        — auto-captured once per chat turn
  FeedbackRating   — per-block thumbs up/down
  SurveySubmission — 10-item SUS survey (fires after 5 turns)

JSONL layout under root/:
  {root}/{user_id}/turns.jsonl
  {root}/{user_id}/feedback.jsonl
  {root}/{user_id}/surveys.jsonl

Firestore layout (``Settings.event_backend=firestore``):
  users/{uid}/turns|feedback|surveys|events/{uuid}
  users/{uid} carries a marker field so export_all can enumerate users.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from api.stores.firestore_client import FirestoreClient

# ── Domain objects (mirror packages/schema/src/api.ts) ────────────────────────


@dataclass
class TurnEvent:
    session_id: str
    user_id: str
    timestamp: str  # ISO 8601
    query: str  # truncated to 500 chars
    mode: str
    intent: str
    agents_triggered: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    block_types: list[str] = field(default_factory=list)
    retrieved_chunk_count: int = 0


@dataclass
class FeedbackRating:
    session_id: str
    block_id: str
    user_id: str
    rating: str  # 'up' | 'down'
    block_type: str
    timestamp: str  # ISO 8601


@dataclass
class SurveySubmission:
    session_id: str
    user_id: str
    timestamp: str  # ISO 8601
    responses: list[int]  # 10 items, Likert 1-5
    sus_score: float  # 0-100, pre-computed by route
    task_description: str = ""


@dataclass
class ActivityEvent:
    """Generic §20 instrumentation event (FR-ANL). Captures the categories
    not already covered per-turn — ingestion, learning, UI overrides — as a
    flat (category, action, payload) row so new event kinds need no schema
    change."""

    user_id: str
    timestamp: str  # ISO 8601
    category: str  # 'ingestion' | 'retrieval' | 'learning' | 'ui' | 'agent'
    action: str  # e.g. 'document_added', 'mode_override'
    payload: dict[str, Any] = field(default_factory=dict)


def compute_sus(responses: list[int]) -> float:
    """Standard SUS formula: odd items (1-indexed) subtract 1; even items: 5 minus.
    Sum x 2.5 -> 0-100 scale.  Expects exactly 10 Likert 1-5 responses.
    """
    if len(responses) != 10:
        raise ValueError(f"SUS requires 10 responses, got {len(responses)}")
    total = 0
    for i, r in enumerate(responses):
        if (i + 1) % 2 == 1:  # odd (1,3,5,7,9)
            total += r - 1
        else:  # even (2,4,6,8,10)
            total += 5 - r
    return total * 2.5


# ── Abstract interface ─────────────────────────────────────────────────────────


class EventStore(ABC):
    @abstractmethod
    async def append_turn(self, event: TurnEvent) -> None: ...

    @abstractmethod
    async def append_feedback(self, rating: FeedbackRating) -> None: ...

    @abstractmethod
    async def append_survey(self, submission: SurveySubmission) -> None: ...

    @abstractmethod
    async def append_event(self, event: ActivityEvent) -> None: ...

    @abstractmethod
    async def export_user(self, user_id: str) -> dict[str, list[dict[str, Any]]]: ...

    @abstractmethod
    async def export_all(self) -> dict[str, Any]: ...

    async def aclose(self) -> None:  # noqa: B027
        pass


# ── JSONL implementation ───────────────────────────────────────────────────────


class JsonlEventStore(EventStore):
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _user_dir(self, user_id: str) -> Path:
        d = self._root / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _append(path: Path, data: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(data) + "\n")

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    async def append_turn(self, event: TurnEvent) -> None:
        self._append(self._user_dir(event.user_id) / "turns.jsonl", asdict(event))

    async def append_feedback(self, rating: FeedbackRating) -> None:
        self._append(self._user_dir(rating.user_id) / "feedback.jsonl", asdict(rating))

    async def append_survey(self, submission: SurveySubmission) -> None:
        self._append(
            self._user_dir(submission.user_id) / "surveys.jsonl",
            asdict(submission),
        )

    async def append_event(self, event: ActivityEvent) -> None:
        self._append(self._user_dir(event.user_id) / "events.jsonl", asdict(event))

    async def export_user(self, user_id: str) -> dict[str, list[dict[str, Any]]]:
        d = self._root / user_id
        return {
            "turns": self._read(d / "turns.jsonl"),
            "feedback": self._read(d / "feedback.jsonl"),
            "surveys": self._read(d / "surveys.jsonl"),
            "events": self._read(d / "events.jsonl"),
        }

    async def export_all(self) -> dict[str, Any]:
        if not self._root.exists():
            return {}
        result: dict[str, Any] = {}
        for user_dir in sorted(self._root.iterdir()):
            if user_dir.is_dir():
                result[user_dir.name] = {
                    "turns": self._read(user_dir / "turns.jsonl"),
                    "feedback": self._read(user_dir / "feedback.jsonl"),
                    "surveys": self._read(user_dir / "surveys.jsonl"),
                    "events": self._read(user_dir / "events.jsonl"),
                }
        return result


# ── Firestore implementation ───────────────────────────────────────────────────


class FirestoreEventStore(EventStore):
    """Firestore-backed analytics store: one document per event at
    ``users/{uid}/{turns|feedback|surveys|events}/{uuid}``.

    JSONL preserved append order; Firestore document ids are random, so
    exports sort each collection by ``timestamp`` to keep rows stable for
    the researcher-facing `GET /analytics/export` (FR-ANL-03).

    A marker field is upserted on ``users/{uid}`` (once per process per
    user) so ``export_all`` can enumerate users by listing the ``users``
    collection — subcollection parents are not listable otherwise.
    """

    _KINDS = ("turns", "feedback", "surveys", "events")

    def __init__(self, client: FirestoreClient) -> None:
        self._client = client
        self._seen_users: set[str] = set()

    @staticmethod
    def _safe(user_id: str) -> str:
        return "".join(c if c.isalnum() or c in "-_." else "_" for c in user_id)

    async def _append(self, user_id: str, kind: str, data: dict[str, Any]) -> None:
        uid = self._safe(user_id)
        if uid not in self._seen_users:
            # Marker doc so export_all can list users. Full-replace is safe:
            # nothing else writes fields on users/{uid} itself.
            await self._client.set(f"users/{uid}", {"uid": uid})
            self._seen_users.add(uid)
        await self._client.set(f"users/{uid}/{kind}/{uuid.uuid4()}", data)

    async def append_turn(self, event: TurnEvent) -> None:
        await self._append(event.user_id, "turns", asdict(event))

    async def append_feedback(self, rating: FeedbackRating) -> None:
        await self._append(rating.user_id, "feedback", asdict(rating))

    async def append_survey(self, submission: SurveySubmission) -> None:
        await self._append(submission.user_id, "surveys", asdict(submission))

    async def append_event(self, event: ActivityEvent) -> None:
        await self._append(event.user_id, "events", asdict(event))

    @staticmethod
    def _sorted(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda r: str(r.get("timestamp", "")))

    async def export_user(self, user_id: str) -> dict[str, list[dict[str, Any]]]:
        uid = self._safe(user_id)
        out: dict[str, list[dict[str, Any]]] = {}
        for kind in self._KINDS:
            docs = await self._client.list(f"users/{uid}/{kind}")
            out[kind] = self._sorted([fields for _, fields in docs])
        return out

    async def export_all(self) -> dict[str, Any]:
        users = await self._client.list("users")
        result: dict[str, Any] = {}
        for uid, _fields in sorted(users):
            result[uid] = await self.export_user(uid)
        return result

    async def aclose(self) -> None:
        await self._client.aclose()
