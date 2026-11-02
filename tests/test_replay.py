"""Tests for :mod:`tft.replay`."""

from __future__ import annotations

from pathlib import Path

import pytest

from tft.environment import AUGMENTS, Game, Unit
from tft.items import Component
from tft.market import load_builtin
from tft.replay import Action, Replay, apply_action, run_replay, unit_at, verify_replay
from tft.roster import champion
from tft.rules import DEFAULT_RULES, Rules

NAMES = ["you", "ana", "bo", "cy"]


def scripted_game(seed: int = 3) -> tuple[Game, Replay]:
    """Play two rounds of a human seat through the API and record them."""
    game = Game(NAMES, seed=seed, policies={"you": None})
    seat = game.player("you")
    replay = Replay(seed=seed, players=NAMES, seat="you", rules_digest=DEFAULT_RULES.digest())
    for _ in range(2):
        _ = game.start_round()
        actions = [Action("buy", (0,))]
        _ = apply_action(game, seat, actions[0])
        actions.append(Action("field", (len(seat.units) - 1,)))
        _ = apply_action(game, seat, actions[1])
        replay.rounds.append(actions)
        _ = game.finish_round()
    replay.result = game.run()
    return game, replay


def test_action_json_round_trip_and_validation() -> None:
    assert Action.from_json(Action("buy", (2,)).to_json()) == Action("buy", (2,))
    assert Action.from_json(["reroll", []]) == Action("reroll")
    assert Action.from_json(["equip", [0, 1]]) == Action("equip", (0, 1))
    for bad in ("buy", ["buy"], [1, [2]], ["buy", "x"], ["buy", [True]], ["buy", None]):
        with pytest.raises(ValueError, match="action"):
            Action.from_json(bad)


def test_apply_action_messages_and_errors() -> None:
    game = Game(NAMES, seed=1, policies={"you": None})
    seat = game.player("you")
    _ = game.start_round()
    assert apply_action(game, seat, Action("buy", (0,))).startswith("bought shop slot 0")
    assert apply_action(game, seat, Action("field", (0,))).startswith("fielded ")
    assert apply_action(game, seat, Action("bench", (0,))).startswith("benched ")
    assert apply_action(game, seat, Action("sell", (0,))).startswith("sold ")
    assert apply_action(game, seat, Action("reroll")).startswith("rerolled")
    seat.gold += 10
    assert apply_action(game, seat, Action("xp")).startswith("bought xp")
    seat.components = [Component.STOP_ORDER, Component.LIMIT_ORDER]
    assert apply_action(game, seat, Action("craft", (0, 1))).startswith("crafted Bracket Order")
    _ = apply_action(game, seat, Action("buy", (1,)))
    assert apply_action(game, seat, Action("equip", (0, 0))).endswith("now holds Bracket Order")
    with pytest.raises(ValueError, match="unknown action"):
        apply_action(game, seat, Action("dance"))
    with pytest.raises(ValueError, match="needs a shop slot"):
        apply_action(game, seat, Action("buy"))
    with pytest.raises(ValueError, match="two component numbers"):
        apply_action(game, seat, Action("craft", (0,)))
    with pytest.raises(ValueError, match="no augment"):
        apply_action(game, seat, Action("augment", (0,)))


def test_augment_action_takes_the_offer() -> None:
    game = Game(NAMES, seed=1, policies={"you": None})
    seat = game.player("you")
    seat.pending_augments = list(AUGMENTS[:3])
    assert apply_action(game, seat, Action("augment", (1,))).startswith("took ")
    assert seat.augments == [AUGMENTS[1]]


def test_unit_at_numbers_board_then_bench() -> None:
    game = Game(NAMES, seed=1)
    seat = game.player("you")
    seat.board = [Unit(champion("Pip Squeak"))]
    seat.bench = [Unit(champion("Index Drone"))]
    assert unit_at(seat, 1).champion.name == "Index Drone"
    with pytest.raises(ValueError, match="unit number must be 0 to 1"):
        unit_at(seat, 2)
    seat.board, seat.bench = [], []
    with pytest.raises(ValueError, match="own no units"):
        unit_at(seat, 0)


def test_replay_json_round_trip(tmp_path: Path) -> None:
    _, replay = scripted_game()
    path = tmp_path / "nested" / "match.json"
    replay.save(path)
    assert Replay.load(path) == replay
    with pytest.raises(ValueError, match="not a replay"):
        Replay.from_json({"format": 99})
    with pytest.raises(ValueError, match="incomplete"):
        Replay.from_json({"format": 2, "seed": 1})


def test_replay_reproduces_the_match() -> None:
    game, replay = scripted_game()
    assert run_replay(replay) == game.placements == replay.result
    assert verify_replay(replay)
    replay.result = list(reversed(replay.result or []))
    assert not verify_replay(replay)
    replay.result = None
    assert not verify_replay(replay)


def test_replay_refuses_other_rules_or_packs() -> None:
    _, replay = scripted_game()
    with pytest.raises(ValueError, match="different rule set"):
        run_replay(replay, Rules(stages=2))
    with pytest.raises(ValueError, match="recorded with market pack None"):
        run_replay(replay, DEFAULT_RULES, load_builtin())


def test_replay_on_a_market_pack_reproduces_the_match() -> None:
    pack = load_builtin()
    game = Game(NAMES, seed=4, policies={"you": None}, pack=pack)
    replay = Replay(4, NAMES, "you", DEFAULT_RULES.digest(), pack.name)
    _ = game.start_round()
    _ = apply_action(game, game.player("you"), Action("buy", (0,)))
    replay.rounds.append([Action("buy", (0,))])
    _ = game.finish_round()
    replay.result = game.run()
    assert verify_replay(replay, DEFAULT_RULES, pack)
    with pytest.raises(ValueError, match="recorded with market pack 'starter'"):
        run_replay(replay)
    assert Replay.from_json(replay.to_json()) == replay
