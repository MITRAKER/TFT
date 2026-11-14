"""Tests for :mod:`tft.cli` with a scripted console."""

from __future__ import annotations

import runpy
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from tft import cli
from tft.cli import (
    Console,
    handle_command,
    main,
    parse_command,
    render_report,
    render_scout,
    render_status,
    standard_console,
)
from tft.environment import AUGMENTS, CombatResult, Game, Player, RoundId, RoundReport
from tft.replay import Replay
from tft.rules import Rules


class FakeConsole:
    """Feeds scripted lines and collects everything written."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = list(lines)
        self.out: list[str] = []

    def read(self, prompt: str) -> str:
        del prompt
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)

    def write(self, text: str) -> None:
        self.out.append(text)

    @property
    def console(self) -> Console:
        return Console(read=self.read, write=self.write)

    @property
    def text(self) -> str:
        return "\n".join(self.out)


def short_rules(tmp_path: Path) -> Path:
    path = tmp_path / "short.toml"
    path.write_text(Rules(stages=1).to_toml(), encoding="utf-8")
    return path


def test_parse_command() -> None:
    assert parse_command("") == ("e", ())
    assert parse_command("B 2") == ("b", (2,))
    assert parse_command("o") == ("o", ())
    assert parse_command("i 0 1") == ("i", (0, 1))
    assert parse_command("m 0 3 2") == ("m", (0, 3, 2))
    for bad in ("b x", "b 1 2 3 4"):
        with pytest.raises(ValueError, match="whole number"):
            parse_command(bad)


def test_full_match_is_played_saved_and_verified(tmp_path: Path) -> None:
    rules_path = short_rules(tmp_path)
    replay_path = tmp_path / "match.json"
    script = ["h", "o", "b 0", "f 0", "zz", "b 99", "b x", "p", "", "x", "c 0 1", "i 0 0", "", "e"]
    fake = FakeConsole(script)
    status = main(
        [
            "play",
            "--seed",
            "5",
            "--bots",
            "2",
            "--rules",
            str(rules_path),
            "--replay",
            str(replay_path),
        ],
        fake.console,
    )
    assert status == 0
    assert "Commands" in fake.text
    assert "unknown command 'zz'" in fake.text
    assert "cannot: shop slot 99" in fake.text
    assert "cannot: a command takes" in fake.text
    assert "Odds of winning" in fake.text
    assert "Market slice:" in fake.text
    assert "crafted " in fake.text
    assert "now holds" in fake.text
    assert "Final placements" in fake.text
    assert replay_path.exists()
    check = FakeConsole([])
    assert (
        main(["replay", str(replay_path), "--verify", "--rules", str(rules_path)], check.console)
        == 0
    )
    assert "verified" in check.text


def test_quitting_abandons_the_match(tmp_path: Path) -> None:
    fake = FakeConsole(["q"])
    assert main(["play", "--rules", str(short_rules(tmp_path))], fake.console) == 1
    assert "abandoned" in fake.text
    silent = FakeConsole([])
    assert main(["play", "--rules", str(short_rules(tmp_path))], silent.console) == 1


def test_play_rejects_a_bad_bot_count() -> None:
    fake = FakeConsole([])
    assert main(["play", "--bots", "0"], fake.console) == 2
    assert "error: bots must be" in fake.text


def test_play_continues_with_bots_after_the_seat_is_eliminated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class SeatLoses:
        def resolve(
            self, home: Player, away: Player, _rng: object, _ctx: object, /
        ) -> CombatResult:
            loser, winner = (home, away) if home.name == "you" else (away, home)
            return CombatResult(winner.name, loser.name, 9)

    original = Game

    def hobbled_game(names: Sequence[str], seed: int = 0, **kwargs: Any) -> Game:
        kwargs["resolver"] = SeatLoses()
        return original(names, seed, **kwargs)

    monkeypatch.setattr(cli, "Game", hobbled_game)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(Rules(stages=3, starting_health=20).to_toml(), encoding="utf-8")
    replay_path = tmp_path / "lost.json"
    fake = FakeConsole(["e"] * 60)
    argv = ["play", "--bots", "1", "--rules", str(rules_path), "--replay", str(replay_path)]
    assert main(argv, fake.console) == 0
    assert "Final placements" in fake.text
    assert "Eliminated: you" in fake.text
    assert replay_path.exists()


def test_sim_prints_placements() -> None:
    fake = FakeConsole([])
    assert main(["sim", "--seed", "3", "--players", "4"], fake.console) == 0
    assert fake.text.count("\n") >= 4
    assert "1. " in fake.text


def test_rules_dump_and_check(tmp_path: Path) -> None:
    fake = FakeConsole([])
    assert main(["rules"], fake.console) == 0
    assert fake.text.startswith("# Ticker Fight Tactics rule set")
    path = tmp_path / "rules.toml"
    path.write_text(fake.text + "\n", encoding="utf-8")
    check = FakeConsole([])
    assert main(["rules", "--check", str(path)], check.console) == 0
    assert "ok:" in check.text
    path.write_text("shop_size = 0\n", encoding="utf-8")
    bad = FakeConsole([])
    assert main(["rules", "--check", str(path)], bad.console) == 2
    assert "error:" in bad.text


def test_replay_command_reports_missing_results_and_mismatches(tmp_path: Path) -> None:
    rules_path = short_rules(tmp_path)
    replay_path = tmp_path / "match.json"
    fake = FakeConsole(["e"] * 5)
    argv = ["play", "--bots", "1", "--rules", str(rules_path), "--replay", str(replay_path)]
    assert main(argv, fake.console) == 0
    recorded = Replay.load(replay_path)
    recorded.result = list(reversed(recorded.result or []))
    recorded.save(replay_path)
    bad = FakeConsole([])
    assert (
        main(["replay", str(replay_path), "--verify", "--rules", str(rules_path)], bad.console) == 1
    )
    assert "MISMATCH" in bad.text
    recorded.result = None
    recorded.save(replay_path)
    none = FakeConsole([])
    assert (
        main(["replay", str(replay_path), "--verify", "--rules", str(rules_path)], none.console)
        == 1
    )
    assert "no recorded result" in none.text
    plain = FakeConsole([])
    assert main(["replay", str(replay_path), "--rules", str(rules_path)], plain.console) == 0
    assert plain.text.startswith("Placements: ")
    missing = FakeConsole([])
    assert main(["replay", str(tmp_path / "nope.json")], missing.console) == 2


def test_render_status_shows_the_augment_offer() -> None:
    player = Player("you", gold=3)
    player.shop = [None] * 5
    player.pending_augments = list(AUGMENTS[:2])
    text = render_status(player, RoundId.make(2, 1))
    assert "Augment offer: [0] Windfall" in text
    assert "Shop: [0] -, [1] -" in text


def test_scout_and_augment_commands_in_a_round(tmp_path: Path) -> None:
    fake = FakeConsole(["o", "a 0", "a 9", ""] + ["e"] * 20)
    rules = Rules(stages=2)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(rules.to_toml(), encoding="utf-8")
    status = main(
        ["play", "--bots", "2", "--rules", str(rules_path), "--replay", str(tmp_path / "r.json")],
        fake.console,
    )
    assert status == 0
    assert "ana:" in fake.text


def test_version_flag() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0


def test_rendering_edge_cases() -> None:
    assert render_scout([]) == "Nobody else is left."
    report = RoundReport(RoundId.make(2, 2), (CombatResult(None, None, 0),), ("bo",))
    text = render_report(report)
    assert "a draw" in text
    assert "Eliminated: bo" in text
    player = Player("you")
    with pytest.raises(ValueError, match="not been rolled"):
        render_status(player, RoundId.make(1, 1))
    game = Game(["you", "ana"], policies={"you": None})
    with pytest.raises(ValueError, match="empty command"):
        handle_command(game, game.player("you"), ("", ()), FakeConsole([]).console, [])
    assert standard_console().read is input


def test_default_replay_path_is_timestamped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    fake = FakeConsole(["e"] * 5)
    assert main(["play", "--bots", "1", "--rules", str(short_rules(tmp_path))], fake.console) == 0
    saved = list((tmp_path / "replays").glob("match-0-*.json"))
    assert len(saved) == 1


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["tft", "--version"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("tft", run_name="__main__", alter_sys=True)
    assert exit_info.value.code == 0


def test_no_market_and_pack_options(tmp_path: Path) -> None:
    rules_path = short_rules(tmp_path)
    fake = FakeConsole(["p", "e", "e", "e"])
    argv = [
        "play",
        "--bots",
        "1",
        "--no-market",
        "--rules",
        str(rules_path),
        "--replay",
        str(tmp_path / "r.json"),
    ]
    assert main(argv, fake.console) == 0
    assert "power comparison" in fake.text
    assert "cannot: the preview needs a market pack" in fake.text
    sim = FakeConsole([])
    assert (
        main(["sim", "--players", "3", "--no-market", "--rules", str(rules_path)], sim.console) == 0
    )
    from tft.market import load_builtin  # noqa: PLC0415

    pack_path = tmp_path / "pack.json"
    load_builtin().save(pack_path)
    custom = FakeConsole(["e"] * 4)
    argv = [
        "play",
        "--bots",
        "1",
        "--pack",
        str(pack_path),
        "--rules",
        str(rules_path),
        "--replay",
        str(tmp_path / "m.json"),
    ]
    assert main(argv, custom.console) == 0
    assert "market pack starter" in custom.text
    check = FakeConsole([])
    assert (
        main(
            ["replay", str(tmp_path / "m.json"), "--verify", "--rules", str(rules_path)],
            check.console,
        )
        == 0
    )
    assert "verified" in check.text
    with_pack = FakeConsole([])
    argv = [
        "replay",
        str(tmp_path / "m.json"),
        "--verify",
        "--rules",
        str(rules_path),
        "--pack",
        str(pack_path),
    ]
    assert main(argv, with_pack.console) == 0


def test_replay_with_an_unknown_pack_name_needs_the_file(tmp_path: Path) -> None:
    rules_path = short_rules(tmp_path)
    replay_path = tmp_path / "r.json"
    fake = FakeConsole(["e"] * 4)
    assert (
        main(
            ["play", "--bots", "1", "--rules", str(rules_path), "--replay", str(replay_path)],
            fake.console,
        )
        == 0
    )
    recorded = Replay.load(replay_path)
    recorded.pack = "elsewhere"
    recorded.save(replay_path)
    missing = FakeConsole([])
    assert main(["replay", str(replay_path), "--rules", str(rules_path)], missing.console) == 2
    assert "pass it with --pack" in missing.text
