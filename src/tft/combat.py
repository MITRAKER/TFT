"""Combat resolution: the mock power comparison and the market replay.

Every resolver turns two boards into a :class:`CombatResult`. The
:class:`PowerResolver` compares the boards' power, the mock of milestone M0.
The :class:`MarketResolver` scores every unit's strategy on the round's slice
of real historical bars, sized by the unit's power and shaped by its items,
sums the board with its trait and augment bonuses, and lets the higher score
win. :func:`preview` is the Time Machine: it replays a fight on bootstrapped
bars many times and reports the odds, never a promise.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING, Protocol

from tft.market import Bar, MarketPack, Slice
from tft.rules import DEFAULT_RULES, Rules
from tft.strategies import Outcome, Params, strategy_for

if TYPE_CHECKING:
    from tft.environment import Player, RoundId, Unit

SCORE_DECIMALS = 4
PERCENT = 100
TENTHS = 10


@dataclass(frozen=True)
class CombatContext:
    """What a fight is resolved on: the round and, for the market replay, its slice."""

    round_id: RoundId
    slice: Slice | None = None


@dataclass(frozen=True)
class CombatResult:
    """Who won a fight, who lost, and how many winning units were left standing."""

    winner: str | None
    loser: str | None
    survivors: int

    @property
    def is_draw(self) -> bool:
        """Return whether nobody won."""
        return self.winner is None


class CombatResolver(Protocol):
    """The seam between the round loop and the way a fight is decided."""

    def resolve(
        self, home: Player, away: Player, rng: Random, context: CombatContext, /
    ) -> CombatResult:
        """Fight ``home`` against ``away`` and return the result."""


def margin_result(home: Player, away: Player, home_score: float, away_score: float) -> CombatResult:
    """Turn two scores into a result: the higher wins, survivors scale with the margin."""
    if home_score == away_score:
        return CombatResult(None, None, 0)
    winner, loser = (home, away) if home_score > away_score else (away, home)
    strong, weak = max(home_score, away_score), min(home_score, away_score)
    spread = abs(strong) + abs(weak)
    fraction = (strong - weak) / spread if spread else 1.0
    survivors = max(1, round(len(winner.board) * fraction))
    return CombatResult(winner.name, loser.name, survivors)


class PowerResolver:
    """The mock resolver: the stronger board wins and survivors scale with the margin."""

    def resolve(
        self, home: Player, away: Player, _rng: Random, _context: CombatContext, /
    ) -> CombatResult:
        """Compare team power; a tie is a draw."""
        return margin_result(home, away, home.team_power, away.team_power)


def unit_symbol(pack: MarketPack, origin: str, index: int) -> str:
    """Return the symbol the unit in board position ``index`` trades for ``origin``."""
    symbols = pack.symbols_for(origin)
    return symbols[index % len(symbols)]


def unit_trade(
    unit: Unit, bars: tuple[Bar, ...], params: Params, rules: Rules
) -> tuple[Outcome, float]:
    """Run the unit's strategy on ``bars`` and return the outcome and the unit's score.

    The score is the profit minus the penalised drawdown, times the unit's size.
    Items tighten or widen the stop and target, change the size, and shield
    part of the drawdown from the penalty.
    """
    effect = unit.effect
    outcome = strategy_for(unit.champion.role)(
        bars, params.scaled(effect.stop_tenths, effect.target_tenths)
    )
    size = unit.power(rules) / TENTHS * (PERCENT + effect.size_percent) / PERCENT
    shielded = outcome.drawdown * max(0, PERCENT - effect.shield_percent) / PERCENT
    score = size * (outcome.pnl - rules.risk_penalty_tenths / TENTHS * shielded)
    return outcome, score


def board_score(player: Player, market: Slice, pack: MarketPack, rules: Rules) -> float:
    """Score a whole board on a slice: the units' scores with the trait and augment bonuses."""
    params = Params.from_rules(rules)
    total = 0.0
    for index, unit in enumerate(player.board):
        bars = market.bars[unit_symbol(pack, unit.champion.origin, index)]
        total += unit_trade(unit, bars, params, rules)[1]
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


def bootstrap_slice(pack: MarketPack, rng: Random, length: int) -> Slice:
    """Build a synthetic slice by chaining randomly chosen real bars of each symbol.

    Each step takes a real bar and scales it to the current price, so the
    synthetic path has the symbol's own kind of moves in a new order: the
    Time Machine of the Day Trader skill, applied per symbol.

    Raises:
        ValueError: If ``length`` is shorter than two bars.
    """
    if length < 2:  # noqa: PLR2004
        msg = "a slice needs at least two bars"
        raise ValueError(msg)
    bars: dict[str, tuple[Bar, ...]] = {}
    for symbol, series in sorted(pack.series.items()):
        real = series.bars
        first = real[rng.randrange(len(real))]
        path = [first]
        for _ in range(length - 1):
            index = rng.randrange(1, len(real))
            anchor = real[index - 1].close
            scale = path[-1].close / anchor
            sample = real[index]
            path.append(
                Bar(
                    sample.open * scale,
                    sample.high * scale,
                    sample.low * scale,
                    sample.close * scale,
                    sample.volume,
                )
            )
        bars[symbol] = tuple(path)
    dates = tuple(f"sample {number}" for number in range(1, length + 1))
    return Slice(-1, dates, bars)


def sample_points(home: Player, away: Player, pack: MarketPack, rules: Rules, rng: Random) -> float:
    """Score one bootstrapped slice: 1 when ``home`` wins, 0.5 for a draw, 0 for a loss."""
    sample = bootstrap_slice(pack, rng, rules.slice_bars)
    home_score = board_score(home, sample, pack, rules)
    away_score = board_score(away, sample, pack, rules)
    if home_score > away_score:
        return 1.0
    return 0.5 if home_score == away_score else 0.0


def preview(home: Player, away: Player, pack: MarketPack, rules: Rules, rng: Random) -> float:
    """Return the share of bootstrapped slices ``home`` wins; a draw counts half."""
    total = sum(sample_points(home, away, pack, rules, rng) for _ in range(rules.preview_samples))
    return total / rules.preview_samples
