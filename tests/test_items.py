"""Tests for :mod:`tft.items`."""

from __future__ import annotations

from itertools import combinations_with_replacement

from tft.items import (
    COMPONENT_EFFECTS,
    EMBLEMS,
    ITEM_NAMES,
    Component,
    Effect,
    combined_effect,
    craft,
)


def test_every_pair_crafts_a_uniquely_named_item() -> None:
    names = {craft(a, b).name for a, b in combinations_with_replacement(Component, 2)}
    assert len(names) == 36
    assert len(ITEM_NAMES) == 29
    assert craft(Component.STOP_ORDER, Component.LIMIT_ORDER).name == "Bracket Order"
    assert craft(Component.LIMIT_ORDER, Component.STOP_ORDER).name == "Bracket Order"
    assert craft(Component.STOP_ORDER, Component.STOP_ORDER).name == "Trailing Stop"


def test_effects_add_up() -> None:
    bracket = craft(Component.STOP_ORDER, Component.LIMIT_ORDER).effect
    assert (bracket.stop_tenths, bracket.target_tenths) == (8, 13)
    war_chest = craft(Component.CASH_BUFFER, Component.CASH_BUFFER).effect
    assert (war_chest.size_percent, war_chest.shield_percent) == (-20, 70)
    assert Effect().combine(Effect()) == Effect()


def test_prospectus_makes_emblems_and_the_index_fund() -> None:
    emblem = craft(Component.PROSPECTUS, Component.HEDGE_TICKET)
    assert emblem.name == "Bonds Emblem"
    assert emblem.effect.trait == "Bonds"
    assert emblem.effect.shield_percent == COMPONENT_EFFECTS[Component.HEDGE_TICKET].shield_percent
    fund = craft(Component.PROSPECTUS, Component.PROSPECTUS)
    assert fund.name == "Index Fund"
    assert fund.effect.extra_slots == 1
    assert set(EMBLEMS) == set(Component) - {Component.PROSPECTUS}


def test_combined_effect_of_several_items() -> None:
    items = [
        craft(Component.VOLUME_FILTER, Component.MARGIN_NOTE),
        craft(Component.PROSPECTUS, Component.STOP_ORDER),
    ]
    total = combined_effect(items)
    assert total.size_percent == 55
    assert total.stop_tenths == 8
    assert total.trait == "Equities"
    assert combined_effect([]) == Effect()
