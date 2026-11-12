"""Round summaries: what happened on the market slice and what it teaches.

After every round a client shows the seat a summary: the opponent and the
scores, what each fielded unit did on its symbol (the closes and the bars
where it bought, stopped out or took profit), how each origin moved, and up to
three plain-language lessons picked from the facts of the round. The lessons
are the point of the game: each one names a real trading habit (a stop, a
hedge, over-trading, concentration, idle capital) that the round just made
concrete.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from tft.combat import CombatResult, board_trades
from tft.economy import streak_bonus
from tft.environment import Game, Player, RoundId, RoundReport, stage_damage
from tft.formation import Cell, is_back_half, is_covered
from tft.market import Bar, Slice
from tft.strategies import Mark

MAX_LESSONS = 3
PERCENT = 100.0
DECIMALS = 2
MEANINGFUL_GAP = 0.5
"""Percent points by which two results must differ before a lesson calls one better."""

UNPROTECTED_LOSS = 1.5
OVERTRADING_TRADES = 5
HEDGE_GAP = 1.0
CONTESTED_BOARDS = 2
LOW_HEALTH = 40
RICH = 30
INTEREST_CAP_GOLD = 50
IDLE_GOLD = 60
INTEREST_STEP = 10
NEARLY = 3
IDLE_COMPONENTS = 2
LONG_STREAK = 3
ONE_POSITION_MARKS = 2

WON, LOST, DRAWN, NO_FIGHT = "won", "lost", "draw", "none"


@dataclass(frozen=True)
class UnitLine:
    """One fielded unit's round: where it stood, what it traded, and how that went."""

    unit: str
    champion: str
    role: str
    origin: str
    symbol: str
    cell: Cell
    items: tuple[str, ...]
    pnl: float
    drawdown: float
    trades: int
    score: float
    raw_move: float
    closes: tuple[float, ...]
    marks: tuple[Mark, ...]

    def held_from(self, bar: int) -> float:
        """Return the percent move from the close of ``bar`` to the end of the slice."""
        return (self.closes[-1] / self.closes[bar] - 1) * PERCENT

    def mark(self, label: str) -> int | None:
        """Return the bar where the strategy did ``label``, if it did."""
        return next((bar for bar, what in self.marks if what == label), None)

    @property
    def one_position(self) -> bool:
        """Return whether the line is a single entry and exit whose result is the unit's result."""
        return self.role != "Quant" and len(self.marks) == ONE_POSITION_MARKS

    @property
    def entry(self) -> int:
        """Return the bar the position was opened on; 0 when the strategy left no marks."""
        bought = self.mark("buy")
        return bought if bought is not None else 0


@dataclass(frozen=True)
class RoundSummary:
    """A seat's round: the fight, the per-unit lines, the origins' moves and the lessons."""

    round_label: str
    slice_label: str | None
    opponent: str | None
    outcome: str
    score: float
    opponent_score: float
    damage: int
    units: tuple[UnitLine, ...]
    origin_moves: tuple[tuple[str, float], ...]
    lessons: tuple[str, ...]


@dataclass(frozen=True)
class Facts:
    """Everything a lesson rule may look at."""

    game: Game
    player: Player
    round_id: RoundId
    outcome: str
    units: tuple[UnitLine, ...]


Rule = Callable[[Facts], str | None]


def empty_slots(facts: Facts) -> str | None:
    """Units on the bench while the board has room."""
    player = facts.player
    if len(player.board) >= player.board_limit or not player.bench:
        return None
    return (
        f"You fielded {len(player.board)} of {player.board_limit} units with "
        f"{len(player.bench)} on the bench. An empty slot earns nothing: field your bench "
        "before you fight."
    )


def stopped_out(facts: Facts) -> str | None:
    """A stop that fired: did it save money, or cost the rebound?"""
    for line in facts.units:
        if line.mark("stop") is None or not line.one_position:
            continue
        held = line.held_from(line.entry)
        if held < line.pnl - MEANINGFUL_GAP:
            return (
                f"{line.champion} was stopped out of {line.symbol} at {line.pnl:+.1f}%. Holding "
                f"to the end of the slice would have made {held:+.1f}%: the stop turned an "
                "open-ended loss into a known one."
            )
        return (
            f"{line.champion} was stopped out of {line.symbol} at {line.pnl:+.1f}% and the "
            f"price then finished at {held:+.1f}%. A stop sometimes costs you the rebound: "
            "that is the price of a known maximum loss."
        )
    return None


def took_profit(facts: Facts) -> str | None:
    """A target that fired: did it bank the gain, or cap it?"""
    for line in facts.units:
        if line.mark("target") is None or not line.one_position:
            continue
        held = line.held_from(line.entry)
        if held > line.pnl + MEANINGFUL_GAP:
            return (
                f"{line.champion} took profit at {line.pnl:+.1f}% on {line.symbol}, which went "
                f"on to {held:+.1f}%. A target locks a win in and caps it: widen it with a "
                "Limit Order when you expect a trend."
            )
        return (
            f"{line.champion} took profit at {line.pnl:+.1f}% on {line.symbol} before it "
            f"finished at {held:+.1f}%. The target banked the gain while it was there."
        )
    return None


