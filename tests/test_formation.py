"""Tests for :mod:`tft.formation`."""

from __future__ import annotations

import pytest

from tft.errors import Refusal
from tft.formation import (
    check_cell,
    column_order,
    default_cell,
    is_back_half,
    is_covered,
    position_effect,
    preferred_row,
    row_order,
)
from tft.rules import DEFAULT_RULES, Rules


def test_check_cell_accepts_the_grid_and_refuses_the_rest() -> None:
    check_cell((0, 0))
    check_cell((3, 6))
    for cell in ((-1, 0), (4, 0), (0, 7), (0, -1)):
        with pytest.raises(Refusal, match="rows 0 to 3 and columns 0 to 6"):
            check_cell(cell)


def test_column_order_runs_from_the_centre_outwards() -> None:
    assert column_order(7) == (3, 2, 4, 1, 5, 0, 6)
    assert column_order(2) == (1, 0)
    assert column_order(1) == (0,)


def test_preferred_rows_put_hedges_in_front_and_carries_at_the_back() -> None:
    assert preferred_row("Hedger") == 0
    assert preferred_row("Arbitrageur") == 0
    assert preferred_row("Swing") == 1
    assert preferred_row("Momentum") == 3
    assert preferred_row("Whale") == 3
    assert preferred_row("Swing", Rules(board_rows=1, row_size_percent=(100,), row_shield_percent=(0,), max_level=7,
        shop_odds={level: DEFAULT_RULES.shop_odds[level] for level in range(1, 8)},
        xp_to_next_level={level: DEFAULT_RULES.xp_to_next_level[level] for level in range(1, 7)})) == 0


def test_row_order_prefers_the_row_then_its_neighbours_back_first() -> None:
    assert row_order(0, 4) == (0, 1, 2, 3)
    assert row_order(3, 4) == (3, 2, 1, 0)
    assert row_order(1, 4) == (1, 2, 0, 3)


def test_default_cell_fills_the_preferred_row_then_spills_over() -> None:
    assert default_cell("Hedger", set()) == (0, 3)
    assert default_cell("Momentum", {(3, 3)}) == (3, 2)
    front_row = {(0, column) for column in range(7)}
    assert default_cell("Hedger", front_row) == (1, 3)
    everything = {(row, column) for row in range(4) for column in range(7)}
    with pytest.raises(Refusal, match="no free cell"):
        default_cell("Hedger", everything)


def test_cover_and_back_half() -> None:
    assert is_back_half((2, 0))
    assert is_back_half((3, 6))
    assert not is_back_half((1, 0))
    assert is_covered((3, 2), {(0, 2)})
    assert is_covered((2, 2), {(1, 2), (3, 2)})
    assert not is_covered((3, 2), {(0, 3), (3, 2)})
    assert not is_covered((0, 2), {(3, 2)})


def test_position_effect_by_row_and_cover() -> None:
    front = position_effect((0, 3), set())
    assert (front.size_percent, front.shield_percent) == (-20, 30)
    middle = position_effect((1, 3), set())
    assert (middle.size_percent, middle.shield_percent) == (-10, 15)
    exposed = position_effect((3, 3), {(3, 3)})
    assert (exposed.size_percent, exposed.shield_percent) == (20, -25)
    covered = position_effect((3, 3), {(3, 3), (0, 3)})
    assert (covered.size_percent, covered.shield_percent) == (20, 25)
    third_row = position_effect((2, 1), {(1, 1)})
    assert (third_row.size_percent, third_row.shield_percent) == (0, 25)
    with pytest.raises(Refusal, match="rows"):
        position_effect((9, 9), set())


def test_position_effect_follows_the_rules() -> None:
    rules = Rules(row_size_percent=(50, 60, 70, 150), cover_shield_percent=10, exposed_penalty_percent=40)
    assert position_effect((3, 0), set(), rules).shield_percent == -40
    assert position_effect((3, 0), {(1, 0)}, rules).shield_percent == 10
    assert position_effect((3, 0), set(), rules).size_percent == 50
