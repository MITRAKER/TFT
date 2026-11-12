"""Trading strategies: one per class, scored on a slice of bars.

Every strategy is a pure function of the bars and a :class:`Params`: it returns
the profit or loss in percent of the capital committed, the worst peak-to-trough
drawdown along the way, and the number of trades. The market resolver turns
those into combat scores. The rules are deliberately simple and legible; the
point is that a Momentum champion really does trade a breakout and a Hedger
really does cap its losses.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

from tft.market import Bar
from tft.rules import Rules

PERCENT = 100.0
BASIS_POINTS = 10_000.0
MIN_TARGET_PERCENT = 0.1


@dataclass(frozen=True)
class Params:
    """The knobs a strategy reads; items scale ``stop`` and ``target``."""

    stop: float
    target: float
    lookback: int
    reversion_threshold: float
    cost_bps: float
    hedge_floor: float
    hedge_premium: float
    leverage: float
    capture: float

    @classmethod
    def from_rules(cls, rules: Rules) -> Params:
        """Read the strategy knobs from a rule set."""
        return cls(
            stop=float(rules.stop_percent),
            target=float(rules.target_percent),
            lookback=rules.momentum_lookback,
            reversion_threshold=rules.reversion_threshold_tenths / 10,
            cost_bps=float(rules.trade_cost_bps),
            hedge_floor=float(rules.hedge_floor_percent),
            hedge_premium=rules.hedge_premium_tenths / 10,
            leverage=rules.whale_leverage_tenths / 10,
            capture=float(rules.arb_capture_percent),
        )

    def scaled(self, stop_tenths: int, target_tenths: int) -> Params:
        """Return a copy with the stop and target multiplied by tenths (items)."""
        return replace(
            self, stop=self.stop * stop_tenths / 10, target=self.target * target_tenths / 10
        )


Mark = tuple[int, str]
"""A bar of the slice and what the strategy did there: buy, sell, stop, target or close."""


@dataclass(frozen=True)
class Outcome:
    """What a strategy made on a slice: profit, worst drawdown, trades, and where it traded.

    Profit and drawdown are in percent of the capital committed. ``marks`` lists
    the entry and the exit of strategies that take one position; strategies that
    trade every bar leave it empty.
    """

    pnl: float
    drawdown: float
    trades: int
    marks: tuple[Mark, ...] = ()


Strategy = Callable[[Sequence[Bar], Params], Outcome]

FLAT = Outcome(0.0, 0.0, 0)


def require_bars(bars: Sequence[Bar]) -> None:
    """Check there is something to trade.

    Raises:
        ValueError: If the slice is empty.
    """
    if not bars:
        msg = "a strategy needs at least one bar"
        raise ValueError(msg)


def path_drawdown(values: Sequence[float]) -> float:
    """Return the largest peak-to-trough fall along ``values``, in percent of the peak."""
    peak = values[0] if values else 0.0
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = max(worst, (peak - value) / peak * PERCENT if peak > 0 else 0.0)
    return worst


def bracket_exit(
    bars: Sequence[Bar], start: int, stop_price: float, target_price: float
) -> tuple[float, int, str, float]:
    """Walk the bars after the entry: return the exit price, its bar, why, and the lowest low seen.

    A bar that touches both levels counts as the stop. A gap through the stop fills at the open.
    """
    worst = bars[start].close
    for index in range(start + 1, len(bars)):
        bar = bars[index]
        worst = min(worst, bar.low)
        if bar.low <= stop_price:
            return min(bar.open, stop_price), index, "stop", worst
        if bar.high >= target_price:
            return target_price, index, "target", worst
    return bars[-1].close, len(bars) - 1, "close", worst


def bracket(bars: Sequence[Bar], start: int, params: Params) -> Outcome:
    """Go long at bar ``start``'s close with a stop and a target; exit at the end at the latest.

    The drawdown is the worst excursion below the entry.

    Raises:
        ValueError: If ``start`` is not a bar of the slice.
    """
    if not 0 <= start < len(bars):
        msg = f"bracket needs a bar to enter on, got {start} of {len(bars)}"
        raise ValueError(msg)
    entry = bars[start].close
    stop_price = entry * (1 - params.stop / PERCENT)
    target_price = entry * (1 + params.target / PERCENT)
    exit_price, exit_bar, reason, worst = bracket_exit(bars, start, stop_price, target_price)
    pnl = (exit_price / entry - 1) * PERCENT - params.cost_bps / BASIS_POINTS * PERCENT
    drawdown = max(0.0, (entry - min(worst, exit_price)) / entry * PERCENT)
    return Outcome(pnl, drawdown, 1, ((start, "buy"), (exit_bar, reason)))


def hold(bars: Sequence[Bar], params: Params) -> Outcome:
    """Swing: buy the first open, sell the last close."""
    require_bars(bars)
    entry = bars[0].open
    closes = [bar.close for bar in bars]
    pnl = (closes[-1] / entry - 1) * PERCENT - params.cost_bps / BASIS_POINTS * PERCENT
    marks = ((0, "buy"), (len(bars) - 1, "sell"))
    return Outcome(pnl, path_drawdown([entry, *closes]), 1, marks)


def breakout(bars: Sequence[Bar], params: Params) -> Outcome:
    """Momentum: buy the first close above the opening range's high, with a bracket."""
    require_bars(bars)
    lookback = max(1, min(params.lookback, len(bars) - 1))
    level = max(bar.close for bar in bars[:lookback])
    for index in range(lookback, len(bars)):
        if bars[index].close > level:
            return bracket(bars, index, params)
    return FLAT


