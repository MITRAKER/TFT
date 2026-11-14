"""Combat resolution: the mock power comparison and the market replay.

Every resolver turns two boards into a :class:`CombatResult`. The
:class:`PowerResolver` compares the boards' power, the mock of milestone M0.
The :class:`MarketResolver` scores every unit's strategy on the round's slice
of real historical bars: the unit's column picks the symbol of its origin, its
power, its items and its cell set the size and the drawdown shield, the board
adds its trait and augment bonuses, and the higher score wins.
:func:`preview_field` is the Time Machine: it replays the fights on
bootstrapped bars many times and reports the odds, never a promise.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING, Protocol

from tft.formation import Cell, position_effect
from tft.market import Bar, MarketPack, Slice
from tft.rules import DEFAULT_RULES, Rules
from tft.strategies import Outcome, Params, strategy_for

if TYPE_CHECKING:
    from tft.environment import Player, RoundId, Unit

SCORE_DECIMALS = 4
PERCENT = 100
TENTHS = 10
WIN, DRAW, LOSS = 1.0, 0.5, 0.0


@dataclass(frozen=True)
class CombatContext:
    """What a fight is resolved on: the round and, for the market replay, its slice."""

    round_id: RoundId
    slice: Slice | None = None


@dataclass(frozen=True)
class CombatResult:
    """Who won a fight, who lost, how many winning units were left, and the two scores.

    ``home`` and ``away`` name the two sides even when the fight is a draw.
    """

    winner: str | None
    loser: str | None
    survivors: int
    home: str = ""
    away: str = ""
    home_score: float = 0.0
    away_score: float = 0.0

    @property
    def is_draw(self) -> bool:
        """Return whether nobody won."""
        return self.winner is None

    def involves(self, name: str) -> bool:
        """Return whether ``name`` took part in the fight."""
        return name in (self.home, self.away, self.winner, self.loser)

    def opponent_of(self, name: str) -> str | None:
        """Return the other side of the fight as seen by ``name``, if it is known."""
        sides = (self.home, self.away) if self.home or self.away else (self.winner, self.loser)
        others = [side for side in sides if side and side != name]
        return others[0] if self.involves(name) and others else None

    def score_of(self, name: str) -> float:
        """Return the score ``name`` fought with; 0 when the resolver recorded none."""
        if name == self.home:
            return self.home_score
        return self.away_score if name == self.away else 0.0


class CombatResolver(Protocol):
    """The seam between the round loop and the way a fight is decided."""

    def resolve(
        self, home: Player, away: Player, rng: Random, context: CombatContext, /
    ) -> CombatResult:
        """Fight ``home`` against ``away`` and return the result."""


def margin_result(home: Player, away: Player, home_score: float, away_score: float) -> CombatResult:
    """Turn two scores into a result: the higher wins, survivors scale with the margin."""
    sides = (home.name, away.name, home_score, away_score)
    if home_score == away_score:
        return CombatResult(None, None, 0, *sides)
    winner, loser = (home, away) if home_score > away_score else (away, home)
    strong, weak = max(home_score, away_score), min(home_score, away_score)
    spread = abs(strong) + abs(weak)
    fraction = (strong - weak) / spread if spread else 1.0
    survivors = max(1, round(len(winner.board) * fraction))
    return CombatResult(winner.name, loser.name, survivors, *sides)


class PowerResolver:
    """The mock resolver: the stronger board wins and survivors scale with the margin."""

    def resolve(
        self, home: Player, away: Player, _rng: Random, _context: CombatContext, /
    ) -> CombatResult:
        """Compare team power; a tie is a draw."""
        return margin_result(home, away, home.team_power, away.team_power)


@dataclass(frozen=True)
class UnitTrade:
    """What one unit did on a slice: its symbol, its cell, the outcome, its size and its score."""

    unit: str
    champion: str
    role: str
    origin: str
    symbol: str
    cell: Cell
    outcome: Outcome
    size: float
    score: float


def unit_symbol(pack: MarketPack, origin: str, column: int) -> str:
    """Return the symbol a unit of ``origin`` trades when it stands in ``column``."""
    symbols = pack.symbols_for(origin)
    return symbols[column % len(symbols)]


def trade_unit(
    player: Player, unit: Unit, market: Slice, pack: MarketPack, rules: Rules, params: Params
) -> UnitTrade:
    """Run ``unit``'s strategy on the slice and score it.

    The score is the profit minus the penalised drawdown, times the unit's size.
    Items and the cell tighten or widen the stop and target, change the size,
    and shield part of the drawdown from the penalty (or expose it to more).

    Raises:
        ValueError: If the unit has no cell; call ``player.ensure_positions()`` first.
    """
    cell = unit.position
    if cell is None:
        msg = f"{unit.champion.name} has no cell on {player.name}'s board"
        raise ValueError(msg)
    origin, role = unit.champion.origin, unit.champion.role
    symbol = unit_symbol(pack, origin, cell[1])
    effect = unit.effect.combine(position_effect(cell, player.occupied(), rules))
    scaled = params.scaled(effect.stop_tenths, effect.target_tenths)
    outcome = strategy_for(role)(market.bars[symbol], scaled)
    size = unit.power(rules) / TENTHS * max(0, PERCENT + effect.size_percent) / PERCENT
    shielded = outcome.drawdown * max(0, PERCENT - effect.shield_percent) / PERCENT
    score = size * (outcome.pnl - rules.risk_penalty_tenths / TENTHS * shielded)
    name = unit.champion.name
    return UnitTrade(unit.describe(), name, role, origin, symbol, cell, outcome, size, score)


def board_trades(player: Player, market: Slice, pack: MarketPack, rules: Rules) -> list[UnitTrade]:
    """Trade every fielded unit on the slice, in board order."""
    player.ensure_positions()
    params = Params.from_rules(rules)
    return [trade_unit(player, unit, market, pack, rules, params) for unit in player.board]


def board_score(player: Player, market: Slice, pack: MarketPack, rules: Rules) -> float:
    """Score a whole board on a slice: the units' scores with the trait and augment bonuses."""
    total = sum(trade.score for trade in board_trades(player, market, pack, rules))
    return round(total * (PERCENT + player.bonus_percent) / PERCENT, SCORE_DECIMALS)


