"""The game environment mock: lobby, rounds, shop, pool, levels, damage.

A headless, deterministic simulation of the auto-battler loop around the roster
in :mod:`tft.roster`. It exists so that the product requirements document
(``docs/PRD.md``) has running code behind every mechanic it names, and so that
the real combat resolver (market-data replays) can be plugged in later through
:class:`CombatResolver`. Combat here is a power comparison; everything else
(economy, shop odds, shared pool, star-ups, levels, stage damage, streaks,
augments, carousel, PvE rounds, eliminations) follows the genre's conventions.

Determinism: every random draw comes from the one :class:`random.Random` the
game owns, so a seed reproduces a whole game. Every loop is bounded: a game
runs at most :data:`MAX_ROUNDS` rounds.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from random import Random
from typing import Protocol

from tft.economy import round_income
from tft.roster import CHAMPIONS, Champion, synergy_bonus

STARTING_HEALTH = 100
LOBBY_SIZE = 8
MIN_PLAYERS = 2
SHOP_SIZE = 5
BENCH_SIZE = 9
MAX_LEVEL = 10
REROLL_COST = 2
XP_PURCHASE_COST = 4
XP_PER_PURCHASE = 4
XP_PER_ROUND = 2
COPIES_TO_STAR_UP = 3
MAX_STAR = 3
OPENING_ROUNDS = 3
ROUNDS_PER_STAGE = 7
CAROUSEL_ROUND = 4
BOSS_ROUND = 7
MAX_ROUNDS = OPENING_ROUNDS + 6 * ROUNDS_PER_STAGE
"""Stage 1 has three PvE rounds; stages 2 to 7 have seven rounds each: 7-7 is the cap."""

COSTS: tuple[int, ...] = (1, 2, 3, 4, 5)
POOL_SIZES: dict[int, int] = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}
"""Copies of each champion shared by the whole lobby, by cost."""

SHOP_ODDS: dict[int, tuple[int, int, int, int, int]] = {
    1: (100, 0, 0, 0, 0),
    2: (100, 0, 0, 0, 0),
    3: (75, 25, 0, 0, 0),
    4: (55, 30, 15, 0, 0),
    5: (45, 33, 20, 2, 0),
    6: (30, 40, 25, 5, 0),
    7: (19, 30, 40, 10, 1),
    8: (17, 24, 32, 24, 3),
    9: (15, 18, 25, 30, 12),
    10: (5, 10, 20, 40, 25),
}
"""Percent chance per shop slot of each cost tier, by player level."""

XP_TO_NEXT_LEVEL: dict[int, int] = {1: 2, 2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 48, 8: 80, 9: 84}
STAGE_BASE_DAMAGE: dict[int, int] = {1: 0, 2: 2, 3: 5, 4: 8, 5: 10, 6: 12, 7: 17}
STAR_POWER_TENTHS: dict[int, int] = {1: 10, 2: 18, 3: 32}
"""Power multiplier per star level, in tenths (a two-star is 1.8 times a one-star)."""

AUGMENT_ROUNDS: frozenset[tuple[int, int]] = frozenset({(2, 1), (3, 2), (4, 2)})
MARKET = "The Market"
"""The PvE opponent's name."""

MARKET_POWER_PER_STAGE = 6
MARKET_BOSS_FACTOR_TENTHS = 15
MARKET_SURVIVORS = 2
ECON_RESERVE = 10
"""Gold the greedy policy keeps before buying experience."""


@dataclass(frozen=True)
class RoundId:
    """A round's place in the match: stage 2, round 1 is ``2-1``."""

    stage: int
    number: int

    @property
    def label(self) -> str:
        """Return the genre's ``stage-round`` label."""
        return f"{self.stage}-{self.number}"

    @property
    def is_pve(self) -> bool:
        """Return whether the lobby fights the Market instead of each other."""
        return self.stage == 1 or self.number == BOSS_ROUND

    @property
    def is_carousel(self) -> bool:
        """Return whether every player gets a free champion this round."""
        return self.stage >= 2 and self.number == CAROUSEL_ROUND  # noqa: PLR2004

    @property
    def is_augment(self) -> bool:
        """Return whether players pick an augment this round."""
        return (self.stage, self.number) in AUGMENT_ROUNDS


