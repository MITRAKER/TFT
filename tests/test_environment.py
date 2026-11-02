"""Tests for :mod:`tft.environment`."""

from __future__ import annotations

from random import Random

import pytest

from tft import environment as env
from tft.environment import (
    AUGMENTS,
    BENCH_SIZE,
    MAX_LEVEL,
    MAX_ROUNDS,
    POOL_SIZES,
    SHOP_ODDS,
    SHOP_SIZE,
    STARTING_HEALTH,
    CombatResult,
    Game,
    Player,
    Pool,
    PowerResolver,
    RoundId,
    Unit,
    greedy_policy,
    market_power,
    roll_shop,
    round_sequence,
    sell_value,
    stage_damage,
)
from tft.roster import CHAMPIONS, champion, champions_of_cost

PIP = champion("Pip Squeak")
DRONE = champion("Index Drone")
GAZELLE = champion("Gap Gazelle")
BULL = champion("Breakout Bull")


def stocked_player(gold: int = 50, level: int = 1) -> Player:
    player = Player("tester", gold=gold, level=level)
    player.shop = [PIP, DRONE, GAZELLE, None, BULL]
    return player


# Rounds ---------------------------------------------------------------------


def test_round_sequence_shape_and_labels() -> None:
    rounds = round_sequence()
    assert len(rounds) == MAX_ROUNDS == 45
    assert [round_id.label for round_id in rounds[:5]] == ["1-1", "1-2", "1-3", "2-1", "2-2"]
    assert rounds[-1].label == "7-7"
    assert round_sequence(5)[-1].label == "2-2"


def test_round_flags() -> None:
    assert RoundId(1, 2).is_pve
    assert RoundId(3, 7).is_pve
    assert not RoundId(3, 6).is_pve
    assert RoundId(2, 4).is_carousel
    assert not RoundId(1, 3).is_carousel
    assert all(RoundId(stage, number).is_augment for stage, number in ((2, 1), (3, 2), (4, 2)))
    assert not RoundId(2, 2).is_augment


def test_round_sequence_rejects_a_non_positive_length() -> None:
    with pytest.raises(ValueError, match="positive"):
        round_sequence(0)


def test_stage_damage_and_market_power_grow_with_the_stage() -> None:
    assert [stage_damage(stage) for stage in (1, 2, 7, 9)] == [0, 2, 17, 17]
    assert market_power(RoundId(1, 1)) < market_power(RoundId(2, 1)) < market_power(RoundId(3, 1))
    assert market_power(RoundId(3, 7)) > market_power(RoundId(3, 6))


# Shop and pool --------------------------------------------------------------


def test_shop_odds_rows_sum_to_one_hundred() -> None:
    assert set(SHOP_ODDS) == set(range(1, MAX_LEVEL + 1))
    assert all(sum(row) == 100 for row in SHOP_ODDS.values())


def test_pool_take_and_give_back() -> None:
    pool = Pool()
    assert pool.remaining("Pip Squeak") == POOL_SIZES[1]
    pool.take("Pip Squeak", 3)
    assert pool.remaining("Pip Squeak") == POOL_SIZES[1] - 3
    pool.give_back("Pip Squeak", 2)
    assert pool.remaining("Pip Squeak") == POOL_SIZES[1] - 1
    with pytest.raises(ValueError, match="copies"):
        pool.take("Black Swan", POOL_SIZES[5] + 1)
    with pytest.raises(KeyError, match="not in the pool"):
        pool.remaining("Nobody")


def test_pool_available_drops_exhausted_champions() -> None:
    pool = Pool()
    assert [unit.name for unit in pool.available(5)] == sorted(u.name for u in champions_of_cost(5))
    pool.take("Black Swan", POOL_SIZES[5])
    assert "Black Swan" not in [unit.name for unit in pool.available(5)]


