"""Tests for tools/balance_report.py (importable through pytest's ``pythonpath``)."""

from __future__ import annotations

from pathlib import Path
from random import Random

import pytest

import balance_report as tool
from tft.environment import Player, Pool, Unit
from tft.market import Bar, MarketPack, Series, load_builtin
from tft.roster import CHAMPIONS, CLASSES, champion
from tft.rules import DEFAULT_RULES, Rules

SHORT = Rules(stages=2, starting_health=20, slice_bars=5, preview_samples=5)


def small_pack() -> MarketPack:
    """Two symbols over eight dates: one rises a point a day, one falls a point a day."""
    dates = tuple(f"2026-04-{day:02d}" for day in range(1, 9))
    up = Series("UP", tuple(Bar(100 + i, 101.5 + i, 99.5 + i, 101 + i, 1) for i in range(8)))
    down = Series("DOWN", tuple(Bar(100 - i, 100.5 - i, 98.5 - i, 99 - i, 1) for i in range(8)))
    origins: dict[str, tuple[str, ...]] = {"Tech": ("UP",), "Bonds": ("DOWN",)}
    return MarketPack("small", "1d", "test", dates, origins, {"UP": up, "DOWN": down})


def test_trials_cover_every_window_of_every_symbol() -> None:
    pack = small_pack()
    found = tool.trials("Swing", pack.symbols, pack, SHORT)
    assert len(found) == 2 * 4
    assert {trial.start for trial in found} == {0, 1, 2, 3}
    rising = [trial for trial in found if trial.symbol == "UP"]
    falling = [trial for trial in found if trial.symbol == "DOWN"]
    assert all(trial.edge > 0 and trial.factor > 1 for trial in rising)
    assert all(trial.edge < 0 and trial.factor < 1 for trial in falling)
    with pytest.raises(ValueError, match="needs 5 dates"):
        tool.trials("Swing", (), pack, SHORT)
    with pytest.raises(ValueError, match="needs 20 dates"):
        tool.trials("Swing", pack.symbols, pack, Rules(slice_bars=20))


def test_beat_rate_counts_wins_and_half_the_ties() -> None:
    assert tool.beat_rate([2.0], [1.0]) == 1.0
    assert tool.beat_rate([1.0], [2.0]) == 0.0
    assert tool.beat_rate([1.0], [1.0]) == 0.5
    assert tool.beat_rate([1.0, 3.0], [2.0, 2.0]) == 0.5
    assert tool.beat_rate([3.0, 3.0], [1.0, 3.0]) == 0.75
    with pytest.raises(ValueError, match="at least one value"):
        tool.beat_rate([], [1.0])
    with pytest.raises(ValueError, match="at least one value"):
        tool.beat_rate([1.0], [])


def test_field_rates_compare_classes_window_by_window() -> None:
    strong = [tool.Trial("A", 0, 1.0, 1.1), tool.Trial("A", 1, 1.0, 1.1)]
    weak = [tool.Trial("A", 0, -1.0, 0.9), tool.Trial("A", 1, -1.0, 0.9)]
    assert tool.field_rates({"strong": strong, "weak": weak}) == {"strong": 1.0, "weak": 0.0}
    assert tool.field_rates({"alone": strong}) == {"alone": 0.5}
    assert tool.by_window(strong) == {0: [1.1], 1: [1.1]}


def test_the_tables_have_a_row_per_class_and_champion() -> None:
    pack = small_pack()
    classes = tool.class_table(pack, SHORT)
    assert [row[0] for row in classes.rows] == [trait.name for trait in CLASSES]
    assert all(len(row) == len(classes.head) for row in classes.rows)
    origins = tool.origin_table(pack, SHORT)
    assert origins.head == ("Class", "Tech", "Bonds")
    swing = next(row for row in origins.rows if row[0] == "Swing")
    assert float(swing[1]) > 1 > float(swing[2])
    champions = tool.champion_table(pack, SHORT)
    assert [row[0] for row in champions.rows] == [one.name for one in CHAMPIONS]
    yeti = next(row for row in champions.rows if row[0] == "Yield Yeti")
    assert yeti[1:4] == ("2", "Bonds", "Swing")
    assert float(yeti[6]) == pytest.approx(float(yeti[4]) * float(yeti[5]), abs=0.02)
    assert tool.pack_origins(pack) == ("Tech", "Bonds")