def round_sequence(max_rounds: int = MAX_ROUNDS) -> tuple[RoundId, ...]:
    """Return the rounds of a match in order, ``max_rounds`` of them at most.

    Raises:
        ValueError: If ``max_rounds`` is not positive.
    """
    if max_rounds <= 0:
        msg = f"max_rounds must be positive, got {max_rounds}"
        raise ValueError(msg)
    rounds = [RoundId(1, number) for number in range(1, OPENING_ROUNDS + 1)]
    for stage in range(2, 2 + max_rounds):
        rounds.extend(RoundId(stage, number) for number in range(1, ROUNDS_PER_STAGE + 1))
        if len(rounds) >= max_rounds:
            break
    return tuple(rounds[:max_rounds])


def stage_damage(stage: int) -> int:
    """Return the base damage a lost round costs at ``stage``; late stages cap at stage 7."""
    return STAGE_BASE_DAMAGE[min(stage, max(STAGE_BASE_DAMAGE))]


def market_power(round_id: RoundId) -> int:
    """Return the Market's power for a PvE round: it grows with the stage, more on boss rounds."""
    base = MARKET_POWER_PER_STAGE * round_id.stage * round_id.stage
    if round_id.number == BOSS_ROUND:
        return base * MARKET_BOSS_FACTOR_TENTHS // 10
    return base


@dataclass(frozen=True)
class Augment:
    """A rule-changing pick: the mock has gold and board-power effects only."""

    name: str
    tier: str
    text: str
    gold: int = 0
    power_percent: int = 0


AUGMENTS: tuple[Augment, ...] = (
    Augment("Windfall", "gold", "Receive 20 gold now.", gold=20),
    Augment("Compound Interest", "silver", "Receive 8 gold now; keep banking.", gold=8),
    Augment("Tight Stops", "silver", "Your board hits 10 % harder.", power_percent=10),
    Augment("Diversified", "gold", "Your board hits 18 % harder.", power_percent=18),
    Augment("Hedge Fund", "gold", "10 gold now and 8 % board power.", gold=10, power_percent=8),
    Augment("Leverage", "prismatic", "Your board hits 30 % harder.", power_percent=30),
)
"""The mock augment pool."""


@dataclass
class Unit:
    """A champion on a bench or board at a star level."""

    champion: Champion
    star: int = 1

    @property
    def power(self) -> int:
        """Return the unit's power at its star level."""
        return self.champion.power * STAR_POWER_TENTHS[self.star] // 10

    @property
    def copies(self) -> int:
        """Return how many one-star copies the unit represents (1, 3 or 9)."""
        return int(COPIES_TO_STAR_UP ** (self.star - 1))


def sell_value(cost: int, star: int) -> int:
    """Return the gold a unit sells for.

    A one-star sells for its cost; higher stars sell for the copies they hold,
    minus one gold, except one-cost champions which sell for the full copies.

    Raises:
        ValueError: If ``star`` is outside 1 to 3.
    """
    if not 1 <= star <= MAX_STAR:
        msg = f"star must be 1 to {MAX_STAR}, got {star}"
        raise ValueError(msg)
    if star == 1:
        return cost
    copies = int(cost * COPIES_TO_STAR_UP ** (star - 1))
    return copies if cost == 1 else copies - 1