def test_roll_shop_respects_level_odds_and_the_pool() -> None:
    rng = Random(7)
    pool = Pool()
    shop = roll_shop(1, pool, rng)
    assert len(shop) == SHOP_SIZE
    assert all(unit is not None and unit.cost == 1 for unit in shop)
    assert pool.remaining("Pip Squeak") == POOL_SIZES[1]
    exhausted = Pool([PIP])
    exhausted.take("Pip Squeak", POOL_SIZES[1])
    assert roll_shop(1, exhausted, rng) == [None] * SHOP_SIZE
    with pytest.raises(ValueError, match="odds"):
        roll_shop(11, pool, rng)


@pytest.mark.parametrize(
    ("cost", "star", "expected"),
    [(1, 1, 1), (1, 2, 3), (1, 3, 9), (2, 1, 2), (2, 2, 5), (3, 3, 26), (4, 2, 11), (5, 1, 5)],
)
def test_sell_value_table(cost: int, star: int, expected: int) -> None:
    assert sell_value(cost, star) == expected


def test_sell_value_rejects_bad_stars() -> None:
    with pytest.raises(ValueError, match="star"):
        sell_value(1, 4)


def test_unit_power_and_copies_by_star() -> None:
    assert [Unit(PIP, star).power for star in (1, 2, 3)] == [10, 18, 32]
    assert [Unit(PIP, star).copies for star in (1, 2, 3)] == [1, 3, 9]


# Player ---------------------------------------------------------------------


def test_buy_moves_gold_pool_and_bench() -> None:
    player, pool = stocked_player(gold=5), Pool()
    player.buy(0, pool)
    assert player.gold == 4
    assert [unit.champion.name for unit in player.bench] == ["Pip Squeak"]
    assert player.shop[0] is None
    assert pool.remaining("Pip Squeak") == POOL_SIZES[1] - 1


def test_buy_rejects_bad_purchases() -> None:
    player, pool = stocked_player(gold=1), Pool()
    with pytest.raises(ValueError, match="does not exist"):
        player.buy(9, pool)
    with pytest.raises(ValueError, match="empty"):
        player.buy(3, pool)
    with pytest.raises(ValueError, match="gold"):
        player.buy(4, pool)
    rich = stocked_player(gold=50)
    rich.bench = [Unit(unit) for unit in CHAMPIONS[:BENCH_SIZE]]
    with pytest.raises(ValueError, match="bench is full"):
        rich.buy(4, pool)


def test_buying_the_third_copy_merges_even_on_a_full_bench() -> None:
    player, pool = stocked_player(gold=50), Pool()
    player.bench = [Unit(unit) for unit in CHAMPIONS[1 : BENCH_SIZE - 1]] + [Unit(PIP), Unit(PIP)]
    assert len(player.bench) == BENCH_SIZE
    player.buy(0, pool)
    stars = [unit.star for unit in player.bench if unit.champion is PIP]
    assert stars == [2]
    assert len(player.bench) == BENCH_SIZE - 1


def test_merge_reaches_three_stars_from_nine_copies() -> None:
    player = Player("tester")
    player.board = [Unit(PIP)]
    player.bench = [Unit(PIP) for _ in range(8)]
    player.merge("Pip Squeak")
    assert [unit.star for unit in player.units] == [3]


def test_sell_returns_gold_and_copies() -> None:
    player, pool = Player("tester"), Pool()
    pool.take("Gap Gazelle", 3)
    unit = Unit(GAZELLE, star=2)
    player.board = [unit]
    assert player.sell(unit, pool) == 5
    assert player.gold == 5
    assert player.board == []
    assert pool.remaining("Gap Gazelle") == POOL_SIZES[2]
    with pytest.raises(ValueError, match="does not own"):
        player.sell(unit, pool)


def test_xp_levels_and_the_cap() -> None:
    player = Player("tester")
    player.add_xp(2)
    assert (player.level, player.xp) == (2, 0)
    player.add_xp(7)
    assert (player.level, player.xp) == (3, 5)
    player.add_xp(10_000)
    assert player.level == MAX_LEVEL
    with pytest.raises(ValueError, match="negative"):
        player.add_xp(-1)
    with pytest.raises(ValueError, match="already level"):
        player.buy_xp()


