"""Tests for :mod:`tft.view`."""

from __future__ import annotations

import json

from tft.combat import CombatResult
from tft.environment import AUGMENTS, Game, Player, RoundId, RoundReport, Unit
from tft.items import Component, Effect, craft
from tft.lessons import summarize
from tft.market import load_builtin
from tft.roster import champion
from tft.rules import DEFAULT_RULES
from tft.view import (
    augment_view,
    board_view,
    catalog,
    effect_text,
    income_view,
    item_view,
    match_state,
    private_seat,
    public_seat,
    report_view,
    round_view,
    shop_view,
    summary_view,
    trait_views,
    unit_view,
)

PIP = champion("Pip Squeak")
DRONE = champion("Index Drone")
GAZELLE = champion("Gap Gazelle")


def test_effect_text_lists_what_an_effect_changes() -> None:
    assert effect_text(Effect()) == "no effect"
    full = Effect(8, 13, 15, -20, "Tech", 1)
    assert effect_text(full) == (
        "stop x0.8, target x1.3, size +15%, drawdown shield -20%, counts as Tech, +1 board slot"
    )
    assert effect_text(Effect(shield_percent=35)) == "drawdown shield +35%"


def test_item_and_augment_views() -> None:
    item = craft(Component.STOP_ORDER, Component.LIMIT_ORDER)
    assert item_view(item) == {
        "name": "Bracket Order",
        "components": ["Stop Order", "Limit Order"],
        "effect": "stop x0.8, target x1.3",
    }
    assert augment_view(AUGMENTS[0]) == {
        "name": "Windfall",
        "tier": "gold",
        "text": "Receive 20 gold now.",
    }


def test_unit_view_with_and_without_a_cell_or_a_pack() -> None:
    pack = load_builtin()
    fielded = Unit(GAZELLE, star=2, position=(3, 1), items=[craft(*[Component.STOP_ORDER] * 2)])
    view = unit_view(fielded, 4, pack, DEFAULT_RULES)
    assert view["index"] == 4
    assert (view["name"], view["cost"], view["origin"], view["role"]) == (
        "Gap Gazelle",
        2,
        "Equities",
        "Momentum",
    )
    assert (view["star"], view["power"], view["sell"]) == (2, 25, 5)
    assert view["cell"] == [3, 1]
    assert view["symbol"] == pack.symbols_for("Equities")[1]
    assert view["items"][0]["name"] == "Trailing Stop"
    assert view["traits"] == ["Equities", "Momentum"]
    benched = unit_view(Unit(PIP), 0, pack, DEFAULT_RULES)
    assert (benched["cell"], benched["symbol"]) == (None, None)
    assert unit_view(fielded, 0, None, DEFAULT_RULES)["symbol"] is None


def test_trait_views_are_sorted_strongest_first() -> None:
    player = Player("you", level=5)
    player.board = [Unit(DRONE), Unit(GAZELLE), Unit(PIP)]
    views = trait_views(player)
    assert views[0]["name"] == "Equities"
    assert (views[0]["count"], views[0]["tier"], views[0]["bonus"]) == (2, 1, 10)
    assert views[0]["breakpoints"] == [2, 4, 6]
    assert {view["name"] for view in views} == {"Equities", "Quant", "Momentum", "Forex", "Scalper"}
    assert all(view["tier"] == 0 for view in views[1:])
    assert trait_views(Player("empty")) == []


def test_shop_and_income_views() -> None:
    player = Player("you", gold=1, streak=-5)
    player.shop = [PIP, None, GAZELLE]
    shop = shop_view(player)
    assert shop[1] is None
    assert shop[0] == {
        "slot": 0,
        "name": "Pip Squeak",
        "cost": 1,
        "origin": "Forex",
        "role": "Scalper",
        "affordable": True,
    }
    assert shop[2] is not None
    assert shop[2]["affordable"] is False
    assert income_view(Player("you", gold=34, streak=4)) == {
        "base": 5,
        "interest": 3,
        "streak": 2,
        "total": 10,
    }