class Pool:
    """The copies of every champion the whole lobby draws from."""

    def __init__(self, champions: Sequence[Champion] = CHAMPIONS) -> None:
        """Fill the pool with the standard number of copies of each champion."""
        self._champions = {unit.name: unit for unit in champions}
        self._remaining = {unit.name: POOL_SIZES[unit.cost] for unit in champions}

    def remaining(self, name: str) -> int:
        """Return the copies of ``name`` left in the pool.

        Raises:
            KeyError: If ``name`` is not in the pool at all.
        """
        if name not in self._remaining:
            msg = f"{name!r} is not in the pool"
            raise KeyError(msg)
        return self._remaining[name]

    def take(self, name: str, copies: int = 1) -> None:
        """Remove ``copies`` of ``name`` from the pool.

        Raises:
            ValueError: If fewer copies are left than requested.
        """
        if self.remaining(name) < copies:
            msg = f"only {self.remaining(name)} copies of {name!r} left, {copies} requested"
            raise ValueError(msg)
        self._remaining[name] -= copies

    def give_back(self, name: str, copies: int = 1) -> None:
        """Return ``copies`` of ``name`` to the pool (a sale)."""
        self._remaining[name] = self.remaining(name) + copies

    def available(self, cost: int) -> list[Champion]:
        """Return the champions of ``cost`` that still have copies, in name order."""
        units = (unit for unit in self._champions.values() if unit.cost == cost)
        return sorted(
            (unit for unit in units if self._remaining[unit.name] > 0), key=lambda u: u.name
        )


def roll_shop(level: int, pool: Pool, rng: Random) -> list[Champion | None]:
    """Roll a shop: a cost tier per slot by the level's odds, then a champion by copies left.

    A slot is ``None`` when the pool has no champion of the drawn cost left.
    Rolling never consumes the pool.

    Raises:
        ValueError: If ``level`` has no odds table.
    """
    if level not in SHOP_ODDS:
        msg = f"no shop odds for level {level}"
        raise ValueError(msg)
    slots: list[Champion | None] = []
    for _ in range(SHOP_SIZE):
        cost = rng.choices(COSTS, weights=SHOP_ODDS[level], k=1)[0]
        choices = pool.available(cost)
        if not choices:
            slots.append(None)
            continue
        weights = [pool.remaining(unit.name) for unit in choices]
        slots.append(rng.choices(choices, weights=weights, k=1)[0])
    return slots


