"""Tests for :mod:`tft.economy`."""

from __future__ import annotations

import pytest

from tft import economy
from tft.economy import interest, round_income, rounds_to_reach, streak_bonus


@pytest.mark.parametrize(
    ("gold", "expected"),
    [(0, 0), (9, 0), (10, 1), (19, 1), (20, 2), (49, 4), (50, 5), (51, 5), (1000, 5)],
)
def test_interest_table(gold: int, expected: int) -> None:
    assert interest(gold) == expected


def test_interest_rejects_negative_gold() -> None:
    with pytest.raises(ValueError, match="negative"):
        interest(-1)


@pytest.mark.parametrize(
    ("streak", "expected"),
    [(0, 0), (1, 0), (2, 1), (3, 1), (4, 2), (5, 3), (9, 3), (-1, 0), (-2, 1), (-5, 3)],
)
def test_streak_bonus_table(streak: int, expected: int) -> None:
    assert streak_bonus(streak) == expected


def test_streak_bonus_never_exceeds_the_cap() -> None:
    assert all(0 <= streak_bonus(streak) <= economy.MAX_STREAK_BONUS for streak in range(-30, 31))


def test_round_income_adds_the_three_components() -> None:
    assert round_income(50, 5) == economy.BASE_INCOME + 5 + 3
    assert round_income(0) == economy.BASE_INCOME
    assert round_income(30, -4, base=0) == 3 + 2


def test_round_income_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError, match="base"):
        round_income(10, base=-1)
    with pytest.raises(ValueError, match="gold"):
        round_income(-10)


def test_rounds_to_reach_counts_rounds() -> None:
    assert rounds_to_reach(50, 50) == 0
    assert rounds_to_reach(50, 0) == 8
    assert rounds_to_reach(50, 0, streak=5) < rounds_to_reach(50, 0)


def test_rounds_to_reach_gives_up_at_the_bound() -> None:
    assert rounds_to_reach(10**6, 0, max_rounds=5) == -1


def test_rounds_to_reach_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError, match="negative"):
        rounds_to_reach(-1, 0)
    with pytest.raises(ValueError, match="negative"):
        rounds_to_reach(10, 0, max_rounds=-1)
