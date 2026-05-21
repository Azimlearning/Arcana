"""Tests for api.core.budget — hop + token accounting."""

from __future__ import annotations

import pytest

from api.core.budget import TokenBudget


def test_default_within_limits():
    b = TokenBudget()
    assert not b.exceeded
    assert b.tokens_used == 0 and b.hops_used == 0
    assert b.remaining_hops() == b.hops_limit
    assert b.remaining_tokens() == b.tokens_limit


def test_charge_hop_until_exceeded():
    b = TokenBudget(hops_limit=3)
    b.charge_hop()
    b.charge_hop()
    assert b.hops_used == 2
    assert not b.exceeded
    b.charge_hop()
    assert b.hops_exceeded
    assert b.exceeded


def test_charge_tokens_until_exceeded():
    b = TokenBudget(tokens_limit=100)
    b.charge_tokens(50)
    assert not b.exceeded
    b.charge_tokens(60)
    assert b.tokens_exceeded
    assert b.exceeded


def test_charge_tokens_rejects_negative():
    b = TokenBudget()
    with pytest.raises(ValueError):
        b.charge_tokens(-1)


def test_remaining_helpers_clamp_at_zero():
    b = TokenBudget(tokens_limit=10, hops_limit=2)
    b.charge_tokens(25)
    b.charge_hop()
    b.charge_hop()
    b.charge_hop()
    assert b.remaining_tokens() == 0
    assert b.remaining_hops() == 0