@dataclass
class Player:
    """One seat in the lobby: health, economy, level, bench, board and shop."""

    name: str
    health: int = STARTING_HEALTH
    gold: int = 0
    level: int = 1
    xp: int = 0
    streak: int = 0
    bench: list[Unit] = field(default_factory=list)
    board: list[Unit] = field(default_factory=list)
    shop: list[Champion | None] = field(default_factory=list)
    augments: list[Augment] = field(default_factory=list)

    @property
    def alive(self) -> bool:
        """Return whether the player is still in the match."""
        return self.health > 0

    @property
    def board_limit(self) -> int:
        """Return how many units the player may field: one per level."""
        return self.level

    @property
    def units(self) -> list[Unit]:
        """Return every unit the player owns, board first."""
        return [*self.board, *self.bench]

    @property
    def team_power(self) -> int:
        """Return the board's power with trait and augment bonuses applied."""
        base = sum(unit.power for unit in self.board)
        bonus = synergy_bonus(unit.champion for unit in self.board)
        bonus += sum(augment.power_percent for augment in self.augments)
        return base * (100 + bonus) // 100

    def buy(self, slot: int, pool: Pool) -> None:
        """Buy the champion in shop ``slot`` onto the bench and merge star-ups.

        Raises:
            ValueError: If the slot is invalid or empty, the gold is short, or
                the bench is full and the purchase would not complete a star-up.
        """
        if not 0 <= slot < len(self.shop):
            msg = f"shop slot {slot} does not exist"
            raise ValueError(msg)
        unit = self.shop[slot]
        if unit is None:
            msg = f"shop slot {slot} is empty"
            raise ValueError(msg)
        if self.gold < unit.cost:
            msg = f"{unit.name} costs {unit.cost} gold, {self.gold} available"
            raise ValueError(msg)
        if len(self.bench) >= BENCH_SIZE and not self.completes_star_up(unit):
            msg = "the bench is full"
            raise ValueError(msg)
        pool.take(unit.name)
        self.gold -= unit.cost
        self.shop[slot] = None
        self.bench.append(Unit(unit))
        self.merge(unit.name)

    def completes_star_up(self, champion: Champion) -> bool:
        """Return whether buying one more copy of ``champion`` triggers a star-up."""
        owned = sum(1 for unit in self.units if unit.champion is champion and unit.star == 1)
        return owned >= COPIES_TO_STAR_UP - 1

    def merge(self, name: str) -> None:
        """Combine three copies of ``name`` at the same star into the next star, repeatedly."""
        for star in range(1, MAX_STAR):
            for _ in range(BENCH_SIZE + MAX_LEVEL):  # bounded: a player never owns more units
                same = [u for u in self.units if u.champion.name == name and u.star == star]
                if len(same) < COPIES_TO_STAR_UP:
                    break
                kept, *extra = same[:COPIES_TO_STAR_UP]
                kept.star += 1
                for unit in extra:
                    self.remove(unit)

    def remove(self, unit: Unit) -> None:
        """Take ``unit`` off the board or the bench.

        Raises:
            ValueError: If the player does not own ``unit``.
        """
        if unit in self.board:
            self.board.remove(unit)
        elif unit in self.bench:
            self.bench.remove(unit)
        else:
            msg = f"{self.name} does not own that {unit.champion.name}"
            raise ValueError(msg)

    def sell(self, unit: Unit, pool: Pool) -> int:
        """Sell ``unit``, return its copies to the pool, and return the gold received."""
        self.remove(unit)
        pool.give_back(unit.champion.name, unit.copies)
        value = sell_value(unit.champion.cost, unit.star)
        self.gold += value
        return value

    def add_xp(self, amount: int) -> None:
        """Grant experience and level up as far as it reaches, never past the cap.

        Raises:
            ValueError: If ``amount`` is negative.
        """
        if amount < 0:
            msg = f"xp must not be negative, got {amount}"
            raise ValueError(msg)
        self.xp += amount
        while self.level < MAX_LEVEL and self.xp >= XP_TO_NEXT_LEVEL[self.level]:
            self.xp -= XP_TO_NEXT_LEVEL[self.level]
            self.level += 1

    def buy_xp(self) -> None:
        """Spend gold on experience.

        Raises:
            ValueError: If the player is at the level cap or short of gold.
        """
        if self.level >= MAX_LEVEL:
            msg = f"{self.name} is already level {MAX_LEVEL}"
            raise ValueError(msg)
        if self.gold < XP_PURCHASE_COST:
            msg = f"buying xp costs {XP_PURCHASE_COST} gold, {self.gold} available"
            raise ValueError(msg)
        self.gold -= XP_PURCHASE_COST
        self.add_xp(XP_PER_PURCHASE)

    def reroll(self, pool: Pool, rng: Random) -> None:
        """Pay for a new shop.

        Raises:
            ValueError: If the player is short of gold.
        """
        if self.gold < REROLL_COST:
            msg = f"a reroll costs {REROLL_COST} gold, {self.gold} available"
            raise ValueError(msg)
        self.gold -= REROLL_COST
        self.shop = roll_shop(self.level, pool, rng)

    def field_unit(self, unit: Unit) -> None:
        """Move ``unit`` from the bench to the board.

        Raises:
            ValueError: If ``unit`` is not on the bench or the board is full.
        """
        if unit not in self.bench:
            msg = f"that {unit.champion.name} is not on {self.name}'s bench"
            raise ValueError(msg)
        if len(self.board) >= self.board_limit:
            msg = f"the board holds {self.board_limit} units at level {self.level}"
            raise ValueError(msg)
        self.bench.remove(unit)
        self.board.append(unit)

    def record_result(self, won: bool | None) -> None:
        """Extend or flip the streak; a draw (``None``) breaks it."""
        if won is None:
            self.streak = 0
        elif won:
            self.streak = self.streak + 1 if self.streak > 0 else 1
        else:
            self.streak = self.streak - 1 if self.streak < 0 else -1

    def collect_income(self) -> None:
        """Add the round's income: base, interest and streak bonus."""
        self.gold += round_income(self.gold, self.streak)

    def take_damage(self, amount: int) -> None:
        """Lose health, never below zero.

        Raises:
            ValueError: If ``amount`` is negative.
        """
        if amount < 0:
            msg = f"damage must not be negative, got {amount}"
            raise ValueError(msg)
        self.health = max(0, self.health - amount)


