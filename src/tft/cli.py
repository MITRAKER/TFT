"""The command-line client: play against bots, simulate, replay, or print the rules.

Examples::

    tft play --seed 7                      # you against seven bots
    tft sim --seed 7                       # bots only; prints the placements
    tft replay replays/match-7.json --verify
    tft rules > my-rules.toml              # the default rule set, ready to edit
    tft play --rules my-rules.toml

The client is plain text and standard library only. Its input and output are
injectable, so the whole flow is covered by tests.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tft import __version__
from tft.environment import Game, Player, RoundId, RoundReport, SeatView
from tft.replay import Action, Replay, apply_action, run_replay
from tft.roster import active_traits
from tft.rules import DEFAULT_RULES, Rules

BOT_NAMES = ("ana", "bo", "cy", "di", "ed", "fay", "gus", "hal")
DEFAULT_SEAT = "you"
MAX_COMMANDS_PER_ROUND = 200
"""Safety rail: a planning phase ends after this many commands."""

ACTION_COMMANDS: dict[str, tuple[str, str]] = {
    "b": ("buy", "b <slot>    buy the champion in shop slot <slot>"),
    "s": ("sell", "s <unit>    sell unit number <unit>"),
    "r": ("reroll", "r           reroll the shop"),
    "x": ("xp", "x           buy experience"),
    "f": ("field", "f <unit>    move a bench unit to the board"),
    "u": ("bench", "u <unit>    move a board unit to the bench"),
    "a": ("augment", "a <n>       take augment <n> from the offer"),
}
"""Planning commands that become recorded actions."""

LOCAL_COMMANDS: dict[str, str] = {
    "o": "o           scout the other boards",
    "h": "h           show this help",
    "e": "e or Enter  end planning and fight",
    "q": "q           quit the match",
}
"""Commands handled by the client itself."""

MAX_COMMAND_WORDS = 2


@dataclass(frozen=True)
class Console:
    """Where the client reads commands and writes text."""

    read: Callable[[str], str]
    write: Callable[[str], None]


def standard_console() -> Console:
    """Return a console on the terminal."""
    return Console(read=input, write=print)


def render_help() -> str:
    """Return the command list."""
    lines = ["Commands (unit numbers are shown in brackets, board first, then bench):"]
    lines += [f"  {text}" for _, text in ACTION_COMMANDS.values()]
    lines += [f"  {text}" for text in LOCAL_COMMANDS.values()]
    return "\n".join(lines)


def render_status(player: Player, round_id: RoundId) -> str:
    """Return the seat's situation: health, economy, board, bench, traits, shop and offers.

    Raises:
        ValueError: If the shop has not been rolled for this round.
    """
    if len(player.shop) != player.rules.shop_size:
        msg = f"{player.name}'s shop has not been rolled"
        raise ValueError(msg)
    kind = "PvE" if round_id.is_pve else "PvP"
    units = player.units
    board = [f"[{i}] {u.describe()}" for i, u in enumerate(units) if u in player.board]
    bench = [f"[{i}] {u.describe()}" for i, u in enumerate(units) if u in player.bench]
    traits = sorted(active_traits(u.champion for u in player.board).items())
    shop = [
        f"[{i}] {c.name} {c.cost}g" if c is not None else f"[{i}] -"
        for i, c in enumerate(player.shop)
    ]
    lines = [
        f"== Round {round_id.label} ({kind}) ==",
        (
            f"{player.name}: {player.health} hp | {player.gold} gold | level {player.level}, "
            f"{player.xp} xp | streak {player.streak:+d}"
        ),
        f"Board ({len(player.board)}/{player.board_limit}): {', '.join(board) or 'empty'}",
        f"Bench: {', '.join(bench) or 'empty'}",
        f"Traits: {', '.join(f'{name} {tier}' for name, tier in traits) or 'none'}",
        f"Shop: {', '.join(shop)}",
    ]
    if player.pending_augments:
        offers = " | ".join(
            f"[{i}] {a.name}: {a.text}" for i, a in enumerate(player.pending_augments)
        )
        lines.append(f"Augment offer: {offers}")
    return "\n".join(lines)


def render_scout(views: Sequence[SeatView]) -> str:
    """Return the other seats' public boards."""
    if not views:
        return "Nobody else is left."
    lines = []
    for view in views:
        units = ", ".join(view.units) or "empty"
        traits = ", ".join(view.traits) or "no traits"
        lines.append(
            f"{view.name}: {view.health} hp, level {view.level}, {view.gold} gold, "
            f"streak {view.streak:+d} | {units} | {traits}"
        )
    return "\n".join(lines)