def hedge_paid(facts: Facts) -> str | None:
    """A hedge that kept a loss small while its symbol fell."""
    for line in facts.units:
        if line.role == "Hedger" and line.raw_move < line.pnl - HEDGE_GAP:
            return (
                f"{line.champion}'s hedge held its loss to {line.pnl:+.1f}% while "
                f"{line.symbol} moved {line.raw_move:+.1f}%. Insurance costs a premium every "
                "round and pays in the bad ones."
            )
    return None


def unprotected_loss(facts: Facts) -> str | None:
    """The round's worst losing unit, when it carried no item."""
    losers = [line for line in facts.units if line.pnl <= -UNPROTECTED_LOSS and not line.items]
    if not losers:
        return None
    line = min(losers, key=lambda one: one.score)
    return (
        f"{line.champion} lost {abs(line.pnl):.1f}% on {line.symbol} with a "
        f"{line.drawdown:.1f}% drawdown and no item to limit it. A Stop Order or a Hedge "
        "Ticket caps what one bad stretch can cost."
    )


def over_trading(facts: Facts) -> str | None:
    """Many trades and a loss: costs add up."""
    for line in facts.units:
        if line.trades >= OVERTRADING_TRADES and line.pnl < 0:
            return (
                f"{line.champion} made {line.trades} trades on {line.symbol} and lost "
                f"{abs(line.pnl):.1f}%. Every trade pays costs: over-trading is a tax."
            )
    return None


def never_traded(facts: Facts) -> str | None:
    """A strategy that found no signal."""
    idle = [line for line in facts.units if line.trades == 0]
    if not idle:
        return None
    line = idle[0]
    return (
        f"{line.champion} never traded: {line.symbol} gave its {line.role} strategy no signal "
        "on this slice. Staying flat is a position too, and it cost nothing."
    )


def concentration(facts: Facts) -> str | None:
    """Two or more units on the same symbol."""
    counts = Counter(line.symbol for line in facts.units)
    crowded = sorted(symbol for symbol, count in counts.items() if count > 1)
    if not crowded:
        return None
    symbol = crowded[0]
    names = [line.champion for line in facts.units if line.symbol == symbol]
    return (
        f"{names[0]} and {names[1]} both trade {symbol}: one ticker, {len(names)} positions. "
        "They win and lose together. Spread an origin over columns to diversify."
    )


def exposed_carry(facts: Facts) -> str | None:
    """A back-half unit with nobody in front that took a drawdown."""
    occupied = facts.player.occupied()
    rules = facts.game.rules
    for line in facts.units:
        exposed = is_back_half(line.cell, rules) and not is_covered(line.cell, occupied)
        if exposed and line.drawdown > 0:
            return (
                f"{line.champion} stands at the back with nobody in front of it: an exposed "
                f"position pays {rules.exposed_penalty_percent}% more for every drawdown. Put a "
                "unit in the same column, closer to the front."
            )
    return None


def idle_components(facts: Facts) -> str | None:
    """Components or finished items lying unused."""
    player = facts.player
    if len(player.components) >= IDLE_COMPONENTS:
        return (
            f"You are holding {len(player.components)} components. Slam them: a finished item "
            "working now beats a perfect item later."
        )
    if player.items:
        return (
            f"{player.items[0].name} is sitting in your inventory. An item only works on a "
            "unit: equip it."
        )
    return None


def contested(facts: Facts) -> str | None:
    """A fielded champion that several other boards also field."""
    player = facts.player
    others = [other for other in facts.game.alive if other is not player]
    counts = Counter(name for other in others for name in {u.champion.name for u in other.board})
    mine = sorted({unit.champion.name for unit in player.board})
    if not mine:
        return None
    name = max(mine, key=lambda one: counts[one])
    if counts[name] < CONTESTED_BOARDS:
        return None
    left = facts.game.pool.remaining(name)
    return (
        f"{name} is on {counts[name]} other boards and {left} copies are left in the shared "
        "pool. Contested units are slow to upgrade: scout, then pivot or commit."
    )


def low_health(facts: Facts) -> str | None:
    """Little health and a full bank."""
    player = facts.player
    if not player.alive or player.health > LOW_HEALTH or player.gold < RICH:
        return None
    return (
        f"You have {player.health} health and {player.gold} gold in the bank. Health is a "
        "resource too: spend to stabilise before the interest you are saving outlives you."
    )