def test_the_tables_refuse_a_pack_without_symbols() -> None:
    empty = small_pack()
    empty.series.clear()
    with pytest.raises(ValueError, match="holds no symbol"):
        tool.class_table(empty, SHORT)
    with pytest.raises(ValueError, match="holds no symbol"):
        tool.champion_table(empty, SHORT)


def test_probe_policies_shape_the_board() -> None:
    rules = DEFAULT_RULES
    player = Player("probe", level=5, gold=50)
    pool = Pool(CHAMPIONS, rules)
    names = ("Pip Squeak", "Index Drone", "Barrel Bo", "Coupon Clerk", "Candle Reader")
    player.shop = [champion(name) for name in names]
    tool.idle(player, pool, Random(1))
    assert (player.board, player.bench, player.gold) == ([], [], 50)
    tool.in_rows((3, 2))(player, pool, Random(1))
    assert len(player.board) == 5
    assert [unit.position for unit in player.board] == [(3, 3), (3, 2), (3, 4), (3, 1), (3, 5)]
    player.shop = [None] * rules.shop_size
    tool.in_rows((0, 1))(player, pool, Random(1))
    assert {unit.position[0] for unit in player.board if unit.position} == {0}
    tool.one_unit(player, pool, Random(1))
    assert (len(player.board), len(player.bench)) == (1, 4)
    assert list(tool.probes(rules)) == [
        "greedy bot (default formation)",
        "empty board",
        "one unit",
        "every unit in the back rows",
        "every unit in the front rows",
    ]


def test_one_unit_stops_when_the_bench_is_full() -> None:
    rules = DEFAULT_RULES
    player = Player("probe", level=3)
    player.shop = [None] * rules.shop_size
    player.board = [Unit(champion("Pip Squeak"), position=(3, col)) for col in range(3)]
    player.bench = [Unit(champion("Index Drone")) for _ in range(rules.bench_size - 1)]
    tool.one_unit(player, Pool(CHAMPIONS, rules), Random(1))
    assert len(player.bench) == rules.bench_size
    assert len(player.board) == 2


def test_an_empty_board_places_last_and_the_bot_does_not() -> None:
    pack = load_builtin()
    assert tool.mean_placement(tool.idle, pack, SHORT, 3) == 8.0
    assert tool.mean_placement(tool.one_unit, pack, SHORT, 3) > 6.0
    assert (
        1.0
        <= tool.mean_placement(tool.probes(SHORT)["greedy bot (default formation)"], pack, SHORT, 3)
        < 8.0
    )
    with pytest.raises(ValueError, match="matches must be positive"):
        tool.mean_placement(tool.idle, pack, SHORT, 0)


def test_rendering_text_and_markdown() -> None:
    table = tool.Table("Demo", "A note.", ("Name", "Value"), (("alpha", "1.00"), ("b", "10.50")))
    assert tool.render_text(table).splitlines() == [
        "== Demo ==",
        "A note.",
        "Name   Value",
        "alpha   1.00",
        "b      10.50",
    ]
    assert tool.render_markdown(table).splitlines() == [
        "### Demo",
        "",
        "A note.",
        "",
        "| Name | Value |",
        "| --- | ---: |",
        "| alpha | 1.00 |",
        "| b | 10.50 |",
    ]


def test_report_and_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pack = small_pack()
    text = tool.report(pack, SHORT, 0)
    assert text.startswith("Pack small: 2 symbols, 2026-04-01 to 2026-04-08, 4 windows of 5 bars.")
    assert "== Classes ==" in text
    assert "== Policies ==" not in text
    assert "### Champions" in tool.report(pack, SHORT, 0, "markdown")
    with pytest.raises(ValueError, match="format must be one of"):
        tool.report(pack, SHORT, 0, "html")
    pack_file, rules_file = tmp_path / "pack.json", tmp_path / "rules.toml"
    pack.save(pack_file)
    rules_file.write_text(SHORT.to_toml(), encoding="utf-8")
    arguments = ["--pack", str(pack_file), "--rules", str(rules_file)]
    assert tool.main([*arguments, "--matches", "1", "--format", "markdown"]) == 0
    out = capsys.readouterr().out
    assert "### Policies" in out
    assert "| empty board | 8.00 |" in out
    assert tool.main(["--pack", str(tmp_path / "missing.json"), "--matches", "0"]) == 2
    assert "balance_report:" in capsys.readouterr().err
    assert tool.main(["--matches", "0"]) == 0
    assert "Pack starter: 29 symbols" in capsys.readouterr().out