def render_report(report: RoundReport) -> str:
    """Return the round's combat results and eliminations."""
    lines = [f"-- Round {report.round_id.label} results --"]
    for result in report.results:
        if result.is_draw:
            lines.append("a draw")
        else:
            lines.append(
                f"{result.winner} beat {result.loser} with {result.survivors} unit(s) left"
            )
    if report.eliminated:
        lines.append(f"Eliminated: {', '.join(report.eliminated)}")
    return "\n".join(lines)


def render_placements(game: Game) -> str:
    """Return the final standings."""
    lines = ["== Final placements =="]
    for place, name in enumerate(game.placements, start=1):
        player = game.player(name)
        lines.append(f"{place}. {name}: {player.health} hp, level {player.level}")
    return "\n".join(lines)


def parse_command(line: str) -> tuple[str, int | None]:
    """Split a command line into its key and optional number; an empty line ends planning.

    Raises:
        ValueError: If there is more than one argument or it is not a whole number.
    """
    parts = line.split()
    if not parts:
        return ("e", None)
    key = parts[0].lower()
    if len(parts) == 1:
        return (key, None)
    if len(parts) > MAX_COMMAND_WORDS or not parts[1].lstrip("-").isdigit():
        msg = "a command takes at most one whole number"
        raise ValueError(msg)
    return (key, int(parts[1]))


def handle_command(
    game: Game,
    player: Player,
    command: tuple[str, int | None],
    console: Console,
    actions: list[Action],
) -> str:
    """Run one planning command; return ``continue``, ``end`` or ``quit``.

    Raises:
        ValueError: If the command key is empty.
    """
    key, arg = command
    if not key:
        msg = "empty command"
        raise ValueError(msg)
    if key in ("e", "q"):
        return "end" if key == "e" else "quit"
    if key == "h":
        console.write(render_help())
        return "continue"
    if key == "o":
        console.write(render_scout(game.scout(player.name)))
        return "continue"
    if key not in ACTION_COMMANDS:
        console.write(f"unknown command {key!r}; h shows the commands")
        return "continue"
    action = Action(ACTION_COMMANDS[key][0], arg)
    try:
        message = apply_action(game, player, action)
    except ValueError as error:
        console.write(f"cannot: {error}")
        return "continue"
    actions.append(action)
    console.write(message)
    return "continue"


def play_round(game: Game, player: Player, console: Console) -> tuple[list[Action], bool]:
    """Play one round for the outside seat; return its actions and whether to go on.

    Raises:
        ValueError: If ``player`` is a bot seat.
    """
    if game.policies[player.name] is not None:
        msg = f"{player.name} is a bot seat"
        raise ValueError(msg)
    round_id = game.start_round()
    console.write(render_status(player, round_id))
    actions: list[Action] = []
    for _ in range(MAX_COMMANDS_PER_ROUND):
        try:
            line = console.read("> ")
        except EOFError:
            line = "q"
        try:
            command = parse_command(line)
        except ValueError as error:
            console.write(f"cannot: {error}")
            continue
        outcome = handle_command(game, player, command, console, actions)
        if outcome == "quit":
            return actions, False
        if outcome == "end":
            break
    console.write(render_report(game.finish_round()))
    return actions, True


def load_rules(path: str | None) -> Rules:
    """Return the default rules, or the rule set in the TOML file at ``path``."""
    return DEFAULT_RULES if path is None else Rules.from_toml(Path(path))


def save_replay(replay: Replay, path: str | None) -> Path:
    """Write the replay to ``path`` or to a timestamped file under ``replays/``; return the path."""
    if path is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = Path("replays") / f"match-{replay.seed}-{stamp}.json"
    else:
        target = Path(path)
    replay.save(target)  # noqa: JPL07 - acts by side effect
    return target