def reversion(bars: Sequence[Bar], params: Params) -> Outcome:
    """Contrarian: buy a close that falls below the running mean, aim back at the mean."""
    require_bars(bars)
    total = 0.0
    for index, bar in enumerate(bars):
        total += bar.close
        mean = total / (index + 1)
        if index > 0 and bar.close < mean * (1 - params.reversion_threshold / PERCENT):
            target = max(MIN_TARGET_PERCENT, (mean / bar.close - 1) * PERCENT)
            return bracket(bars, index, replace(params, target=target))
    return FLAT


def scalp(bars: Sequence[Bar], params: Params) -> Outcome:
    """Scalper: every bar, trade in the direction of the previous bar; pay costs every time.

    Raises:
        ValueError: If the slice is empty.
    """
    if not bars:
        msg = "a strategy needs at least one bar"
        raise ValueError(msg)
    closes = [bar.close for bar in bars]
    equity = 1.0
    path = [equity]
    trades = 0
    for index in range(2, len(closes)):
        direction = 1.0 if closes[index - 1] >= closes[index - 2] else -1.0
        move = closes[index] / closes[index - 1] - 1
        equity *= 1 + direction * move - params.cost_bps / BASIS_POINTS
        path.append(equity)
        trades += 1
    return Outcome((equity - 1) * PERCENT, path_drawdown(path), trades)


def hedged(bars: Sequence[Bar], params: Params) -> Outcome:
    """Hedger: a swing trade with a floor on the loss, paid for with a premium."""
    base = hold(bars, params)
    pnl = max(base.pnl, -params.hedge_floor) - params.hedge_premium
    drawdown = min(base.drawdown, params.hedge_floor + params.hedge_premium)
    return Outcome(pnl, drawdown, base.trades, base.marks)


def arbitrage(bars: Sequence[Bar], params: Params) -> Outcome:
    """Arbitrageur: capture a fixed share of every bar's move, long or short, minus costs."""
    require_bars(bars)
    closes = [bar.close for bar in bars]
    captured = 0.0
    for index in range(1, len(closes)):
        move = abs(closes[index] / closes[index - 1] - 1) * PERCENT
        captured += move * params.capture / PERCENT - params.cost_bps / BASIS_POINTS * PERCENT
    trades = len(closes) - 1
    drawdown = max(0.0, trades * params.cost_bps / BASIS_POINTS * PERCENT)
    return Outcome(captured, drawdown, trades)


def quant(bars: Sequence[Bar], params: Params) -> Outcome:
    """Quant: half momentum, half contrarian."""
    first, second = breakout(bars, params), reversion(bars, params)
    pnl = (first.pnl + second.pnl) / 2
    drawdown = max(first.drawdown, second.drawdown)
    return Outcome(pnl, drawdown, first.trades + second.trades, first.marks + second.marks)


def whale(bars: Sequence[Bar], params: Params) -> Outcome:
    """Whale: the swing trade with leverage, paying slippage in proportion."""
    base = hold(bars, params)
    slippage = params.cost_bps / BASIS_POINTS * PERCENT * params.leverage
    pnl = base.pnl * params.leverage - slippage
    return Outcome(pnl, min(PERCENT, base.drawdown * params.leverage), base.trades, base.marks)


STRATEGIES: Mapping[str, Strategy] = {
    "Swing": hold,
    "Momentum": breakout,
    "Contrarian": reversion,
    "Scalper": scalp,
    "Hedger": hedged,
    "Arbitrageur": arbitrage,
    "Quant": quant,
    "Whale": whale,
}
"""The strategy each class trades."""


DESCRIPTIONS: Mapping[str, str] = {
    "Swing": "Buys the first open and holds to the last close.",
    "Momentum": "Waits for a close above the opening range, then rides it with a stop and a target.",
    "Contrarian": "Buys a close that drops below the running average and aims back at it.",
    "Scalper": "Trades every bar in the direction of the last one and pays costs each time.",
    "Hedger": "Holds like a Swing, with a floor under the loss that costs a premium.",
    "Arbitrageur": "Captures a fixed share of every bar's move, up or down, minus costs.",
    "Quant": "Half Momentum, half Contrarian.",
    "Whale": "Holds like a Swing with leverage: bigger wins, bigger drawdowns.",
}
"""What each class's strategy does, in one line, for clients and documentation."""


def strategy_for(role: str) -> Strategy:
    """Return the strategy of a class.

    Raises:
        ValueError: If no strategy exists for ``role``.
    """
    if role not in STRATEGIES:
        msg = f"no strategy for class {role!r}"
        raise ValueError(msg)
    return STRATEGIES[role]
