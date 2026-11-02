"""Replays: a seed, a rule set and the recorded seat actions reproduce a match.

Bots are deterministic given the game's seeded random stream, so a replay only
needs to store what the outside-controlled seat did in each round. Running the
replay rebuilds the match and plays those actions back; verifying it checks
that the placements come out the same, which is the engine's determinism
guarantee made visible.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tft.environment import Game, Player, Unit
from tft.rules import DEFAULT_RULES, Rules

FORMAT_VERSION = 1
ACTION_FIELDS = 2


@dataclass(frozen=True)
class Action:
    """One planning-phase action of the recorded seat: a kind and an optional number."""

    kind: str
    arg: int | None = None

    def to_json(self) -> list[object]:
        """Return the action as ``[kind, arg]``."""
        return [self.kind, self.arg]

    @classmethod
    def from_json(cls, data: object) -> Action:
        """Rebuild an action from ``[kind, arg]``.

        Raises:
            ValueError: If the data is not a kind string and an optional integer.
        """
        if not isinstance(data, list) or len(data) != ACTION_FIELDS:
            msg = f"an action is a two-item list, got {data!r}"
            raise ValueError(msg)
        kind, arg = data
        if not isinstance(kind, str) or not (arg is None or isinstance(arg, int)):
            msg = f"an action is [kind, number or null], got {data!r}"
            raise ValueError(msg)
        return cls(kind, arg)


def require_arg(arg: int | None, what: str) -> int:
    """Return ``arg`` or explain which number the action needed.

    Raises:
        ValueError: If ``arg`` is missing.
    """
    if arg is None:
        msg = f"this action needs {what}"
        raise ValueError(msg)
    return arg


def unit_at(player: Player, index: int | None) -> Unit:
    """Return the unit numbered ``index`` in the player's units (board first, then bench).

    Raises:
        ValueError: If the number is missing or out of range.
    """
    number = require_arg(index, "a unit number")
    units = player.units
    if not 0 <= number < len(units):
        msg = f"unit number must be 0 to {len(units) - 1}" if units else "you own no units"
        raise ValueError(msg)
    return units[number]


def _buy(game: Game, player: Player, arg: int | None) -> str:
    slot = require_arg(arg, "a shop slot")
    player.buy(slot, game.pool)  # noqa: JPL07 - acts by side effect
    return f"bought shop slot {slot}; {player.gold} gold left"


def _sell(game: Game, player: Player, arg: int | None) -> str:
    unit = unit_at(player, arg)
    value = player.sell(unit, game.pool)
    return f"sold {unit.describe()} for {value} gold; {player.gold} gold now"


def _reroll(game: Game, player: Player, arg: int | None) -> str:
    del arg
    player.reroll(game.pool, game.rng)  # noqa: JPL07 - acts by side effect
    return f"rerolled; {player.gold} gold left"


def _xp(game: Game, player: Player, arg: int | None) -> str:
    del game, arg
    player.buy_xp()  # noqa: JPL07 - acts by side effect
    return f"bought xp: level {player.level}, {player.xp} xp, {player.gold} gold left"


def _field(game: Game, player: Player, arg: int | None) -> str:
    del game
    unit = unit_at(player, arg)
    player.field_unit(unit)  # noqa: JPL07 - acts by side effect
    return f"fielded {unit.describe()}"


def _bench(game: Game, player: Player, arg: int | None) -> str:
    del game
    unit = unit_at(player, arg)
    player.bench_unit(unit)  # noqa: JPL07 - acts by side effect
    return f"benched {unit.describe()}"


def _augment(game: Game, player: Player, arg: int | None) -> str:
    del game
    augment = player.choose_augment(require_arg(arg, "an augment number"))
    return f"took {augment.name}: {augment.text}"


Handler = Callable[[Game, Player, int | None], str]
ACTIONS: Mapping[str, Handler] = {
    "buy": _buy,
    "sell": _sell,
    "reroll": _reroll,
    "xp": _xp,
    "field": _field,
    "bench": _bench,
    "augment": _augment,
}
"""Every action a seat can take during planning, by name."""


def apply_action(game: Game, player: Player, action: Action) -> str:
    """Apply ``action`` for ``player`` and return a one-line description of what happened.

    Raises:
        ValueError: If the action is unknown or the engine refuses it.
    """
    handler = ACTIONS.get(action.kind)
    if handler is None:
        msg = f"unknown action {action.kind!r}"
        raise ValueError(msg)
    return handler(game, player, action.arg)


@dataclass
class Replay:
    """A recorded match: who played, the seed, the rules, and the seat's actions per round."""

    seed: int
    players: list[str]
    seat: str
    rules_digest: str
    rounds: list[list[Action]] = field(default_factory=list)
    result: list[str] | None = None

    def to_json(self) -> dict[str, object]:
        """Return the replay as plain JSON data."""
        return {
            "format": FORMAT_VERSION,
            "seed": self.seed,
            "players": list(self.players),
            "seat": self.seat,
            "rules_digest": self.rules_digest,
            "rounds": [[action.to_json() for action in actions] for actions in self.rounds],
            "result": None if self.result is None else list(self.result),
        }

    @classmethod
    def from_json(cls, data: object) -> Replay:
        """Rebuild a replay from JSON data.

        Raises:
            ValueError: If the data is not a replay of a known format.
        """
        if not isinstance(data, dict) or data.get("format") != FORMAT_VERSION:
            msg = f"not a replay of format {FORMAT_VERSION}"
            raise ValueError(msg)
        try:
            rounds = [[Action.from_json(item) for item in actions] for actions in data["rounds"]]
            replay = cls(
                int(data["seed"]),
                [str(name) for name in data["players"]],
                str(data["seat"]),
                str(data["rules_digest"]),
                rounds,
                None if data.get("result") is None else [str(n) for n in data["result"]],
            )
        except (KeyError, TypeError) as error:
            msg = f"replay data is incomplete: {error}"
            raise ValueError(msg) from error
        return replay

    def save(self, path: Path) -> None:
        """Write the replay as JSON, creating the parent directory."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Replay:
        """Read a replay written by :meth:`save`."""
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))


def run_replay(replay: Replay, rules: Rules = DEFAULT_RULES) -> list[str]:
    """Rebuild the match, play the recorded actions back, and return the placements.

    Raises:
        ValueError: If ``rules`` is not the rule set the replay was recorded under.
    """
    if rules.digest() != replay.rules_digest:
        msg = "the replay was recorded under a different rule set"
        raise ValueError(msg)
    game = Game(replay.players, seed=replay.seed, rules=rules, policies={replay.seat: None})
    seat = game.player(replay.seat)
    for actions in replay.rounds:
        if game.finished:
            break
        _ = game.start_round()
        for action in actions:
            _ = apply_action(game, seat, action)
        _ = game.finish_round()
    return game.run()


def verify_replay(replay: Replay, rules: Rules = DEFAULT_RULES) -> bool:
    """Return whether playing the replay back gives the placements it recorded."""
    return replay.result is not None and run_replay(replay, rules) == replay.result