def test_buy_xp_costs_gold() -> None:
    player = Player("tester", gold=4)
    player.buy_xp()
    assert (player.gold, player.level, player.xp) == (0, 3, 0)
    with pytest.raises(ValueError, match="gold"):
        player.buy_xp()


def test_reroll_costs_gold_and_rolls_a_shop() -> None:
    player, pool, rng = Player("tester", gold=2), Pool(), Random(1)
    player.reroll(pool, rng)
    assert player.gold == 0
    assert len(player.shop) == SHOP_SIZE
    with pytest.raises(ValueError, match="reroll"):
        player.reroll(pool, rng)


def test_field_unit_respects_the_board_limit() -> None:
    player = Player("tester")
    first, second = Unit(PIP), Unit(DRONE)
    player.bench = [first, second]
    player.field_unit(first)
    assert player.board == [first]
    with pytest.raises(ValueError, match="board holds"):
        player.field_unit(second)
    with pytest.raises(ValueError, match="not on"):
        player.field_unit(first)


def test_team_power_applies_trait_and_augment_bonuses() -> None:
    player = Player("tester", level=3)
    player.board = [Unit(DRONE), Unit(GAZELLE)]
    base = DRONE.power + GAZELLE.power
    assert player.team_power == base * 110 // 100
    player.augments.append(AUGMENTS[-1])
    assert player.team_power == base * 140 // 100
    assert Player("empty").team_power == 0


def test_streaks_extend_flip_and_break() -> None:
    player = Player("tester")
    for won in (True, True):
        player.record_result(won)
    assert player.streak == 2
    player.record_result(False)
    assert player.streak == -1
    player.record_result(False)
    assert player.streak == -2
    player.record_result(None)
    assert player.streak == 0


def test_income_damage_and_elimination() -> None:
    player = Player("tester", gold=50, streak=5)
    player.collect_income()
    assert player.gold == 50 + 5 + 5 + 3
    player.take_damage(STARTING_HEALTH + 5)
    assert player.health == 0
    assert not player.alive
    with pytest.raises(ValueError, match="negative"):
        player.take_damage(-1)


# Policy and resolver --------------------------------------------------------


def test_greedy_policy_buys_fields_and_levels() -> None:
    player, pool = stocked_player(gold=30, level=2), Pool()
    greedy_policy(player, pool, Random(0))
    assert len(player.board) == 2
    assert player.board[0].power >= player.board[1].power
    assert player.gold < 30
    assert player.level >= 2
    unrolled = Player("tester")
    with pytest.raises(ValueError, match="not been rolled"):
        greedy_policy(unrolled, pool, Random(0))


def test_greedy_policy_buys_experience_only_with_a_reserve() -> None:
    poor = Player("poor", gold=5)
    poor.shop = [None] * SHOP_SIZE
    greedy_policy(poor, Pool(), Random(0))
    assert (poor.gold, poor.level) == (5, 1)
    rich = Player("rich", gold=14)
    rich.shop = [None] * SHOP_SIZE
    greedy_policy(rich, Pool(), Random(0))
    assert (rich.gold, rich.level) == (10, 3)


def test_power_resolver_outcomes() -> None:
    strong, weak = Player("strong", level=2), Player("weak")
    strong.board = [Unit(BULL), Unit(GAZELLE)]
    weak.board = [Unit(PIP)]
    result = PowerResolver().resolve(strong, weak, Random(0))
    assert (result.winner, result.loser) == ("strong", "weak")
    assert 1 <= result.survivors <= 2
    mirrored = PowerResolver().resolve(weak, strong, Random(0))
    assert mirrored.winner == "strong"
    assert PowerResolver().resolve(weak, Player("empty"), Random(0)).winner == "weak"
    assert PowerResolver().resolve(Player("a"), Player("b"), Random(0)).is_draw


# Game -----------------------------------------------------------------------


NAMES = ["ana", "bo", "cy", "di", "ed", "fay", "gus", "hal"]


def test_game_rejects_bad_lobbies() -> None:
    for names in (["solo"], [*NAMES, "ivy"], ["ana", "ana"]):
        with pytest.raises(ValueError, match="distinct players"):
            Game(names)


