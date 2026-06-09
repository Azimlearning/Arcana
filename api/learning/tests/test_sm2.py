"""SM-2 algorithm unit tests — FR-LRN-02."""

from __future__ import annotations

from datetime import date

import pytest

from api.learning.sm2 import (
    _EASE_DEFAULT,
    _EASE_MIN,
    ScheduleState,
    advance,
    from_wire,
    initial_state,
    is_due,
    to_wire,
)

_TODAY = date(2026, 6, 9)


# ── initial_state ─────────────────────────────────────────────────────────────


def test_initial_state_uses_provided_date():
    s = initial_state(_TODAY)
    assert s.due_at == "2026-06-09"
    assert s.ease_factor == _EASE_DEFAULT
    assert s.repetitions == 0
    assert s.interval == 0


# ── advance — fail branch (rating 0-2) ────────────────────────────────────────


@pytest.mark.parametrize("rating", [0, 1, 2])
def test_fail_resets_repetitions(rating: int):
    s = initial_state(_TODAY)
    next_s = advance(s, rating, today=_TODAY)
    assert next_s.repetitions == 0


@pytest.mark.parametrize("rating", [0, 1, 2])
def test_fail_sets_interval_to_1(rating: int):
    s = ScheduleState(due_at="2026-06-09", interval=10, ease_factor=2.5, repetitions=5)
    next_s = advance(s, rating, today=_TODAY)
    assert next_s.interval == 1


def test_fail_due_at_is_tomorrow():
    s = initial_state(_TODAY)
    next_s = advance(s, 0, today=_TODAY)
    assert next_s.due_at == "2026-06-10"


def test_fail_lowers_ease_factor():
    s = initial_state(_TODAY)
    next_s = advance(s, 0, today=_TODAY)
    assert next_s.ease_factor < _EASE_DEFAULT


def test_ease_never_drops_below_minimum():
    s = ScheduleState(due_at="2026-06-09", interval=1, ease_factor=_EASE_MIN, repetitions=0)
    next_s = advance(s, 0, today=_TODAY)
    assert next_s.ease_factor >= _EASE_MIN


# ── advance — pass branch (rating 3-5) ────────────────────────────────────────


def test_first_pass_interval_is_1():
    s = initial_state(_TODAY)
    next_s = advance(s, 4, today=_TODAY)
    assert next_s.interval == 1
    assert next_s.repetitions == 1


def test_second_pass_interval_is_6():
    # Simulate first pass.
    s = initial_state(_TODAY)
    s1 = advance(s, 4, today=_TODAY)
    s2 = advance(s1, 4, today=_TODAY)
    assert s2.interval == 6
    assert s2.repetitions == 2


def test_third_pass_grows_by_ease_factor():
    s = ScheduleState(due_at="2026-06-09", interval=6, ease_factor=2.5, repetitions=2)
    next_s = advance(s, 4, today=_TODAY)
    # interval = round(6 * ease_factor_after_rating4)
    # ease after rating=4: 2.5 + 0.1 - 1*(0.08 + 1*0.02) = 2.5 + 0.1 - 0.1 = 2.5
    assert next_s.interval == round(6 * 2.5)
    assert next_s.repetitions == 3


def test_perfect_rating_raises_ease():
    s = initial_state(_TODAY)
    next_s = advance(s, 5, today=_TODAY)
    assert next_s.ease_factor > _EASE_DEFAULT


def test_hard_rating_lowers_ease_but_passes():
    s = initial_state(_TODAY)
    next_s = advance(s, 3, today=_TODAY)
    assert next_s.ease_factor < _EASE_DEFAULT
    assert next_s.repetitions == 1  # still a pass


def test_invalid_rating_raises():
    s = initial_state(_TODAY)
    with pytest.raises(ValueError):
        advance(s, 6, today=_TODAY)
    with pytest.raises(ValueError):
        advance(s, -1, today=_TODAY)


def test_none_state_treated_as_new_card():
    next_s = advance(None, 4, today=_TODAY)
    assert next_s.repetitions == 1
    assert next_s.interval == 1


# ── is_due ────────────────────────────────────────────────────────────────────


def test_is_due_when_today():
    s = ScheduleState(due_at="2026-06-09", interval=1, ease_factor=2.5, repetitions=0)
    assert is_due(s, _TODAY) is True


def test_not_due_when_future():
    s = ScheduleState(due_at="2026-06-15", interval=6, ease_factor=2.5, repetitions=1)
    assert is_due(s, _TODAY) is False


def test_is_due_when_past():
    s = ScheduleState(due_at="2026-06-01", interval=6, ease_factor=2.5, repetitions=1)
    assert is_due(s, _TODAY) is True


def test_corrupt_due_at_treated_as_due():
    s = ScheduleState(due_at="not-a-date", interval=1, ease_factor=2.5, repetitions=0)
    assert is_due(s, _TODAY) is True


# ── to_wire / from_wire ───────────────────────────────────────────────────────


def test_to_wire_produces_camel_keys():
    s = ScheduleState(due_at="2026-06-09", interval=6, ease_factor=2.3, repetitions=2)
    w = to_wire(s)
    assert w == {"dueAt": "2026-06-09", "interval": 6, "easeFactor": 2.3, "repetitions": 2}


def test_from_wire_round_trips():
    original = ScheduleState(due_at="2026-06-09", interval=6, ease_factor=2.3, repetitions=2)
    assert from_wire(to_wire(original)) == original


def test_from_wire_handles_missing_keys():
    s = from_wire({})
    assert s.ease_factor == _EASE_DEFAULT
    assert s.repetitions == 0
    assert s.interval == 0
