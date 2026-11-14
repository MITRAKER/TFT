"""Tests for :mod:`tft.lessons`."""

from __future__ import annotations

from typing import Any

import pytest

from tft import lessons
from tft.combat import CombatResult
from tft.environment import Game, Player, RoundId, RoundReport, Unit
from tft.items import Component, craft
from tft.lessons import Facts, UnitLine, pick_lessons, summarize
from tft.market import load_builtin
from tft.roster import champion

PIP = champion("Pip Squeak")
BULL = champion("Breakout Bull")
CLERK = champion("Coupon Clerk")


def line(**changes: Any) -> UnitLine:
    base: dict[str, Any] = {
        "unit": "Pip Squeak 1*",
        "champion": "Pip Squeak",
        "role": "Scalper",
        "origin": "Forex",
        "symbol": "AAA",
        "cell": (3, 3),
        "items": (),
        "pnl": 0.0,
        "drawdown": 0.0,
        "trades": 1,
        "score": 0.0,
        "raw_move": 0.0,
        "closes": (100.0, 101.0, 102.0),
        "marks": (),
    }
    base.update(changes)
    return UnitLine(**base)


def facts(
    player: Player | None = None,
    units: tuple[UnitLine, ...] = (),
    *,
    stage: int = 2,
    game: Game | None = None,
) -> Facts:
    match = game if game is not None else Game(["you", "ana"])
    seat = player if player is not None else match.player("you")
    return Facts(match, seat, RoundId.make(stage, 2), "lost", units)


def test_unit_line_helpers() -> None:
    one = line(marks=((1, "buy"), (2, "stop")), closes=(100.0, 110.0, 99.0), role="Momentum")
    assert one.held_from(1) == pytest.approx(-10.0)
    assert one.mark("stop") == 2
    assert one.mark("target") is None
    assert one.entry == 1
    assert one.one_position
    assert line().entry == 0
    assert not line(role="Quant", marks=((0, "buy"), (1, "stop"))).one_position
    assert not line(marks=((0, "buy"), (1, "stop"), (2, "buy"), (2, "close"))).one_position


def test_empty_slots() -> None:
    player = Player("you", level=2)
    player.board, player.bench = [Unit(PIP)], [Unit(BULL)]
    text = lessons.empty_slots(facts(player))
    assert text is not None
    assert "1 of 2 units" in text
    player.bench = []
    assert lessons.empty_slots(facts(player)) is None
    player.board, player.bench = [Unit(PIP), Unit(BULL)], [Unit(CLERK)]
    assert lessons.empty_slots(facts(player)) is None


def test_stopped_out_tells_a_saving_stop_from_a_costly_one() -> None:
    stop = {"marks": ((0, "buy"), (1, "stop")), "pnl": -2.05, "role": "Momentum"}
    saved = lessons.stopped_out(facts(units=(line(closes=(100.0, 97.0, 90.0), **stop),)))
    assert saved is not None
    assert "would have made -10.0%" in saved
    costly = lessons.stopped_out(facts(units=(line(closes=(100.0, 97.0, 104.0), **stop),)))
    assert costly is not None
    assert "then finished at +4.0%" in costly
    quant = line(**{**stop, "role": "Quant"})
    assert lessons.stopped_out(facts(units=(quant,))) is None
    assert lessons.stopped_out(facts(units=(line(),))) is None


def test_took_profit_tells_a_capped_win_from_a_banked_one() -> None:
    target = {"marks": ((0, "buy"), (1, "target")), "pnl": 3.95, "role": "Momentum"}
    capped = lessons.took_profit(facts(units=(line(closes=(100.0, 104.0, 110.0), **target),)))
    assert capped is not None
    assert "went on to +10.0%" in capped
    banked = lessons.took_profit(facts(units=(line(closes=(100.0, 104.0, 101.0), **target),)))
    assert banked is not None
    assert "before it finished at +1.0%" in banked
    assert lessons.took_profit(facts(units=(line(),))) is None


def test_hedge_paid() -> None:
    hedger = {"role": "Hedger", "champion": "Coupon Clerk", "pnl": -2.5}
    text = lessons.hedge_paid(facts(units=(line(raw_move=-8.0, **hedger),)))
    assert text is not None
    assert "held its loss to -2.5% while AAA moved -8.0%" in text
    assert lessons.hedge_paid(facts(units=(line(raw_move=-3.0, **hedger),))) is None
    assert lessons.hedge_paid(facts(units=(line(raw_move=-8.0, pnl=-2.5),))) is None