def test_public_seat_hides_what_private_seat_shows() -> None:
    player = Player("you", gold=7, level=2)
    player.board, player.bench = [Unit(DRONE, position=(1, 3))], [Unit(PIP)]
    player.shop = [PIP] * 5
    player.components = [Component.STOP_ORDER]
    player.items = [craft(Component.STOP_ORDER, Component.LIMIT_ORDER)]
    player.augments = [AUGMENTS[0]]
    player.pending_augments = [AUGMENTS[1], AUGMENTS[2]]
    public = public_seat(player, None, DEFAULT_RULES)
    assert set(public) == {
        "name",
        "health",
        "max_health",
        "level",
        "gold",
        "streak",
        "alive",
        "board",
        "traits",
    }
    private = private_seat(player, None, DEFAULT_RULES)
    assert set(private) > set(public)
    assert [unit["index"] for unit in private["board"]] == [0]
    assert [unit["index"] for unit in private["bench"]] == [1]
    assert (private["xp"], private["xp_needed"], private["board_limit"]) == (0, 2, 2)
    assert private["components"] == ["Stop Order"]
    assert private["items"][0]["name"] == "Bracket Order"
    assert [augment["name"] for augment in private["offer"]] == ["Compound Interest", "Tight Stops"]
    assert private["odds"] == [100, 0, 0, 0, 0]
    assert private_seat(Player("max", level=10), None, DEFAULT_RULES)["xp_needed"] is None


def test_round_and_board_views() -> None:
    game = Game(["you", "ana"])
    assert round_view(None, game) is None
    view = round_view(RoundId.make(2, 4), game)
    assert view == {
        "label": "2-4",
        "stage": 2,
        "number": 4,
        "pve": False,
        "carousel": True,
        "augment": False,
        "index": 0,
        "total": 45,
    }
    assert board_view(DEFAULT_RULES) == {
        "rows": 4,
        "cols": 7,
        "row_size": [80, 90, 100, 120],
        "row_shield": [30, 15, 0, 0],
        "cover": 25,
        "exposed": 25,
    }


def test_match_state_for_a_seat_a_spectator_and_a_finished_match() -> None:
    game = Game(["you", "ana", "bo"], seed=3, pack=load_builtin(), policies={"you": None})
    _ = game.start_round()
    state = match_state(game, "you")
    assert (state["phase"], state["mode"], state["pack"]) == ("planning", "market", "starter")
    assert state["round"]["label"] == "1-1"
    assert state["seat"]["name"] == "you"
    assert [seat["name"] for seat in state["others"]] == ["ana", "bo"]
    assert "shop" not in state["others"][0]
    assert state["placements"] is None
    assert state["costs"] == {"reroll": 2, "xp": 4, "xp_gain": 4}
    watching = match_state(game, None)
    assert watching["seat"] is None
    assert [seat["name"] for seat in watching["others"]] == ["you", "ana", "bo"]
    assert json.loads(json.dumps(state)) == state
    done = Game(["ana", "bo"], seed=1)
    _ = done.run()
    finished = match_state(done, None)
    assert (finished["phase"], finished["mode"], finished["pack"]) == ("finished", "power", None)
    assert finished["round"] is None
    assert sorted(finished["placements"]) == ["ana", "bo"]


def test_report_view_names_both_sides_even_for_old_results() -> None:
    modern = CombatResult("ana", "bo", 2, "bo", "ana", 1.5, 3.5)
    legacy = CombatResult("ana", "bo", 1)
    draw = CombatResult(None, None, 0, "ana", "bo", 2.0, 2.0)
    report = RoundReport(RoundId.make(2, 2), (modern, legacy, draw), ("bo",), "a to b")
    view = report_view(report)
    assert (view["round"], view["slice"], view["eliminated"]) == ("2-2", "a to b", ["bo"])
    first, second, third = view["fights"]
    assert (first["home"], first["away"], first["winner"], first["home_score"]) == (
        "bo",
        "ana",
        "ana",
        1.5,
    )
    assert (second["home"], second["away"], second["survivors"]) == ("ana", "bo", 1)
    assert third["draw"] is True


def test_summary_view_is_plain_data() -> None:
    game = Game(["you", "ana"], seed=5, pack=load_builtin(), policies={"you": None})
    _ = game.start_round()
    you = game.player("you")
    you.buy(0, game.pool)
    you.field_unit(you.bench[0])
    view = summary_view(summarize(game, "you", game.finish_round()))
    assert json.loads(json.dumps(view))["round_label"] == "1-1"
    assert isinstance(view["units"][0]["closes"], tuple)
    assert set(view) == {
        "round_label",
        "slice_label",
        "opponent",
        "outcome",
        "score",
        "opponent_score",
        "damage",
        "units",
        "origin_moves",
        "lessons",
    }


def test_catalog_lists_the_static_content() -> None:
    content = catalog(DEFAULT_RULES)
    assert len(content["champions"]) == 25
    assert len(content["traits"]) == 14
    assert len(content["items"]) == 36
    assert len(content["components"]) == 8
    assert len(content["augments"]) == 6
    assert set(content["strategies"]) == {trait["name"] for trait in content["traits"] if trait["kind"] == "class"}
    assert content["champions"][0]["text"]
    assert content["board"]["rows"] == 4
    assert json.loads(json.dumps(content)) == content
