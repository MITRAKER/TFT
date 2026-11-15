#!/usr/bin/env python3
"""Measure the balance of the strategies, the grid and the bots on a market pack.

A balance change should be judged by numbers. This tool trades every class on
every window of every symbol of a pack and plays whole matches with probe
policies, then prints four tables:

* **Classes**: the risk-adjusted return (the *edge*) of each class, what that
  does to a unit's size (the *result factor*), how often the class is wiped
  out or capped, and how often it out-scores another class on the same window.
* **Class by origin**: the mean result factor of each class on each origin's
  symbols, which shows the combinations a pack favours.
* **Champions**: each champion's mean result factor on its own origin and the
  score that gives it at one star.
* **Policies**: the mean placement of one seat that plays a probe policy (an
  empty board, a single unit, every unit in the back rows, ...) against the
  greedy bot. A probe that places better than the bot is an exploit.

Usage::

    python tools/balance_report.py [--pack PATH] [--rules PATH] [--matches N]
                                   [--format text|markdown]

``--matches 0`` skips the policy table, which is the slow part.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from random import Random

from tft.combat import result_factor
from tft.environment import Game, Player, Pool, Unit, greedy_policy
from tft.errors import Refusal
from tft.formation import column_order
from tft.market import MarketPack, load_builtin
from tft.roster import CHAMPIONS, CLASSES, ORIGINS
from tft.rules import DEFAULT_RULES, Rules
from tft.strategies import Params, strategy_for

TENTHS = 10
PERCENT = 100
PROBE = "probe"
LOBBY: tuple[str, ...] = (PROBE, "ana", "bo", "cy", "di", "ed", "fay", "gus")
DEFAULT_MATCHES = 60
FORMATS = ("text", "markdown")

Policy = Callable[[Player, Pool, Random], None]


@dataclass(frozen=True)
class Trial:
    """One class trading one symbol over one window, as a unit with no shield."""

    symbol: str
    start: int
    edge: float
    factor: float


@dataclass(frozen=True)
class Table:
    """A titled table of text cells; the first column is the row's name."""

    title: str
    note: str
    head: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def trials(role: str, symbols: Sequence[str], pack: MarketPack, rules: Rules) -> list[Trial]:
    """Trade ``role``'s strategy on every window of every one of ``symbols``.

    Raises:
        ValueError: If the pack is shorter than one slice or ``symbols`` is empty.
    """
    windows = len(pack.dates) - rules.slice_bars + 1
    if windows < 1 or not symbols:
        msg = f"the pack needs {rules.slice_bars} dates and the class at least one symbol"
        raise ValueError(msg)
    strategy, params = strategy_for(role), Params.from_rules(rules)
    penalty = rules.risk_penalty_tenths / TENTHS
    found = []
    for start in range(windows):
        bars = pack.window(start, rules.slice_bars).bars
        for symbol in symbols:
            outcome = strategy(bars[symbol], params)
            edge = outcome.pnl - penalty * outcome.drawdown
            found.append(Trial(symbol, start, edge, result_factor(edge, rules)))
    return found


def beat_rate(mine: Sequence[float], theirs: Sequence[float]) -> float:
    """Return the chance that a value of ``mine`` exceeds a value of ``theirs``; a tie counts half.

    Raises:
        ValueError: If either side is empty.
    """
    if not mine or not theirs:
        msg = "both sides need at least one value"
        raise ValueError(msg)
    ordered = sorted(theirs)
    points = sum(bisect_left(ordered, value) + bisect_right(ordered, value) for value in mine)
    return points / (2 * len(mine) * len(ordered))


def by_window(found: Sequence[Trial]) -> dict[int, list[float]]:
    """Group the result factors of ``found`` by the window they were traded on."""
    grouped: dict[int, list[float]] = {}
    for trial in found:
        grouped.setdefault(trial.start, []).append(trial.factor)
    return grouped


def field_rates(by_role: Mapping[str, Sequence[Trial]]) -> dict[str, float]:
    """Return, per class, the chance that it out-scores another class on the same window."""
    windows = {role: by_window(found) for role, found in by_role.items()}
    rates = {}
    for role, mine in windows.items():
        others = [theirs for other, theirs in windows.items() if other != role]
        duels = [
            beat_rate(values, theirs[start]) for theirs in others for start, values in mine.items()
        ]
        rates[role] = statistics.fmean(duels) if duels else 0.5
    return rates