def test_a_full_game_is_deterministic_and_ends() -> None:
    first, second = Game(NAMES, seed=42), Game(NAMES, seed=42)
    placements = first.run()
    assert second.run() == placements
    assert sorted(placements) == sorted(NAMES)
    assert first.finished
    assert [p.health for p in first.players] == [p.health for p in second.players]
    assert len(first.alive) <= 1 or first.round_index == MAX_ROUNDS
    with pytest.raises(RuntimeError, match="finished"):
        first.step()


def test_different_seeds_give_different_games() -> None:
    outcomes = {tuple(Game(NAMES, seed=seed).run()) for seed in range(4)}
    assert len(outcomes) > 1


def test_step_reports_eliminations_in_order() -> None:
    class HomeWins:
        def resolve(self, home: Player, away: Player, _rng: Random, /) -> CombatResult:
            return CombatResult(home.name, away.name, 9)

    game = Game(["ana", "bo"], seed=1, resolver=HomeWins())
    reports = []
    for _ in range(MAX_ROUNDS):
        if game.finished:
            break
        reports.append(game.step())
    assert game.finished
    assert len(game.eliminated) == 1
    assert game.placements[-1] == game.eliminated[0]
    assert any(report.eliminated for report in reports)
    assert reports[0].round_id.label == "1-1"
    assert all(result.winner for report in reports[:3] for result in report.results)


def test_duel_rejects_a_half_result() -> None:
    class Broken:
        def resolve(self, home: Player, away: Player, _rng: Random, /) -> CombatResult:
            return CombatResult(home.name, None, 1)

    game = Game(["ana", "bo"], seed=1, resolver=Broken())
    with pytest.raises(ValueError, match="winner and a loser"):
        game.duel(game.players[0], game.players[1], RoundId(2, 1))


def test_pvp_round_with_an_odd_lobby_sends_one_player_to_the_market() -> None:
    game = Game(["ana", "bo", "cy"], seed=3)
    results = game.fight(RoundId(2, 2))
    assert len(results) == 2
    assert any(env.MARKET in (result.winner, result.loser) for result in results)


def test_augment_and_carousel_rounds_grant_their_rewards() -> None:
    game = Game(["ana", "bo"], seed=5)
    player = game.players[0]
    game.prepare(player, RoundId(2, 1))
    assert len(player.augments) == 1
    bench_before = len(game.players[1].bench)
    game.prepare(game.players[1], RoundId(2, 4))
    assert len(game.players[1].bench) >= bench_before
    full = game.players[1]
    full.bench = [Unit(unit) for unit in CHAMPIONS[:BENCH_SIZE]]
    game.carousel(full, RoundId(3, 4))
    assert len(full.bench) == BENCH_SIZE
    with pytest.raises(ValueError, match="not a carousel"):
        game.carousel(full, RoundId(3, 5))
    game.players[0].health = 0
    with pytest.raises(ValueError, match="eliminated"):
        game.prepare(game.players[0], RoundId(3, 5))


def test_carousel_skips_an_exhausted_cost_tier() -> None:
    game = Game(["ana", "bo"], seed=5, champions=[PIP, BULL])
    game.pool.take("Pip Squeak", POOL_SIZES[1])
    game.carousel(game.players[0], RoundId(2, 4))
    assert game.players[0].bench == []


def test_market_fight_outcomes() -> None:
    game = Game(["ana", "bo"], seed=0)
    weak = game.players[0]
    result = game.fight_market(weak, RoundId(3, 1))
    assert result.winner == env.MARKET
    assert weak.health == STARTING_HEALTH - stage_damage(3) - env.MARKET_SURVIVORS
    strong = game.players[1]
    strong.level = 5
    strong.board = [Unit(BULL, star=3) for _ in range(5)]
    assert game.fight_market(strong, RoundId(2, 1)).winner == "bo"


def test_player_lookup() -> None:
    game = Game(["ana", "bo"])
    assert game.player("bo").name == "bo"
    with pytest.raises(KeyError, match="no player"):
        game.player("zed")