Policy = Callable[[Player, Pool, Random], None]
"""A planning-phase decision maker: acts on the player, then returns."""


def greedy_policy(player: Player, pool: Pool, rng: Random) -> None:
    """A baseline bot: buy what it can afford, field the strongest units, then level.

    Raises:
        ValueError: If the player's shop has not been rolled.
    """
    del rng  # the greedy bot is deterministic
    if len(player.shop) != SHOP_SIZE:
        msg = f"{player.name}'s shop has not been rolled"
        raise ValueError(msg)
    for slot, unit in enumerate(player.shop):
        if unit is None or player.gold < unit.cost or len(player.bench) >= BENCH_SIZE:
            continue
        player.buy(slot, pool)
    while player.bench and len(player.board) < player.board_limit:
        player.field_unit(max(player.bench, key=lambda unit: unit.power))
    if player.level < MAX_LEVEL and player.gold >= XP_PURCHASE_COST + ECON_RESERVE:
        player.buy_xp()


@dataclass(frozen=True)
class CombatResult:
    """Who won a fight, who lost, and how many winning units were left standing."""

    winner: str | None
    loser: str | None
    survivors: int

    @property
    def is_draw(self) -> bool:
        """Return whether nobody won."""
        return self.winner is None


class CombatResolver(Protocol):
    """The seam where the market replay plugs in."""

    def resolve(self, home: Player, away: Player, rng: Random, /) -> CombatResult:
        """Fight ``home`` against ``away`` and return the result."""


class PowerResolver:
    """The mock resolver: the stronger board wins and survivors scale with the margin."""

    def resolve(self, home: Player, away: Player, _rng: Random, /) -> CombatResult:
        """Compare team power; a tie is a draw."""
        home_power, away_power = home.team_power, away.team_power
        if home_power == away_power:
            return CombatResult(None, None, 0)
        winner, loser = (home, away) if home_power > away_power else (away, home)
        strong, weak = max(home_power, away_power), min(home_power, away_power)
        survivors = max(1, round(len(winner.board) * (strong - weak) / strong))
        return CombatResult(winner.name, loser.name, survivors)


@dataclass(frozen=True)
class RoundReport:
    """What happened in one round."""

    round_id: RoundId
    results: tuple[CombatResult, ...]
    eliminated: tuple[str, ...]


