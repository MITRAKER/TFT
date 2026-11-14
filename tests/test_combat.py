"""Tests for :mod:`tft.combat`."""

from __future__ import annotations

from random import Random

import pytest

from tft.combat import (
    CombatContext,
    CombatResult,
    MarketResolver,
    PowerResolver,
    board_score,
    board_trades,
    bootstrap_slice,
    margin_result,
    points,
    preview,
    preview_field,
    trade_unit,
    unit_symbol,
)
from tft.environment import Player, RoundId, Unit
from tft.items import Component, craft
from tft.market import Bar, MarketPack, Series
from tft.roster import champion
from tft.rules import DEFAULT_RULES, Rules
from tft.strategies import Params, bracket, scalp

ROUND = RoundId.make(2, 2)
PARAMS = Params.from_rules(DEFAULT_RULES)
RISING: dict[str, tuple[str, ...]] = {
    "Equities": ("UP",),
    "Commodities": ("UP",),
    "Bonds": ("UP",),
    "Tech": ("DOWN",),
}
FALLING: dict[str, tuple[str, ...]] = {"Commodities": ("DOWN",), "Equities": ("UP", "DOWN")}


def make_pack(origins: dict[str, tuple[str, ...]] = RISING) -> MarketPack:
    dates = tuple(f"2026-02-{day:02d}" for day in range(1, 13))
    up = Series("UP", tuple(Bar(100 + i, 101.5 + i, 99 + i, 101 + i, 1) for i in range(12)))
    down = Series("DOWN", tuple(Bar(100 - i, 100.5 - i, 98 - i, 99 - i, 1) for i in range(12)))
    return MarketPack("test", "1d", "test", dates, origins, {"UP": up, "DOWN": down})


def seat(name: str, *units: Unit) -> Player:
    player = Player(name, level=9)
    player.board = list(units)
    return player


def placed(name: str, cell: tuple[int, int], star: int = 1) -> Unit:
    return Unit(champion(name), star, position=cell)


def test_margin_result_records_both_sides_and_handles_ties() -> None:
    home, away = seat("h", Unit(champion("Pip Squeak"))), seat("a", Unit(champion("Index Drone")))
    tie = margin_result(home, away, 1.0, 1.0)
    assert tie.is_draw
    assert (tie.home, tie.away, tie.home_score, tie.away_score) == ("h", "a", 1.0, 1.0)
    close = margin_result(home, away, -1.0, -3.0)
    assert (close.winner, close.loser, close.survivors) == ("h", "a", 1)
    assert margin_result(home, away, 0.0, 0.0).is_draw


def test_combat_result_knows_its_sides() -> None:
    result = CombatResult("h", "a", 2, "h", "a", 5.0, 3.0)
    assert result.involves("h")
    assert result.involves("a")
    assert not result.involves("z")
    assert result.opponent_of("h") == "a"
    assert result.opponent_of("a") == "h"
    assert result.opponent_of("z") is None
    assert (result.score_of("h"), result.score_of("a"), result.score_of("z")) == (5.0, 3.0, 0.0)
    legacy = CombatResult("h", "a", 1)
    assert legacy.opponent_of("a") == "h"
    draw = CombatResult(None, None, 0, "h", "a")
    assert draw.involves("a")
    assert draw.opponent_of("a") == "h"
    assert CombatResult(None, None, 0).opponent_of("h") is None


def test_power_resolver_compares_team_power() -> None:
    strong = seat("s", Unit(champion("Breakout Bull")), Unit(champion("Gap Gazelle")))
    weak = seat("w", Unit(champion("Pip Squeak")))
    result = PowerResolver().resolve(strong, weak, Random(0), CombatContext(ROUND))
    assert result.winner == "s"
    assert (result.home_score, result.away_score) == (strong.team_power, weak.team_power)


def test_the_column_picks_the_symbol() -> None:
    pack = make_pack(FALLING)
    assert unit_symbol(pack, "Equities", 0) == "UP"
    assert unit_symbol(pack, "Equities", 1) == "DOWN"
    assert unit_symbol(pack, "Equities", 2) == "UP"
    assert unit_symbol(pack, "Crypto", 1) == "UP"


def test_trade_unit_scales_with_stars_and_items() -> None:
    pack = make_pack()
    window = pack.window(0, 10)
    one = placed("Barrel Bo", (1, 3))
    two = placed("Barrel Bo", (1, 3), star=2)
    alone = seat("p", one)
    first = trade_unit(alone, one, window, pack, DEFAULT_RULES, PARAMS)
    assert first.symbol == "UP"
    assert first.cell == (1, 3)
    assert first.size == pytest.approx(0.9)
    assert first.score == pytest.approx(0.9 * 9.95)
    second = trade_unit(seat("p", two), two, window, pack, DEFAULT_RULES, PARAMS)
    assert second.score == pytest.approx(first.score * 1.8)
    block = craft(Component.VOLUME_FILTER, Component.VOLUME_FILTER)
    sized = Unit(champion("Barrel Bo"), items=[block], position=(1, 3))
    third = trade_unit(seat("p", sized), sized, window, pack, DEFAULT_RULES, PARAMS)
    assert third.size == pytest.approx(1.2)
    assert third.unit == "Barrel Bo 1* [Block Trade]"