def play(args: argparse.Namespace, console: Console) -> int:
    """Play a match against bots on the console and save its replay.

    Raises:
        ValueError: If the number of bots does not fit the lobby.
    """
    rules = load_rules(args.rules)
    if not 1 <= args.bots < rules.lobby_size:
        msg = f"bots must be 1 to {rules.lobby_size - 1}"
        raise ValueError(msg)
    names = [args.name, *BOT_NAMES[: args.bots]]
    game = Game(names, seed=args.seed, rules=rules, policies={args.name: None})
    seat = game.player(args.name)
    replay = Replay(seed=args.seed, players=names, seat=args.name, rules_digest=rules.digest())
    console.write(
        f"Ticker Fight Tactics {__version__} | seed {args.seed} | {len(names)} seats | h for help"
    )
    for _ in range(len(game.rounds)):
        if game.finished or not seat.alive:
            break
        actions, keep_going = play_round(game, seat, console)
        replay.rounds.append(actions)
        if not keep_going:
            console.write("Match abandoned; no replay saved.")
            return 1
    replay.result = game.run()
    console.write(render_placements(game))
    console.write(f"Replay saved to {save_replay(replay, args.replay)}")
    return 0


def simulate(args: argparse.Namespace, console: Console) -> int:
    """Run a bots-only match and print the placements."""
    rules = load_rules(args.rules)
    game = Game(BOT_NAMES[: args.players], seed=args.seed, rules=rules)
    _ = game.run()
    console.write(render_placements(game))
    return 0


def verify_outcome(replay: Replay, placements: list[str], console: Console) -> int:
    """Compare a replay's playback with its recorded result; return the exit status."""
    if replay.result is None:
        console.write("The replay has no recorded result to verify against.")
        return 1
    if placements == replay.result:
        console.write("Replay verified: the match reproduced exactly.")
        return 0
    console.write("MISMATCH: the replay did not reproduce the recorded result.")
    return 1


def replay_command(args: argparse.Namespace, console: Console) -> int:
    """Play a replay back and, with ``--verify``, compare it with the recorded result."""
    rules = load_rules(args.rules)
    replay = Replay.load(Path(args.file))
    placements = run_replay(replay, rules)
    console.write("Placements: " + ", ".join(placements))
    if not args.verify:
        return 0
    return verify_outcome(replay, placements, console)


def rules_command(args: argparse.Namespace, console: Console) -> int:
    """Print the default rule set as TOML, or check a rule file."""
    if args.check is None:
        console.write(DEFAULT_RULES.to_toml().rstrip("\n"))
        return 0
    rules = Rules.from_toml(Path(args.check))
    console.write(
        f"ok: {args.check} is a valid rule set, {rules.max_rounds} rounds, digest {rules.digest()}"
    )
    return 0


def add_play_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add ``tft play``."""
    parser = commands.add_parser("play", help="play a match against bots")
    parser.add_argument("--seed", type=int, default=0, help="match seed (default 0)")
    parser.add_argument("--name", default=DEFAULT_SEAT, help="your seat name")
    parser.add_argument("--bots", type=int, default=7, help="number of bots (default 7)")
    parser.add_argument("--rules", help="TOML rule file (default: built-in rules)")
    parser.add_argument("--replay", help="where to save the replay (default: replays/)")
    parser.set_defaults(func=play)


def add_sim_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add ``tft sim``."""
    parser = commands.add_parser("sim", help="run a bots-only match")
    parser.add_argument("--seed", type=int, default=0, help="match seed (default 0)")
    parser.add_argument("--players", type=int, default=8, help="number of bots (default 8)")
    parser.add_argument("--rules", help="TOML rule file (default: built-in rules)")
    parser.set_defaults(func=simulate)


def add_replay_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add ``tft replay``."""
    parser = commands.add_parser("replay", help="play a replay back")
    parser.add_argument("file", help="a replay JSON file")
    parser.add_argument("--verify", action="store_true", help="compare with the recorded result")
    parser.add_argument("--rules", help="TOML rule file the replay was recorded with")
    parser.set_defaults(func=replay_command)


def add_rules_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add ``tft rules``."""
    parser = commands.add_parser("rules", help="print the default rules or check a rule file")
    parser.add_argument("--check", metavar="FILE", help="validate this TOML rule file")
    parser.set_defaults(func=rules_command)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="tft", description="Ticker Fight Tactics, the trading auto-battler."
    )
    parser.add_argument("--version", action="version", version=f"tft {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for add_command in (add_play_command, add_sim_command, add_replay_command, add_rules_command):
        add_command(commands)
    return parser


def main(argv: Sequence[str] | None = None, console: Console | None = None) -> int:
    """Run the client and return the exit status."""
    args = build_parser().parse_args(argv)
    active = console if console is not None else standard_console()
    try:
        return int(args.func(args, active))
    except (ValueError, OSError, RuntimeError) as error:
        active.write(f"error: {error}")
        return 2