def class_table(pack: MarketPack, rules: Rules) -> Table:
    """Build the table of every class over every symbol of the pack.

    Raises:
        ValueError: If the pack holds no symbol.
    """
    if not pack.symbols:
        msg = "the pack holds no symbol"
        raise ValueError(msg)
    by_role = {trait.name: trials(trait.name, pack.symbols, pack, rules) for trait in CLASSES}
    rates = field_rates(by_role)
    cap = rules.result_cap_percent / PERCENT
    rows = []
    for role, found in by_role.items():
        edges = [trial.edge for trial in found]
        factors = [trial.factor for trial in found]
        rows.append(
            (
                role,
                f"{statistics.fmean(edges):+.2f}",
                f"{statistics.pstdev(edges):.2f}",
                f"{statistics.fmean(factors):.2f}",
                f"{sum(factor <= 0 for factor in factors) / len(factors):.0%}",
                f"{sum(factor >= cap for factor in factors) / len(factors):.0%}",
                f"{rates[role]:.0%}",
            )
        )
    head = ("Class", "Edge %", "Spread", "Factor", "Wiped out", "Capped", "Beats the field")
    note = (
        "Edge is the profit minus the penalised drawdown; the factor is what it multiplies a "
        "unit's size by. Beats the field is the chance of out-scoring another class on the "
        "same window; 50% is even."
    )
    return Table("Classes", note, head, tuple(rows))


def pack_origins(pack: MarketPack) -> tuple[str, ...]:
    """Return the roster's origins that the pack maps to symbols, in roster order."""
    return tuple(origin.name for origin in ORIGINS if origin.name in pack.origins)


def origin_table(pack: MarketPack, rules: Rules) -> Table:
    """Build the matrix of mean result factors, one row per class and one column per origin."""
    origins = pack_origins(pack)
    rows = []
    for trait in CLASSES:
        cells = [
            statistics.fmean(
                trial.factor for trial in trials(trait.name, pack.symbols_for(origin), pack, rules)
            )
            for origin in origins
        ]
        rows.append((trait.name, *(f"{cell:.2f}" for cell in cells)))
    note = "The mean result factor of each class on each origin's symbols; 1.00 keeps the size."
    return Table("Class by origin", note, ("Class", *origins), tuple(rows))


def champion_table(pack: MarketPack, rules: Rules) -> Table:
    """Build the table of every champion on the symbols of its own origin.

    Raises:
        ValueError: If the pack holds no symbol.
    """
    if not pack.symbols:
        msg = "the pack holds no symbol"
        raise ValueError(msg)
    cache: dict[tuple[str, str], float] = {}
    rows = []
    for champion in CHAMPIONS:
        key = (champion.role, champion.origin)
        if key not in cache:
            found = trials(champion.role, pack.symbols_for(champion.origin), pack, rules)
            cache[key] = statistics.fmean(trial.factor for trial in found)
        size = Unit(champion).power(rules) / TENTHS
        rows.append(
            (
                champion.name,
                str(champion.cost),
                champion.origin,
                champion.role,
                f"{cache[key]:.2f}",
                f"{size:.1f}",
                f"{size * cache[key]:.2f}",
            )
        )
    head = ("Champion", "Cost", "Origin", "Class", "Factor", "Size", "Score")
    note = "The size is the unit's power at one star; the score is the size times the factor."
    return Table("Champions", note, head, tuple(rows))


def idle(player: Player, pool: Pool, rng: Random) -> None:
    """Buy nothing and field nothing: the empty board."""
    del player, pool, rng


def one_unit(player: Player, pool: Pool, rng: Random) -> None:
    """Play the greedy bot, then send every unit but the first back to the bench."""
    greedy_policy(player, pool, rng)
    for unit in player.board[1:]:
        try:
            player.bench_unit(unit)
        except Refusal:
            break


def in_rows(rows: Sequence[int]) -> Policy:
    """Return the greedy bot with its units moved to ``rows``, centre columns first."""

    def policy(player: Player, pool: Pool, rng: Random) -> None:
        greedy_policy(player, pool, rng)
        columns = column_order(player.rules.board_cols)
        cells = [(row, column) for row in rows for column in columns]
        for unit, cell in zip(player.board, cells, strict=False):
            unit.position = cell

    return policy


