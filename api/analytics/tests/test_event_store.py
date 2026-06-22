"""Tests for analytics event store — FR-ANL-01, FR-ANL-03."""

from __future__ import annotations

import pytest

from api.analytics.event_store import (
    FeedbackRating,
    JsonlEventStore,
    SurveySubmission,
    TurnEvent,
    compute_sus,
)

# ── compute_sus ───────────────────────────────────────────────────────────────


def test_sus_all_max_score():
    # Odd items = 5, even items = 1 → maximum score = 100
    responses = [5, 1, 5, 1, 5, 1, 5, 1, 5, 1]
    assert compute_sus(responses) == 100.0


def test_sus_all_min_score():
    # Odd items = 1, even items = 5 → minimum score = 0
    responses = [1, 5, 1, 5, 1, 5, 1, 5, 1, 5]
    assert compute_sus(responses) == 0.0


def test_sus_mid_score():
    # All 3s -> each odd: 3-1=2, each even: 5-3=2; total=20, x2.5=50
    responses = [3] * 10
    assert compute_sus(responses) == 50.0


def test_sus_wrong_length():
    with pytest.raises(ValueError, match="10 responses"):
        compute_sus([3, 3, 3])


def test_sus_typical():
    # [4,1,4,1,4,1,4,1,4,1]: odd=3 each x5=15, even=4 each x5=20, total=35*2.5=87.5
    responses = [4, 1, 4, 1, 4, 1, 4, 1, 4, 1]
    assert compute_sus(responses) == pytest.approx(87.5)


# ── JsonlEventStore ───────────────────────────────────────────────────────────


@pytest.fixture()
def store(tmp_path):
    return JsonlEventStore(root=tmp_path / "events")


def _turn(user_id="u1", session_id="s1") -> TurnEvent:
    return TurnEvent(
        session_id=session_id,
        user_id=user_id,
        timestamp="2026-06-09T10:00:00Z",
        query="test query",
        mode="research",
        intent="summarize",
        agents_triggered=["research", "ui_agent"],
        latency_ms=320.5,
        block_types=["CitedSummary"],
        retrieved_chunk_count=5,
    )


def _feedback(user_id="u1") -> FeedbackRating:
    return FeedbackRating(
        session_id="s1",
        block_id="b1",
        user_id=user_id,
        rating="up",
        block_type="CitedSummary",
        timestamp="2026-06-09T10:00:05Z",
    )


def _survey(user_id="u1") -> SurveySubmission:
    return SurveySubmission(
        session_id="s1",
        user_id=user_id,
        timestamp="2026-06-09T10:01:00Z",
        responses=[4, 1, 4, 1, 4, 1, 4, 1, 4, 1],
        sus_score=90.0,
        task_description="research task",
    )


@pytest.mark.asyncio
async def test_append_and_export_user(store):
    await store.append_turn(_turn())
    await store.append_feedback(_feedback())
    await store.append_survey(_survey())

    result = await store.export_user("u1")
    assert len(result["turns"]) == 1
    assert len(result["feedback"]) == 1
    assert len(result["surveys"]) == 1
    assert result["turns"][0]["query"] == "test query"
    assert result["feedback"][0]["rating"] == "up"
    assert result["surveys"][0]["sus_score"] == 90.0


@pytest.mark.asyncio
async def test_export_user_empty(store):
    result = await store.export_user("nobody")
    assert result == {"turns": [], "feedback": [], "surveys": [], "events": []}


@pytest.mark.asyncio
async def test_export_all_multi_user(store):
    await store.append_turn(_turn(user_id="alice"))
    await store.append_turn(_turn(user_id="bob"))
    await store.append_turn(_turn(user_id="alice"))

    result = await store.export_all()
    assert set(result.keys()) == {"alice", "bob"}
    assert len(result["alice"]["turns"]) == 2
    assert len(result["bob"]["turns"]) == 1


@pytest.mark.asyncio
async def test_export_all_empty_root(store):
    result = await store.export_all()
    assert result == {}


@pytest.mark.asyncio
async def test_turns_accumulate(store):
    for i in range(5):
        t = TurnEvent(
            session_id="s1",
            user_id="u1",
            timestamp=f"2026-06-09T10:0{i}:00Z",
            query=f"query {i}",
            mode="research",
            intent="summarize",
        )
        await store.append_turn(t)
    result = await store.export_user("u1")
    assert len(result["turns"]) == 5


@pytest.mark.asyncio
async def test_user_isolation(store):
    await store.append_turn(_turn(user_id="alice"))
    await store.append_feedback(_feedback(user_id="bob"))

    alice = await store.export_user("alice")
    bob = await store.export_user("bob")

    assert len(alice["turns"]) == 1
    assert len(alice["feedback"]) == 0
    assert len(bob["turns"]) == 0
    assert len(bob["feedback"]) == 1


# ── ActivityEvent (§20 generic capture, FR-ANL) ───────────────────────────────


async def test_append_event_persists_and_exports(tmp_path):
    from datetime import UTC, datetime

    from api.analytics.event_store import ActivityEvent

    store = JsonlEventStore(root=tmp_path)
    await store.append_event(
        ActivityEvent(
            user_id="u1",
            timestamp=datetime.now(UTC).isoformat(),
            category="ingestion",
            action="document_added",
            payload={"doc_id": "doc_a", "source": "pdf"},
        )
    )

    exported = await store.export_user("u1")
    assert "events" in exported
    assert len(exported["events"]) == 1
    ev = exported["events"][0]
    assert ev["category"] == "ingestion"
    assert ev["action"] == "document_added"
    assert ev["payload"]["doc_id"] == "doc_a"

    # export_all also carries the new stream.
    all_export = await store.export_all()
    assert all_export["u1"]["events"][0]["action"] == "document_added"