def test_unprotected_loss_names_the_worst_bare_loser() -> None:
    mild = line(champion="Mild", pnl=-2.0, drawdown=2.0, score=-3.0)
    bad = line(champion="Bad", pnl=-4.0, drawdown=5.0, score=-9.0)
    armoured = line(champion="Armoured", pnl=-9.0, score=-20.0, items=("Trailing Stop",))
    text = lessons.unprotected_loss(facts(units=(mild, bad, armoured)))
    assert text is not None
    assert text.startswith("Bad lost 4.0% on AAA with a 5.0% drawdown")
    assert lessons.unprotected_loss(facts(units=(armoured, line(pnl=-1.0)))) is None


def test_over_trading_and_never_traded() -> None:
    busy = line(trades=8, pnl=-1.2)
    text = lessons.over_trading(facts(units=(busy,)))
    assert text is not None
    assert "made 8 trades on AAA and lost 1.2%" in text
    assert lessons.over_trading(facts(units=(line(trades=8, pnl=1.0),))) is None
    idle = lessons.never_traded(facts(units=(line(trades=0, role="Momentum"),)))
    assert idle is not None
    assert "never traded" in idle
    assert lessons.never_traded(facts(units=(line(),))) is None


def test_concentration() -> None:
    pair = (line(champion="A"), line(champion="B"), line(champion="C", symbol="ZZZ"))
    text = lessons.concentration(facts(units=pair))
    assert text is not None
    assert text.startswith("A and B both trade AAA: one ticker, 2 positions.")
    assert lessons.concentration(facts(units=(line(), line(symbol="BBB")))) is None


def test_exposed_carry() -> None:
    player = Player("you", level=3)
    player.board = [Unit(BULL, position=(3, 3))]
    exposed = line(champion="Breakout Bull", cell=(3, 3), drawdown=2.0)
    text = lessons.exposed_carry(facts(player, (exposed,)))
    assert text is not None
    assert "pays 25% more" in text
    assert lessons.exposed_carry(facts(player, (line(cell=(3, 3), drawdown=0.0),))) is None
    player.board.append(Unit(CLERK, position=(0, 3)))
    assert lessons.exposed_carry(facts(player, (exposed,))) is None
    assert lessons.exposed_carry(facts(player, (line(cell=(0, 3), drawdown=5.0),))) is None


def test_idle_components() -> None:
    player = Player("you")
    assert lessons.idle_components(facts(player)) is None
    player.components = [Component.STOP_ORDER, Component.LIMIT_ORDER]
    text = lessons.idle_components(facts(player))
    assert text is not None
    assert "holding 2 components" in text
    player.components = []
    player.items = [craft(Component.STOP_ORDER, Component.LIMIT_ORDER)]
    text = lessons.idle_components(facts(player))
    assert text is not None
    assert text.startswith("Bracket Order is sitting in your inventory.")


def test_contested() -> None:
    game = Game(["you", "ana", "bo", "cy"])
    you = game.player("you")
    assert lessons.contested(facts(you, game=game)) is None
    you.board = [Unit(PIP), Unit(CLERK)]
    for name in ("ana", "bo"):
        game.player(name).board = [Unit(PIP)]
    game.player("cy").board = [Unit(CLERK)]
    text = lessons.contested(facts(you, game=game))
    assert text is not None
    assert text.startswith("Pip Squeak is on 2 other boards and 30 copies are left")
    game.player("bo").board = []
    assert lessons.contested(facts(you, game=game)) is None


def test_low_health() -> None:
    player = Player("you", health=30, gold=40)
    text = lessons.low_health(facts(player))
    assert text is not None
    assert "30 health and 40 gold" in text
    assert lessons.low_health(facts(Player("you", health=30, gold=10))) is None
    assert lessons.low_health(facts(Player("you", health=90, gold=40))) is None
    assert lessons.low_health(facts(Player("you", health=0, gold=40))) is None


