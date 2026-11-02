"""Tests for :mod:`tft.strategies`."""

from __future__ import annotations

import pytest

from tft.market import Bar
from tft.rules import DEFAULT_RULES, Rules
from tft.strategies import (
    FLAT,
    STRATEGIES,
    Params,
    arbitrage,
    bracket,
    breakout,
    hedged,
    hold,
    path_drawdown,
    quant,
    reversion,
    scalp,
    strategy_for,
    whale,
)

PARAMS = Params.from_rules(DEFAULT_RULES)


def closes(*values: float) -> list[Bar]:
    return [Bar.from_close(value) for value in values]


RISING = closes(100, 101, 102, 104, 106, 108, 110)
FALLING = closes(100, 99, 97, 95, 93, 92, 90)
DIP = closes(100, 100, 99, 96, 97, 99, 101)


def test_params_from_rules_and_scaling() -> None:
    assert PARAMS.stop == 2.0
    assert PARAMS.leverage == 2.0
    scaled = PARAMS.scaled(8, 13)
    assert (scaled.stop, scaled.target) == (1.6, 5.2)
    assert Params.from_rules(Rules(stop_percent=3)).stop == 3.0


def test_path_drawdown() -> None:
    assert path_drawdown([100, 110, 99, 120]) == pytest.approx(10.0)
    assert path_drawdown([]) == 0.0
    assert path_drawdown([5, 6, 7]) == 0.0


def test_hold_captures_the_move() -> None:
    outcome = hold(RISING, PARAMS)
    assert outcome.pnl == pytest.approx(10.0 - 0.05)
    assert outcome.drawdown == 0.0
    assert outcome.trades == 1
    assert hold(FALLING, PARAMS).pnl < 0
    with pytest.raises(ValueError, match="at least one bar"):
        hold([], PARAMS)


def test_bracket_exits_at_target_stop_or_end() -> None:
    target = bracket(RISING, 0, PARAMS)
    assert target.pnl == pytest.approx(4.0 - 0.05)
    stop = bracket(FALLING, 0, PARAMS)
    assert stop.pnl == pytest.approx(-3.0 - 0.05)
    assert stop.drawdown >= 3.0
    gap = bracket(closes(100, 90), 0, PARAMS)
    assert gap.pnl < -5
    end = bracket(closes(100, 101, 101.5), 0, PARAMS)
    assert end.pnl == pytest.approx(1.5 - 0.05)


def test_breakout_needs_a_new_high() -> None:
    assert breakout(RISING, PARAMS).pnl > 0
    assert breakout(FALLING, PARAMS) == FLAT
    assert breakout(closes(100), PARAMS) == FLAT


def test_reversion_buys_the_dip() -> None:
    outcome = reversion(DIP, PARAMS)
    assert outcome.trades == 1
    assert outcome.pnl > 0
    assert reversion(RISING, PARAMS) == FLAT


def test_scalp_trades_every_bar() -> None:
    outcome = scalp(RISING, PARAMS)
    assert outcome.trades == len(RISING) - 2
    assert outcome.pnl > 0
    assert scalp(closes(100, 101, 99, 102, 98), PARAMS).pnl < 0


def test_hedged_floors_the_loss() -> None:
    outcome = hedged(FALLING, PARAMS)
    assert outcome.pnl == pytest.approx(-2.0 - 0.5)
    assert outcome.drawdown <= 2.5
    assert hedged(RISING, PARAMS).pnl == pytest.approx(10.0 - 0.05 - 0.5)


def test_arbitrage_and_quant_and_whale() -> None:
    arb = arbitrage(FALLING, PARAMS)
    assert arb.trades == 6
    assert arb.pnl > 0
    combined = quant(RISING, PARAMS)
    assert combined.trades == 1
    assert combined.pnl == pytest.approx(breakout(RISING, PARAMS).pnl / 2)
    big = whale(RISING, PARAMS)
    assert big.pnl == pytest.approx((10.0 - 0.05) * 2 - 0.1)
    assert whale(FALLING, PARAMS).drawdown == pytest.approx(
        min(100, hold(FALLING, PARAMS).drawdown * 2)
    )


def test_every_class_has_a_strategy() -> None:
    assert set(STRATEGIES) == {
        "Swing",
        "Momentum",
        "Contrarian",
        "Scalper",
        "Hedger",
        "Arbitrageur",
        "Quant",
        "Whale",
    }
    assert strategy_for("Swing") is hold
    with pytest.raises(ValueError, match="no strategy"):
        strategy_for("Banker")