def test_trade_unit_needs_a_cell() -> None:
    pack = make_pack()
    loose = Unit(champion("Barrel Bo"))
    with pytest.raises(ValueError, match="has no cell"):
        trade_unit(seat("p", loose), loose, pack.window(0, 10), pack, DEFAULT_RULES, PARAMS)


def test_the_row_and_cover_shape_a_losing_trade() -> None:
    pack = make_pack(FALLING)
    window = pack.window(0, 10)

    def score(cell: tuple[int, int], *others: Unit) -> float:
        unit = placed("Barrel Bo", cell)
        player = seat("p", unit, *others)
        return trade_unit(player, unit, window, pack, DEFAULT_RULES, PARAMS).score

    exposed = score((3, 0))
    covered = score((3, 0), placed("Coupon Clerk", (0, 0)))
    front = score((0, 0))
    assert exposed == pytest.approx(1.2 * (-10.05 - 0.5 * 12.5))
    assert covered == pytest.approx(1.2 * (-10.05 - 0.5 * 7.5))
    assert front == pytest.approx(0.8 * (-10.05 - 0.5 * 7.0))
    assert exposed < covered < front < 0


def test_board_trades_gives_every_unit_a_cell_and_a_line() -> None:
    pack = make_pack()
    player = seat("p", Unit(champion("Barrel Bo")), Unit(champion("Coupon Clerk")))
    trades = board_trades(player, pack.window(0, 10), pack, DEFAULT_RULES)
    assert [trade.champion for trade in trades] == ["Barrel Bo", "Coupon Clerk"]
    assert [unit.position for unit in player.board] == [(1, 3), (0, 3)]
    assert trades[0].outcome.marks == ((0, "buy"), (9, "sell"))


def test_board_score_and_market_resolver() -> None:
    pack = make_pack()
    window = pack.window(0, 10)
    bull = seat("bull", Unit(champion("Barrel Bo")), Unit(champion("Coupon Clerk")))
    bear = seat("bear", Unit(champion("Vol Vampire")))
    assert board_score(bull, window, pack, DEFAULT_RULES) > 0
    assert board_score(bear, window, pack, DEFAULT_RULES) < 0
    resolver = MarketResolver(pack)
    result = resolver.resolve(bull, bear, Random(0), CombatContext(ROUND, window))
    assert result.winner == "bull"
    assert 1 <= result.survivors <= 2
    assert result.score_of("bull") == board_score(bull, window, pack, DEFAULT_RULES)
    with pytest.raises(ValueError, match="needs the round's slice"):
        resolver.resolve(bull, bear, Random(0), CombatContext(ROUND))


def test_emblems_count_toward_traits_and_bonuses() -> None:
    emblem = craft(Component.PROSPECTUS, Component.LIMIT_ORDER)
    drone = Unit(champion("Index Drone"), items=[emblem])
    assert drone.traits == ("Equities", "Quant", "Tech")
    player = seat("p", drone, Unit(champion("Candle Reader")))
    assert player.bonus_percent == 15


def test_bootstrap_slices_are_deterministic_and_well_formed() -> None:
    pack = make_pack()
    first = bootstrap_slice(pack, Random(5), 6)
    second = bootstrap_slice(pack, Random(5), 6)
    assert first.bars == second.bars
    assert first.start == -1
    assert len(first.dates) == 6
    assert all(bar.high >= bar.low for bars in first.bars.values() for bar in bars)
    with pytest.raises(ValueError, match="at least two bars"):
        bootstrap_slice(pack, Random(1), 1)


def test_preview_odds() -> None:
    pack = make_pack()
    rules = Rules(preview_samples=20, slice_bars=5)
    bull = seat("bull", Unit(champion("Barrel Bo")))
    bear = seat("bear", Unit(champion("Vol Vampire")))
    odds = preview_field(bull, [bear, bull], pack, rules, Random(9))
    assert odds == preview_field(bull, [bear, bull], pack, rules, Random(9))
    assert 0.0 <= odds[0] <= 1.0
    assert odds[1] == 0.5
    assert preview(bull, bull, pack, rules, Random(9)) == 0.5
    assert preview_field(bull, [], pack, rules, Random(9)) == []
    assert (points(2, 1), points(1, 1), points(1, 2)) == (1.0, 0.5, 0.0)


def test_craft_and_strategies_reject_bad_inputs() -> None:
    with pytest.raises(ValueError, match="two components"):
        craft("Stop Order", "Nope")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="needs a bar"):
        bracket([], 0, PARAMS)
    with pytest.raises(ValueError, match="at least one bar"):
        scalp([], PARAMS)
