"""Tests for :mod:`tft.roster`."""

from __future__ import annotations

import pytest

from tft import roster
from tft.roster import (
    CHAMPIONS,
    TRAITS,
    Champion,
    Trait,
    TraitKind,
    active_traits,
    champion,
    champions_of_cost,
    synergy_bonus,
    trait_counts,
    validate_roster,
)


def test_the_roster_is_valid_and_sized_for_a_set() -> None:
    validate_roster()
    assert len(CHAMPIONS) == 25
    assert all(len(champions_of_cost(cost)) >= 3 for cost in range(1, 6))
    assert len({unit.name for unit in CHAMPIONS}) == len(CHAMPIONS)


def test_every_origin_and_class_is_used_by_a_champion() -> None:
    used = {trait for unit in CHAMPIONS for trait in unit.traits}
    assert used == set(TRAITS)


def test_power_follows_the_cost_tier() -> None:
    assert [champions_of_cost(cost)[0].power for cost in range(1, 6)] == [10, 14, 20, 28, 40]


def test_trait_tiers_and_bonuses() -> None:
    trait = Trait("Test", TraitKind.ORIGIN, "A trait.", (2, 4), (10, 30))
    assert [trait.tier(count) for count in (0, 1, 2, 3, 4, 9)] == [0, 0, 1, 1, 2, 2]
    assert [trait.bonus(count) for count in (1, 2, 4)] == [0, 10, 30]


@pytest.mark.parametrize(
    ("breakpoints", "bonuses"),
    [((), ()), ((4, 2), (1, 2)), ((2, 2), (1, 2)), ((2, 4), (10,))],
)
def test_trait_rejects_bad_tables(breakpoints: tuple[int, ...], bonuses: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="trait"):
        Trait("Broken", TraitKind.CLASS, "Broken.", breakpoints, bonuses)


@pytest.mark.parametrize(("cost", "power"), [(0, 10), (6, 10), (1, 0), (1, -5)])
def test_champion_rejects_bad_cost_or_power(cost: int, power: int) -> None:
    with pytest.raises(ValueError, match="champion"):
        Champion("Broken", cost, "Equities", "Quant", "Nothing", "Does nothing.", power)


def test_champion_lookup() -> None:
    assert champion("Breakout Bull").traits == ("Equities", "Momentum")
    with pytest.raises(KeyError, match="no champion"):
        champion("Nobody")


def test_champions_of_cost_rejects_bad_costs() -> None:
    with pytest.raises(ValueError, match="cost"):
        champions_of_cost(7)


def test_trait_counts_count_distinct_champions_only() -> None:
    pip = champion("Pip Squeak")
    counts = trait_counts([pip, pip, champion("Index Drone")])
    assert counts == {"Forex": 1, "Scalper": 1, "Equities": 1, "Quant": 1}


def test_active_traits_and_synergy_bonus() -> None:
    board = [champion("Index Drone"), champion("Gap Gazelle"), champion("Whale Watcher")]
    assert active_traits(board) == {"Equities": 1, "Whale": 1}
    expected = TRAITS["Equities"].bonus(2) + TRAITS["Whale"].bonus(1)
    assert synergy_bonus(board) == expected
    assert synergy_bonus([]) == 0


def test_validate_roster_reports_problems() -> None:
    duplicate = (champion("Pip Squeak"), champion("Pip Squeak"))
    with pytest.raises(ValueError, match="unique"):
        validate_roster(duplicate)
    bad_origin = (Champion("X", 1, "Nowhere", "Quant", "A", "B", 10),)
    with pytest.raises(ValueError, match="origin"):
        validate_roster(bad_origin)
    bad_class = (Champion("X", 1, "Equities", "Equities", "A", "B", 10),)
    with pytest.raises(ValueError, match="class"):
        validate_roster(bad_class)
    with pytest.raises(ValueError, match="cost tiers"):
        validate_roster(champions_of_cost(1))


def test_module_constants_are_consistent() -> None:
    assert roster.MIN_COST == 1
    assert roster.MAX_COST == 5
    assert set(roster.BASE_POWER) == set(range(1, 6))