class Game:
    """A whole match: the lobby, the shared pool, the round loop and the standings."""

    def __init__(
        self,
        names: Sequence[str],
        seed: int = 0,
        resolver: CombatResolver | None = None,
        policy: Policy = greedy_policy,
        champions: Sequence[Champion] = CHAMPIONS,
    ) -> None:
        """Seat the players and seed the match.

        Raises:
            ValueError: If there are fewer than two or more than eight distinct names.
        """
        if not MIN_PLAYERS <= len(names) <= LOBBY_SIZE or len(set(names)) != len(names):
            msg = f"a lobby needs {MIN_PLAYERS} to {LOBBY_SIZE} distinct players, got {list(names)}"
            raise ValueError(msg)
        self.rng = Random(seed)  # noqa: S311 - game randomness, not cryptography
        self.pool = Pool(champions)
        self.players = [Player(name) for name in names]
        self.resolver: CombatResolver = resolver if resolver is not None else PowerResolver()
        self.policy = policy
        self.rounds = round_sequence()
        self.round_index = 0
        self.eliminated: list[str] = []

    @property
    def alive(self) -> list[Player]:
        """Return the players still in the match, in seat order."""
        return [player for player in self.players if player.alive]

    @property
    def finished(self) -> bool:
        """Return whether the match is over: one player left, or no rounds left."""
        return len(self.alive) <= 1 or self.round_index >= len(self.rounds)

    @property
    def placements(self) -> list[str]:
        """Return the standings: survivors by health, then the eliminated, last out first."""
        survivors = sorted(self.alive, key=lambda player: (-player.health, player.name))
        return [player.name for player in survivors] + list(reversed(self.eliminated))

    def player(self, name: str) -> Player:
        """Return the player called ``name``.

        Raises:
            KeyError: If nobody in the lobby has that name.
        """
        for player in self.players:
            if player.name == name:
                return player
        msg = f"no player named {name!r}"
        raise KeyError(msg)

    def step(self) -> RoundReport:
        """Play the next round: income and events, shops and planning, combat, damage.

        Raises:
            RuntimeError: If the match is already finished.
        """
        if self.finished:
            msg = "the match is finished"
            raise RuntimeError(msg)
        round_id = self.rounds[self.round_index]
        self.round_index += 1
        for player in self.alive:
            self.prepare(player, round_id)
        results = self.fight(round_id)
        fallen = [p.name for p in self.players if not p.alive and p.name not in self.eliminated]
        self.eliminated.extend(fallen)
        return RoundReport(round_id, tuple(results), tuple(fallen))

    def prepare(self, player: Player, round_id: RoundId) -> None:
        """Run a player's planning phase: income, experience, events, shop, policy.

        Raises:
            ValueError: If the player has already been eliminated.
        """
        if not player.alive:
            msg = f"{player.name} has been eliminated and does not play"
            raise ValueError(msg)
        player.collect_income()
        player.add_xp(XP_PER_ROUND)
        if round_id.is_augment:
            augment = self.rng.choice(AUGMENTS)
            player.augments.append(augment)
            player.gold += augment.gold
        if round_id.is_carousel:
            self.carousel(player, round_id)
        player.shop = roll_shop(player.level, self.pool, self.rng)
        self.policy(player, self.pool, self.rng)  # noqa: JPL07 - policies act by side effect

    def carousel(self, player: Player, round_id: RoundId) -> None:
        """Give the player a free champion whose cost grows with the stage, bench permitting.

        Raises:
            ValueError: If called on a round that is not a carousel.
        """
        if not round_id.is_carousel:
            msg = f"round {round_id.label} is not a carousel"
            raise ValueError(msg)
        if len(player.bench) >= BENCH_SIZE:
            return
        cost = min(round_id.stage - 1, max(COSTS) - 1)
        choices = self.pool.available(cost)
        if not choices:
            return
        unit = self.rng.choice(choices)
        self.pool.take(unit.name)
        player.bench.append(Unit(unit))
        player.merge(unit.name)

    def fight(self, round_id: RoundId) -> list[CombatResult]:
        """Resolve the round's combats: the Market on PvE rounds, random pairings otherwise."""
        if round_id.is_pve:
            return [self.fight_market(player, round_id) for player in self.alive]
        order = list(self.alive)
        self.rng.shuffle(order)
        pairs = zip(order[0::2], order[1::2], strict=False)
        results = [self.duel(home, away, round_id) for home, away in pairs]
        if len(order) % 2:
            results.append(self.fight_market(order[-1], round_id))
        return results

    def duel(self, home: Player, away: Player, round_id: RoundId) -> CombatResult:
        """Fight two players and apply streaks and damage.

        Raises:
            ValueError: If the resolver names a winner without a loser.
        """
        result = self.resolver.resolve(home, away, self.rng)
        if result.is_draw:
            home.record_result(None)
            away.record_result(None)
            return result
        if result.winner is None or result.loser is None:
            msg = "a combat result needs both a winner and a loser unless it is a draw"
            raise ValueError(msg)
        self.player(result.winner).record_result(True)
        loser = self.player(result.loser)
        loser.record_result(False)
        loser.take_damage(stage_damage(round_id.stage) + result.survivors)
        return result

    def fight_market(self, player: Player, round_id: RoundId) -> CombatResult:
        """Fight the scripted Market: beat its power or take stage damage."""
        if player.team_power >= market_power(round_id):
            player.record_result(True)
            return CombatResult(player.name, MARKET, 0)
        player.record_result(False)
        player.take_damage(stage_damage(round_id.stage) + MARKET_SURVIVORS)
        return CombatResult(MARKET, player.name, MARKET_SURVIVORS)

    def run(self) -> list[str]:
        """Play until the match is finished and return the placements."""
        for _ in range(len(self.rounds)):
            if self.finished:
                break
            _ = self.step()
        return self.placements
