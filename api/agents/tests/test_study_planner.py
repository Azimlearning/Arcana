"""StudyPlannerAgent — Pomodoro plan sizing (FR-LRN-09)."""

from __future__ import annotations

from api.agents.tier4.study_planner import _build_pomodoro


def test_pomodoro_is_none_for_empty_queue():
    assert _build_pomodoro(0, 10) is None


def test_pomodoro_cycles_cover_session_workload():
    # 8 due, goal 10 -> workload 8 -> ceil(8/5) = 2 cycles.
    plan = _build_pomodoro(8, 10)
    assert plan is not None
    assert plan["cycles"] == 2
    assert plan["focusMinutes"] == 25
    assert plan["breakMinutes"] == 5
    assert plan["cardsPerCycle"] == 5


def test_pomodoro_capped_by_session_goal():
    # 100 due but goal 10 -> workload capped at 10 -> ceil(10/5) = 2 cycles.
    plan = _build_pomodoro(100, 10)
    assert plan is not None
    assert plan["cycles"] == 2


def test_pomodoro_minimum_one_cycle():
    plan = _build_pomodoro(1, 10)
    assert plan is not None
    assert plan["cycles"] == 1