def probes(rules: Rules) -> dict[str, Policy]:
    """Return the probe policies by name: the bot itself, then the would-be exploits."""
    last = rules.board_rows - 1
    return {
        "greedy bot (default formation)": greedy_policy,
        "empty board": idle,
        "one unit": one_unit,
        "every unit in the back rows": in_rows((last, max(last - 1, 0))),
        "every unit in the front rows": in_rows((0, min(1, last))),
    }


def mean_placement(policy: Policy, pack: MarketPack, rules: Rules, matches: int) -> float:
    """Return the mean placement of the probe seat over ``matches`` seeded matches.

    Raises:
        ValueError: If ``matches`` is not positive.
    """
    if matches < 1:
        msg = "matches must be positive"
        raise ValueError(msg)
    names = LOBBY[: rules.lobby_size]
    places = []
    for seed in range(matches):
        game = Game(names, seed, rules=rules, pack=pack, policies={PROBE: policy})
        places.append(game.run().index(PROBE) + 1)
    return statistics.fmean(places)


def policy_table(pack: MarketPack, rules: Rules, matches: int) -> Table:
    """Build the table of probe policies against the greedy bot."""
    rows = tuple(
        (name, f"{mean_placement(policy, pack, rules, matches):.2f}")
        for name, policy in probes(rules).items()
    )
    seats = min(len(LOBBY), rules.lobby_size)
    note = (
        f"The mean placement of one seat over {matches} matches against {seats - 1} greedy "
        f"bots; {(seats + 1) / 2:.1f} is even, lower is better. A probe that places better "
        "than the bot is an exploit."
    )
    return Table("Policies", note, ("Policy", "Mean placement"), rows)


def render_text(table: Table) -> str:
    """Render ``table`` with aligned columns: the first left, the rest right."""
    grid = (table.head, *table.rows)
    widths = [max(len(row[index]) for row in grid) for index in range(len(table.head))]
    lines = [f"== {table.title} ==", table.note]
    for row in grid:
        cells = [
            row[0].ljust(widths[0]),
            *(cell.rjust(width) for cell, width in zip(row[1:], widths[1:], strict=True)),
        ]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def render_markdown(table: Table) -> str:
    """Render ``table`` as a Markdown section."""
    rule = ["---", *("---:" for _ in table.head[1:])]
    lines = [f"### {table.title}", "", table.note, ""]
    lines.extend(f"| {' | '.join(row)} |" for row in (table.head, tuple(rule), *table.rows))
    return "\n".join(lines)


def build_tables(pack: MarketPack, rules: Rules, matches: int) -> list[Table]:
    """Build every table; the policy table only when ``matches`` is positive."""
    tables = [class_table(pack, rules), origin_table(pack, rules), champion_table(pack, rules)]
    if matches > 0:
        tables.append(policy_table(pack, rules, matches))
    return tables


def report(pack: MarketPack, rules: Rules, matches: int, style: str = "text") -> str:
    """Return the whole report: a line about the pack, then every table.

    Raises:
        ValueError: If ``style`` is not a known format or the pack cannot be traded.
    """
    if style not in FORMATS:
        msg = f"the format must be one of {', '.join(FORMATS)}"
        raise ValueError(msg)
    tables = build_tables(pack, rules, matches)
    render = render_markdown if style == "markdown" else render_text
    windows = len(pack.dates) - rules.slice_bars + 1
    heading = (
        f"Pack {pack.name}: {len(pack.symbols)} symbols, {pack.dates[0]} to {pack.dates[-1]}, "
        f"{windows} windows of {rules.slice_bars} bars."
    )
    return "\n\n".join([heading, *(render(table) for table in tables)])


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", type=Path, help="market pack file (default: the starter pack)")
    parser.add_argument("--rules", type=Path, help="rules TOML file (default: the default rules)")
    parser.add_argument(
        "--matches",
        type=int,
        default=DEFAULT_MATCHES,
        help=f"matches per probe policy; 0 skips the policy table (default {DEFAULT_MATCHES})",
    )
    parser.add_argument("--format", choices=FORMATS, default="text", help="output format")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the balance report; return 0, or 2 when the pack or the rules cannot be used."""
    args = parse_args(argv)
    try:
        pack = MarketPack.load(args.pack) if args.pack is not None else load_builtin()
        rules = Rules.from_toml(args.rules) if args.rules is not None else DEFAULT_RULES
        print(report(pack, rules, args.matches, args.format))
    except (OSError, ValueError) as error:
        print(f"balance_report: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
