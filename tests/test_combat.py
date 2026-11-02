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
    bootstrap_slice,
    margin_result,
    preview,
    unit_symbol,
    unit_trade,
)
from tft.environment import Player, RoundId, Unit
from tft.items import Component, craft
from tft.market import Bar, MarketPack, Series
from tft.roster import champion
from tft.rules import DEFAULT_RULES, Rules
from tft.strategies import Params

ROUND = RoundId.make(2, 2)


def rising_pack() -> MarketPack:
    dates = tuple(f"2026-02-{day:02d}" for day in range(1, 13))
    up = Series("UP", tuple(Bar(100 + i, 101.5 + i, 99 + i, 101 + i, 1) for i in range(12)))
    down = Series("DOWN", tuple(Bar(100 - i, 100.5 - i, 98 - i, 99 - i, 1) for i in range(12)))
    origins: dict[str, tuple[str, ...]] = {
        "Equities": ("UP",),
        "Commodities": ("UP",),
        "Bonds": ("UP",),
        "Tech": ("DOWN",),
    }
    return MarketPack("rising", "1d", "test", dates, origins, {"UP": up, "DOWN": down})


def seat(name: str, *units: Unit) -> Player:
    player = Player(name, level=9)
    player.board = list(units)
    return player


def test_margin_result_handles_ties_and_negative_scores() -> None:
    home, away = seat("h", Unit(champion("Pip Squeak"))), seat("a", Unit(champion("Index Drone")))
    assert margin_result(home, away, 1.0, 1.0).is_draw
    close = margin_result(home, away, -1.0, -3.0)
    assert (close.winner, close.loser, close.survivors) == ("h", "a", 1)
    assert margin_result(home, away, 0.0, 0.0).is_draw


def test_power_resolver_with_context() -> None:
    strong = seat("s", Unit(champion("Breakout Bull")), Unit(champion("Gap Gazelle")))
    weak = seat("w", Unit(champion("Pip Squeak")))
    result = PowerResolver().resolve(strong, weak, Random(0), CombatContext(ROUND))
    assert result.winner == "s"


def test_unit_symbol_cycles_through_the_origin() -> None:
    pack = rising_pack()
    assert unit_symbol(pack, "Equities", 0) == "UP"
    assert unit_symbol(pack, "Equities", 5) == "UP"
    assert unit_symbol(pack, "Crypto", 1) == "UP"


def test_unit_trade_scales_with_stars_and_items() -> None:
    pack = rising_pack()
    bars = pack.window(0, 10).bars["UP"]
    params = Params.from_rules(DEFAULT_RULES)
    one = Unit(champion("Barrel Bo"))
    two = Unit(champion("Barrel Bo"), star=2)
    _, one_score = unit_trade(one, bars, params, DEFAULT_RULES)
    _, two_score = unit_trade(two, bars, params, DEFAULT_RULES)
    assert one_score > 0
    assert two_score == pytest.approx(one_score * 1.8)
    sized = Unit(
        champion("Barrel Bo"), items=[craft(Component.VOLUME_FILTER, Component.VOLUME_FILTER)]
    )
    assert unit_trade(sized, bars, params, DEFAULT_RULES)[1] == pytest.approx(one_score * 1.3)


def test_board_score_and_market_resolver() -> None:
    pack = rising_pack()
    window = pack.window(0, 10)
    bull = seat("bull", Unit(champion("Barrel Bo")), Unit(champion("Coupon Clerk")))
    bear = seat("bear", Unit(champion("Vol Vampire")))
    assert board_score(bull, window, pack, DEFAULT_RULES) > 0
    assert board_score(bear, window, pack, DEFAULT_RULES) < 0
    resolver = MarketResolver(pack)
    result = resolver.resolve(bull, bear, Random(0), CombatContext(ROUND, window))
    assert result.winner == "bull"
    assert 1 <= result.survivors <= 2
    with pytest.raises(ValueError, match="needs the round's slice"):
        resolver.resolve(bull, bear, Random(0), CombatContext(ROUND))


def test_emblems_count_toward_traits_and_bonuses() -> None:
    drone = Unit(
        champion("Index Drone"), items=[craft(Component.PROSPECTUS, Component.LIMIT_ORDER)]
    )
    assert drone.traits == ("Equities", "Quant", "Tech")
    player = seat("p", drone, Unit(champion("Candle Reader")))
    assert player.bonus_percent == 15


def test_bootstrap_slice_and_preview_are_deterministic() -> None:
    pack = rising_pack()
    first = bootstrap_slice(pack, Random(5), 6)
    second = bootstrap_slice(pack, Random(5), 6)
    assert first.bars == second.bars
    assert first.start == -1
    assert len(first.dates) == 6
    assert all(bar.high >= bar.low for bars in first.bars.values() for bar in bars)
    with pytest.raises(ValueError, match="at least two bars"):
        bootstrap_slice(pack, Random(1), 1)
    rules = Rules(preview_samples=20, slice_bars=5)
    bull = seat("bull", Unit(champion("Barrel Bo")))
    bear = seat("bear", Unit(champion("Candle Reader")))
    odds = preview(bull, bear, pack, rules, Random(9))
    assert 0.0 <= odds <= 1.0
    assert odds == preview(bull, bear, pack, rules, Random(9))
    assert preview(bull, bull, pack, rules, Random(9)) == 0.5
    assert CombatResult(None, None, 0).is_draw


def test_craft_and_strategies_reject_bad_inputs() -> None:
    from tft.items import craft  # noqa: PLC0415
    from tft.strategies import bracket, scalp  # noqa: PLC0415

    with pytest.raises(ValueError, match="two components"):
        craft("Stop Order", "Nope")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="needs a bar"):
        bracket([], 0, Params.from_rules(DEFAULT_RULES))
    with pytest.raises(ValueError, match="at least one bar"):
        scalp([], Params.from_rules(DEFAULT_RULES))