class MarketResolver:
    """The market replay: boards are scored by trading the round's slice of real bars."""

    def __init__(self, pack: MarketPack, rules: Rules = DEFAULT_RULES) -> None:
        """Resolve fights on ``pack`` under ``rules``."""
        self.pack = pack
        self.rules = rules

    def resolve(
        self, home: Player, away: Player, _rng: Random, context: CombatContext, /
    ) -> CombatResult:
        """Score both boards on the context's slice.

        Raises:
            ValueError: If the context carries no slice.
        """
        if context.slice is None:
            msg = "the market resolver needs the round's slice"
            raise ValueError(msg)
        home_score = board_score(home, context.slice, self.pack, self.rules)
        away_score = board_score(away, context.slice, self.pack, self.rules)
        return margin_result(home, away, home_score, away_score)


def bootstrap_path(real: Sequence[Bar], rng: Random, length: int) -> tuple[Bar, ...]:
    """Chain ``length`` randomly chosen real bars, each scaled to the price the path has reached."""
    path = [real[rng.randrange(len(real))]]
    for _ in range(length - 1):
        index = rng.randrange(1, len(real))
        scale = path[-1].close / real[index - 1].close
        bar = real[index]
        path.append(
            Bar(bar.open * scale, bar.high * scale, bar.low * scale, bar.close * scale, bar.volume)
        )
    return tuple(path)


def bootstrap_slice(pack: MarketPack, rng: Random, length: int) -> Slice:
    """Build a synthetic slice by chaining randomly chosen real bars of each symbol.

    The synthetic path has the symbol's own kind of moves in a new order: the
    Time Machine of the Day Trader skill, applied per symbol.

    Raises:
        ValueError: If ``length`` is shorter than two bars.
    """
    if length < 2:  # noqa: PLR2004
        msg = "a slice needs at least two bars"
        raise ValueError(msg)
    series = sorted(pack.series.items())
    bars = {symbol: bootstrap_path(one.bars, rng, length) for symbol, one in series}
    dates = tuple(f"sample {number}" for number in range(1, length + 1))
    return Slice(-1, dates, bars)


def points(home_score: float, away_score: float) -> float:
    """Return 1 for a win of the home score, 0.5 for a draw and 0 for a loss."""
    if home_score > away_score:
        return WIN
    return DRAW if home_score == away_score else LOSS


def preview_field(
    home: Player, others: Sequence[Player], pack: MarketPack, rules: Rules, rng: Random
) -> list[float]:
    """Return ``home``'s share of wins against each of ``others`` over bootstrapped slices.

    Every sample is one synthetic slice on which all the boards are scored, so
    the odds against different opponents come from the same simulated markets.
    A draw counts as half a win.
    """
    totals = [0.0] * len(others)
    for _ in range(rules.preview_samples):
        sample = bootstrap_slice(pack, rng, rules.slice_bars)
        home_score = board_score(home, sample, pack, rules)
        for index, other in enumerate(others):
            totals[index] += points(home_score, board_score(other, sample, pack, rules))
    return [total / rules.preview_samples for total in totals]


def preview(home: Player, away: Player, pack: MarketPack, rules: Rules, rng: Random) -> float:
    """Return the share of bootstrapped slices ``home`` wins; a draw counts half."""
    return preview_field(home, [away], pack, rules, rng)[0]