def test_interest() -> None:
    def text_for(gold: int, stage: int = 2) -> str | None:
        return lessons.interest(facts(Player("you", gold=gold), stage=stage))

    assert text_for(47, stage=1) is None
    idle = text_for(72)
    assert idle is not None
    assert "sitting on 72 gold" in idle
    near = text_for(47)
    assert near is not None
    assert near.startswith("You are 3 gold short")
    assert text_for(43) is None
    assert text_for(55) is None


def test_streak() -> None:
    losing = lessons.streak(facts(Player("you", streak=-4)))
    assert losing is not None
    assert losing.startswith("Loss streak of 4: the streak bonus pays you 2 gold")
    winning = lessons.streak(facts(Player("you", streak=5)))
    assert winning is not None
    assert winning.startswith("Win streak of 5: 3 extra gold")
    assert lessons.streak(facts(Player("you", streak=1))) is None


def test_pick_lessons_keeps_the_first_three_in_priority_order() -> None:
    player = Player("you", level=2, health=20, gold=75, streak=-5)
    player.board, player.bench = [Unit(PIP, position=(3, 3))], [Unit(BULL)]
    player.components = [Component.STOP_ORDER] * 3
    picked = pick_lessons(facts(player, (line(trades=9, pnl=-3.0, drawdown=4.0),)))
    assert len(picked) == 3
    assert picked[0].startswith("You fielded 1 of 2 units")
    assert picked[1].startswith("Pip Squeak lost 3.0%")
    assert picked[2].startswith("Pip Squeak made 9 trades")
    assert pick_lessons(facts(Player("you"))) == ()
    assert len(lessons.RULES) == 14


def test_summarize_a_market_round() -> None:
    game = Game(["you", "ana", "bo"], seed=5, pack=load_builtin(), policies={"you": None})
    you = game.player("you")
    _ = game.start_round()
    you.buy(0, game.pool)
    you.field_unit(you.bench[0])
    report = game.finish_round()
    summary = summarize(game, "you", report)
    assert summary.round_label == "1-1"
    assert summary.slice_label == report.slice_label
    assert summary.opponent == "The Market"
    assert summary.outcome in {"won", "lost", "draw"}
    assert (summary.damage > 0) == (summary.outcome == "lost")
    assert len(summary.units) == 1
    unit = summary.units[0]
    assert unit.champion == you.board[0].champion.name
    assert unit.closes[0] == 100.0
    assert len(unit.closes) == game.rules.slice_bars
    assert [origin for origin, _ in summary.origin_moves] == list(load_builtin().origins)
    assert len(summary.lessons) <= lessons.MAX_LESSONS
    with pytest.raises(KeyError, match="no player"):
        summarize(game, "zed", report)


def test_summarize_without_a_market_or_a_fight() -> None:
    game = Game(["you", "ana"], seed=2, policies={"you": None})
    _ = game.start_round()
    report = game.finish_round()
    summary = summarize(game, "you", report)
    assert summary.units == ()
    assert summary.origin_moves == ()
    assert summary.slice_label is None
    quiet = summarize(game, "you", RoundReport(RoundId.make(2, 2), (), ()))
    assert (quiet.outcome, quiet.opponent, quiet.damage, quiet.score) == ("none", None, 0, 0.0)


def test_outcomes_and_damage() -> None:
    game = Game(["you", "ana"])
    report = RoundReport(RoundId.make(3, 2), (), ())
    won = CombatResult("you", "ana", 2, "you", "ana", 4.0, 1.0)
    lost = CombatResult("ana", "you", 3, "you", "ana", 1.0, 4.0)
    draw = CombatResult(None, None, 0, "you", "ana", 2.0, 2.0)
    assert [lessons.outcome_of(r, "you") for r in (won, lost, draw, None)] == [
        "won",
        "lost",
        "draw",
        "none",
    ]
    assert lessons.damage_taken(game, report, lost, "you") == 5 + 3
    assert lessons.damage_taken(game, report, won, "you") == 0
    assert lessons.damage_taken(game, report, draw, "you") == 0
    assert lessons.damage_taken(game, report, None, "you") == 0
    summary = summarize(game, "you", RoundReport(RoundId.make(3, 2), (lost,), ()))
    assert (summary.outcome, summary.opponent, summary.score, summary.opponent_score) == (
        "lost",
        "ana",
        1.0,
        4.0,
    )
    assert summary.damage == 8