def interest(facts: Facts) -> str | None:
    """Gold just short of the next interest point, or idle far above the cap."""
    gold = facts.player.gold
    if facts.round_id.stage < 2:  # noqa: PLR2004
        return None
    if gold >= IDLE_GOLD:
        return (
            f"You are sitting on {gold} gold. Interest stops growing at {INTEREST_CAP_GOLD}: "
            "put the surplus to work on levels or rerolls."
        )
    short = INTEREST_STEP - gold % INTEREST_STEP
    if gold < INTEREST_CAP_GOLD and short <= NEARLY:
        return (
            f"You are {short} gold short of the next interest point. Banked gold pays 1 per "
            f"{INTEREST_STEP}, up to 5 a round: a little restraint now compounds."
        )
    return None


def streak(facts: Facts) -> str | None:
    """A long win or loss streak."""
    run = facts.player.streak
    if run <= -LONG_STREAK:
        return (
            f"Loss streak of {-run}: the streak bonus pays you {streak_bonus(run)} gold a round "
            "and every loss costs health. Decide on purpose: ride the streak for gold, or "
            "stabilise."
        )
    if run >= LONG_STREAK:
        return (
            f"Win streak of {run}: {streak_bonus(run)} extra gold a round and your health "
            "stays intact. Consistency pays twice."
        )
    return None


RULES: tuple[Rule, ...] = (
    empty_slots,
    stopped_out,
    took_profit,
    hedge_paid,
    unprotected_loss,
    over_trading,
    never_traded,
    concentration,
    exposed_carry,
    idle_components,
    contested,
    low_health,
    interest,
    streak,
)
"""The lesson rules in priority order; the first :data:`MAX_LESSONS` that apply are shown."""


def pick_lessons(facts: Facts) -> tuple[str, ...]:
    """Return the first lessons that apply to the round, at most :data:`MAX_LESSONS`."""
    found: list[str] = []
    for rule in RULES:
        text = rule(facts)
        if text is not None:
            found.append(text)
        if len(found) == MAX_LESSONS:
            break
    return tuple(found)


def normalised(bars: tuple[Bar, ...]) -> tuple[float, ...]:
    """Return the closes scaled so that the first close is 100."""
    first = bars[0].close
    return tuple(round(bar.close / first * PERCENT, DECIMALS) for bar in bars)


def unit_lines(game: Game, player: Player) -> tuple[UnitLine, ...]:
    """Return one line per fielded unit for the round's slice; empty without a market pack."""
    if game.pack is None or game.slice is None:
        return ()
    trades = board_trades(player, game.slice, game.pack, game.rules)
    lines: list[UnitLine] = []
    for unit, trade in zip(player.board, trades, strict=True):
        bars = game.slice.bars[trade.symbol]
        raw_move = (bars[-1].close / bars[0].open - 1) * PERCENT
        outcome = trade.outcome
        lines.append(
            UnitLine(
                trade.unit,
                trade.champion,
                trade.role,
                trade.origin,
                trade.symbol,
                trade.cell,
                tuple(item.name for item in unit.items),
                round(outcome.pnl, DECIMALS),
                round(outcome.drawdown, DECIMALS),
                outcome.trades,
                round(trade.score, DECIMALS),
                round(raw_move, DECIMALS),
                normalised(bars),
                outcome.marks,
            )
        )
    return tuple(lines)


def origin_moves(game: Game, market: Slice | None) -> tuple[tuple[str, float], ...]:
    """Return each origin's average close-to-close move over the slice, in percent."""
    if game.pack is None or market is None:
        return ()
    moves: list[tuple[str, float]] = []
    for origin, symbols in game.pack.origins.items():
        changes = [market.bars[s][-1].close / market.bars[s][0].close - 1 for s in symbols]
        moves.append((origin, round(sum(changes) / len(changes) * PERCENT, DECIMALS)))
    return tuple(moves)


def outcome_of(result: CombatResult | None, name: str) -> str:
    """Return ``won``, ``lost``, ``draw`` or ``none`` for ``name`` in ``result``."""
    if result is None:
        return NO_FIGHT
    if result.is_draw:
        return DRAWN
    return WON if result.winner == name else LOST


def summarize(game: Game, name: str, report: RoundReport) -> RoundSummary:
    """Summarise the round ``report`` describes for the seat ``name``.

    Call it right after :meth:`tft.environment.Game.finish_round`, while the
    game still holds the round's slice.

    Raises:
        KeyError: If ``name`` is not a seat of the game.
    """
    player = game.player(name)
    result = next((one for one in report.results if one.involves(name)), None)
    outcome = outcome_of(result, name)
    opponent = result.opponent_of(name) if result is not None else None
    lost = outcome == LOST and result is not None
    damage = stage_damage(report.round_id.stage, game.rules) + result.survivors if lost else 0
    units = unit_lines(game, player)
    facts = Facts(game, player, report.round_id, outcome, units)
    return RoundSummary(
        report.round_id.label,
        report.slice_label,
        opponent,
        outcome,
        result.score_of(name) if result is not None else 0.0,
        result.score_of(opponent) if result is not None and opponent is not None else 0.0,
        damage,
        units,
        origin_moves(game, game.slice),
        pick_lessons(facts),
    )
