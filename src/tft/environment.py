"""The game environment: lobby, rounds, shop, pool, levels, items, damage.

A headless, deterministic simulation of the auto-battler loop around the roster
in :mod:`tft.roster`, with every number read from a :class:`tft.rules.Rules`.
Combat goes through a :class:`tft.combat.CombatResolver`: the market replay
when the game has a :class:`tft.market.MarketPack`, the power comparison
otherwise. Everything else (economy, shop odds, shared pool, star-ups, levels,
stage damage, streaks, augments, carousel, component drops, PvE rounds,
eliminations) follows the genre's conventions.

A round has two phases. :meth:`Game.start_round` deals the round's market
slice, pays income, runs the round's events, rolls every shop and lets the
bots act. A seat whose policy is ``None`` is driven from outside (the
command-line client, or a replay) between the two calls.
:meth:`Game.finish_round` resolves combat and damage.

Determinism: every random draw comes from the one :class:`random.Random` the
game owns, so a seed, a rule set, a pack and the outside seat's actions
reproduce a whole match. Every loop is bounded: a match runs at most
``rules.max_rounds`` rounds.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from random import Random

from tft.combat import (
    CombatContext,
    CombatResolver,
    CombatResult,
    MarketResolver,
    PowerResolver,
    preview,
)
from tft.economy import round_income
from tft.items import Component, Effect, Item, combined_effect, craft
from tft.market import MarketPack, Slice
from tft.roster import CHAMPIONS, Champion, TraitEntry, active_traits_for, synergy_bonus_for
from tft.rules import DEFAULT_RULES, Rules

__all__ = [
    "AUGMENTS",
    "MARKET",
    "Augment",
    "CombatContext",
    "CombatResolver",
    "CombatResult",
    "Game",
    "MarketResolver",
    "Player",
    "Policy",
    "Pool",
    "PowerResolver",
    "RoundId",
    "RoundReport",
    "SeatView",
    "Unit",
    "greedy_policy",
    "market_board",
    "market_power",
    "roll_shop",
    "round_sequence",
    "seat_view",
    "sell_value",
    "stage_damage",
]

MARKET = "The Market"
"""The PvE opponent's name."""

COSTS: tuple[int, ...] = (1, 2, 3, 4, 5)
COMPONENTS: tuple[Component, ...] = tuple(Component)

PHASE_BETWEEN = "between rounds"
PHASE_PLANNING = "planning"

MARKET_MID_STAGE = 3
MARKET_TOP_COST = 4
MARKET_FINAL_STAGE = 7

# Aliases of the default rule set, for readers and for callers that never change the rules.
STARTING_HEALTH = DEFAULT_RULES.starting_health
LOBBY_SIZE = DEFAULT_RULES.lobby_size
SHOP_SIZE = DEFAULT_RULES.shop_size
BENCH_SIZE = DEFAULT_RULES.bench_size
MAX_LEVEL = DEFAULT_RULES.max_level
MAX_ROUNDS = DEFAULT_RULES.max_rounds
POOL_SIZES = DEFAULT_RULES.pool_sizes
SHOP_ODDS = DEFAULT_RULES.shop_odds


@dataclass(frozen=True)
class RoundId:
    """A round's place in the match (``2-1`` is stage 2, round 1) and its events."""

    stage: int
    number: int
    is_pve: bool = False
    is_carousel: bool = False
    is_augment: bool = False

    @classmethod
    def make(cls, stage: int, number: int, rules: Rules = DEFAULT_RULES) -> RoundId:
        """Build a round with its event flags derived from ``rules``."""
        return cls(
            stage,
            number,
            is_pve=stage == 1 or number == rules.boss_round,
            is_carousel=stage >= 2 and number == rules.carousel_round,  # noqa: PLR2004
            is_augment=(stage, number) in rules.augment_rounds,
        )

    @property
    def label(self) -> str:
        """Return the genre's ``stage-round`` label."""
        return f"{self.stage}-{self.number}"


def round_sequence(rules: Rules = DEFAULT_RULES) -> tuple[RoundId, ...]:
    """Return the rounds of a match in order: the opening PvE rounds, then full stages."""
    rounds = [RoundId.make(1, number, rules) for number in range(1, rules.opening_rounds + 1)]
    for stage in range(2, rules.stages + 1):
        numbers = range(1, rules.rounds_per_stage + 1)
        rounds.extend(RoundId.make(stage, number, rules) for number in numbers)
    return tuple(rounds)


def stage_damage(stage: int, rules: Rules = DEFAULT_RULES) -> int:
    """Return the base damage a lost round costs at ``stage``, from the nearest listed stage."""
    table = rules.stage_base_damage
    return table[max(listed for listed in table if listed <= stage)]


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


@dataclass(eq=False)
class Unit:
    """A champion on a bench or board at a star level, with its items. Units compare by identity."""

    champion: Champion
    star: int = 1
    items: list[Item] = field(default_factory=list)

    def power(self, rules: Rules = DEFAULT_RULES) -> int:
        """Return the unit's power at its star level."""
        return self.champion.power * rules.star_power_tenths[self.star] // 10

    def copies(self, rules: Rules = DEFAULT_RULES) -> int:
        """Return how many one-star copies the unit represents (1, 3 or 9 by default)."""
        return int(rules.copies_to_star_up ** (self.star - 1))

    @property
    def effect(self) -> Effect:
        """Return the combined effect of the unit's items."""
        return combined_effect(self.items)

    @property
    def traits(self) -> tuple[str, ...]:
        """Return the champion's traits plus any emblem its items grant."""
        emblems = tuple(item.effect.trait for item in self.items if item.effect.trait is not None)
        return (*self.champion.traits, *emblems)

    def describe(self) -> str:
        """Return ``Name N*`` with the item names in brackets when it holds any."""
        base = f"{self.champion.name} {self.star}*"
        if not self.items:
            return base
        return f"{base} [{', '.join(item.name for item in self.items)}]"


def sell_value(cost: int, star: int, rules: Rules = DEFAULT_RULES) -> int:
    """Return the gold a unit sells for.

    A one-star sells for its cost; higher stars sell for the copies they hold,
    minus one gold, except one-cost champions which sell for the full copies.

    Raises:
        ValueError: If ``star`` is outside the rule set's range.
    """
    if not 1 <= star <= rules.max_star:
        msg = f"star must be 1 to {rules.max_star}, got {star}"
        raise ValueError(msg)
    if star == 1:
        return cost
    copies = int(cost * rules.copies_to_star_up ** (star - 1))
    return copies if cost == 1 else copies - 1


class Pool:
    """The copies of every champion the whole lobby draws from."""

    def __init__(
        self, champions: Sequence[Champion] = CHAMPIONS, rules: Rules = DEFAULT_RULES
    ) -> None:
        """Fill the pool with the rule set's number of copies of each champion."""
        self._champions = {unit.name: unit for unit in champions}
        self._remaining = {unit.name: rules.pool_sizes[unit.cost] for unit in champions}

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


def roll_shop(
    level: int, pool: Pool, rng: Random, rules: Rules = DEFAULT_RULES
) -> list[Champion | None]:
    """Roll a shop: a cost tier per slot by the level's odds, then a champion by copies left.

    A slot is ``None`` when the pool has no champion of the drawn cost left.
    Rolling never consumes the pool.

    Raises:
        ValueError: If ``level`` has no odds row.
    """
    if level not in rules.shop_odds:
        msg = f"no shop odds for level {level}"
        raise ValueError(msg)
    slots: list[Champion | None] = []
    for _ in range(rules.shop_size):
        cost = rng.choices(COSTS, weights=rules.shop_odds[level], k=1)[0]
        choices = pool.available(cost)
        if not choices:
            slots.append(None)
            continue
        weights = [pool.remaining(unit.name) for unit in choices]
        slots.append(rng.choices(choices, weights=weights, k=1)[0])
    return slots


@dataclass
class Player:
    """One seat in the lobby: health, economy, level, bench, board, shop, items and augments."""

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
    pending_augments: list[Augment] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    rules: Rules = DEFAULT_RULES

    @property
    def alive(self) -> bool:
        """Return whether the player is still in the match."""
        return self.health > 0

    @property
    def board_limit(self) -> int:
        """Return how many units the player may field: one per level, plus item slots."""
        return self.level + sum(unit.effect.extra_slots for unit in self.board)

    @property
    def units(self) -> list[Unit]:
        """Return every unit the player owns, board first."""
        return [*self.board, *self.bench]

    def board_entries(self) -> list[TraitEntry]:
        """Return the fielded champions with every trait they count for, emblems included."""
        return [(unit.champion.name, unit.traits) for unit in self.board]

    @property
    def bonus_percent(self) -> int:
        """Return the board's trait and augment bonus in percent."""
        return synergy_bonus_for(self.board_entries()) + sum(a.power_percent for a in self.augments)

    @property
    def team_power(self) -> int:
        """Return the board's power with trait and augment bonuses applied."""
        base = sum(unit.power(self.rules) for unit in self.board)
        return base * (100 + self.bonus_percent) // 100

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
        if len(self.bench) >= self.rules.bench_size and not self.completes_star_up(unit):
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
        return owned >= self.rules.copies_to_star_up - 1

    def merge(self, name: str) -> None:
        """Combine copies of ``name`` at the same star into the next star, repeatedly.

        The kept copy inherits the items of the copies it absorbs, up to the limit.

        Raises:
            ValueError: If the rules need fewer than two copies for a star-up.
        """
        needed = self.rules.copies_to_star_up
        if needed < 2:  # noqa: PLR2004
            msg = "copies_to_star_up must be at least 2"
            raise ValueError(msg)
        for star in range(1, self.rules.max_star):
            for _ in range(self.rules.bench_size + self.rules.max_level):  # bounded by owned units
                same = [u for u in self.units if u.champion.name == name and u.star == star]
                if len(same) < needed:
                    break
                kept, *extra = same[:needed]
                kept.star += 1
                for unit in extra:
                    self.absorb(kept, unit)

    def absorb(self, kept: Unit, extra: Unit) -> None:
        """Remove ``extra`` and hand its items to ``kept``; the overflow goes to the inventory."""
        self.remove(extra)
        for item in extra.items:
            if len(kept.items) < self.rules.max_items_per_unit:
                kept.items.append(item)
            else:
                self.items.append(item)

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
        """Sell ``unit``: copies back to the pool, items to the inventory; return the gold."""
        self.remove(unit)
        self.items.extend(unit.items)
        unit.items = []
        pool.give_back(unit.champion.name, unit.copies(self.rules))
        value = sell_value(unit.champion.cost, unit.star, self.rules)
        self.gold += value
        return value

    def craft(self, first: int, second: int) -> Item:
        """Combine components ``first`` and ``second`` (inventory numbers) into an item.

        Raises:
            ValueError: If either number is out of range or they are the same component.
        """
        count = len(self.components)
        if first == second or not (0 <= first < count and 0 <= second < count):
            msg = (
                f"craft needs two different component numbers from 0 to {count - 1}"
                if count
                else "no components"
            )
            raise ValueError(msg)
        item = craft(self.components[first], self.components[second])
        for index in sorted((first, second), reverse=True):
            del self.components[index]
        self.items.append(item)
        return item

    def equip(self, unit: Unit, item_index: int) -> Item:
        """Give item ``item_index`` of the inventory to ``unit``.

        Raises:
            ValueError: If the player does not own the unit, the item number is
                out of range, or the unit already holds the maximum.
        """
        if unit not in self.units:
            msg = f"{self.name} does not own that {unit.champion.name}"
            raise ValueError(msg)
        if not 0 <= item_index < len(self.items):
            msg = (
                f"item number must be 0 to {len(self.items) - 1}"
                if self.items
                else "no items to equip"
            )
            raise ValueError(msg)
        if len(unit.items) >= self.rules.max_items_per_unit:
            msg = f"{unit.champion.name} already holds {self.rules.max_items_per_unit} items"
            raise ValueError(msg)
        item = self.items.pop(item_index)
        unit.items.append(item)
        return item

    def add_xp(self, amount: int) -> None:
        """Grant experience and level up as far as it reaches, never past the cap.

        Raises:
            ValueError: If ``amount`` is negative.
        """
        if amount < 0:
            msg = f"xp must not be negative, got {amount}"
            raise ValueError(msg)
        self.xp += amount
        table = self.rules.xp_to_next_level
        while self.level < self.rules.max_level and self.xp >= table[self.level]:
            self.xp -= table[self.level]
            self.level += 1

    def buy_xp(self) -> None:
        """Spend gold on experience.

        Raises:
            ValueError: If the player is at the level cap or short of gold.
        """
        if self.level >= self.rules.max_level:
            msg = f"{self.name} is already level {self.rules.max_level}"
            raise ValueError(msg)
        if self.gold < self.rules.xp_purchase_cost:
            msg = f"buying xp costs {self.rules.xp_purchase_cost} gold, {self.gold} available"
            raise ValueError(msg)
        self.gold -= self.rules.xp_purchase_cost
        self.add_xp(self.rules.xp_per_purchase)

    def reroll(self, pool: Pool, rng: Random) -> None:
        """Pay for a new shop.

        Raises:
            ValueError: If the player is short of gold.
        """
        if self.gold < self.rules.reroll_cost:
            msg = f"a reroll costs {self.rules.reroll_cost} gold, {self.gold} available"
            raise ValueError(msg)
        self.gold -= self.rules.reroll_cost
        self.shop = roll_shop(self.level, pool, rng, self.rules)

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

    def bench_unit(self, unit: Unit) -> None:
        """Move ``unit`` from the board to the bench.

        Raises:
            ValueError: If ``unit`` is not on the board or the bench is full.
        """
        if unit not in self.board:
            msg = f"that {unit.champion.name} is not on {self.name}'s board"
            raise ValueError(msg)
        if len(self.bench) >= self.rules.bench_size:
            msg = "the bench is full"
            raise ValueError(msg)
        self.board.remove(unit)
        self.bench.append(unit)

    def choose_augment(self, index: int) -> Augment:
        """Take augment ``index`` of the pending offer, apply it, and clear the offer.

        Raises:
            ValueError: If nothing is on offer or ``index`` is out of range.
        """
        if not self.pending_augments:
            msg = "no augment is on offer"
            raise ValueError(msg)
        if not 0 <= index < len(self.pending_augments):
            msg = f"augment choice must be 0 to {len(self.pending_augments) - 1}"
            raise ValueError(msg)
        augment = self.pending_augments[index]
        self.augments.append(augment)
        self.gold += augment.gold
        self.pending_augments = []
        return augment

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
"""A planning-phase decision maker for a bot seat: acts on the player, then returns."""


def greedy_items(player: Player) -> None:
    """Craft every pair of components and hand the items to the strongest fielded units."""
    rules = player.rules
    for _ in range(len(player.components) // 2):
        _ = player.craft(0, 1)
    for unit in sorted(player.board, key=lambda unit: -unit.power(rules)):
        while player.items and len(unit.items) < rules.max_items_per_unit:
            _ = player.equip(unit, 0)


def greedy_policy(player: Player, pool: Pool, rng: Random) -> None:
    """A baseline bot: buy what it can afford, field the strongest units, level, use items.

    Raises:
        ValueError: If the player's shop has not been rolled.
    """
    del rng  # the greedy bot is deterministic
    rules = player.rules
    if len(player.shop) != rules.shop_size:
        msg = f"{player.name}'s shop has not been rolled"
        raise ValueError(msg)
    for slot, unit in enumerate(player.shop):
        if unit is None or player.gold < unit.cost or len(player.bench) >= rules.bench_size:
            continue
        player.buy(slot, pool)
    while player.bench and len(player.board) < player.board_limit:
        player.field_unit(max(player.bench, key=lambda unit: unit.power(rules)))
    if (
        player.level < rules.max_level
        and player.gold >= rules.xp_purchase_cost + rules.econ_reserve
    ):
        player.buy_xp()
    greedy_items(player)


@dataclass(frozen=True)
class RoundReport:
    """What happened in one round."""

    round_id: RoundId
    results: tuple[CombatResult, ...]
    eliminated: tuple[str, ...]
    slice_label: str | None = None


@dataclass(frozen=True)
class SeatView:
    """What scouting shows of another seat: everything but the shop, the bench and the inventory."""

    name: str
    health: int
    level: int
    gold: int
    streak: int
    units: tuple[str, ...]
    traits: tuple[str, ...]


def seat_view(player: Player) -> SeatView:
    """Return the public view of ``player``."""
    traits = active_traits_for(player.board_entries())
    return SeatView(
        player.name,
        player.health,
        player.level,
        player.gold,
        player.streak,
        tuple(unit.describe() for unit in player.board),
        tuple(f"{name} {tier}" for name, tier in sorted(traits.items())),
    )


def market_board(
    round_id: RoundId, rules: Rules = DEFAULT_RULES, champions: Sequence[Champion] = CHAMPIONS
) -> Player:
    """Return the scripted Market: a board that grows with the stage, bigger on boss rounds."""
    stage = round_id.stage
    count = min(stage + 1, rules.lobby_size) + (1 if round_id.number == rules.boss_round else 0)
    cost = max(COSTS) if stage >= MARKET_FINAL_STAGE else min(stage, MARKET_TOP_COST)
    star = 1 if stage <= MARKET_MID_STAGE else min(2, rules.max_star)
    ranked = sorted(enumerate(champions), key=lambda item: (abs(item[1].cost - cost), item[0]))
    market = Player(MARKET, level=count, rules=rules)
    market.board = [Unit(champion, star) for _, champion in ranked[:count]]
    return market


def market_power(round_id: RoundId, rules: Rules = DEFAULT_RULES) -> int:
    """Return the power of the scripted Market's board for ``round_id``."""
    return market_board(round_id, rules).team_power


class Game:
    """A whole match: lobby, shared pool, market pack, the round loop and the standings."""

    def __init__(
        self,
        names: Sequence[str],
        seed: int = 0,
        *,
        rules: Rules = DEFAULT_RULES,
        resolver: CombatResolver | None = None,
        policies: Mapping[str, Policy | None] | None = None,
        champions: Sequence[Champion] = CHAMPIONS,
        pack: MarketPack | None = None,
    ) -> None:
        """Seat the players and seed the match.

        ``policies`` maps a seat to its bot, or to ``None`` for a seat driven from
        outside between :meth:`start_round` and :meth:`finish_round`; seats not
        listed get the greedy bot. With a ``pack`` and no ``resolver``, fights are
        decided by the market replay; without a pack, by the power comparison.

        Raises:
            ValueError: If the lobby size or the names are invalid, or a policy
                names a seat that is not in the lobby.
        """
        lobby = rules.min_players <= len(names) <= rules.lobby_size
        if not lobby or len(set(names)) != len(names):
            msg = f"a lobby needs {rules.min_players} to {rules.lobby_size} distinct players"
            raise ValueError(msg)
        given = dict(policies or {})
        strangers = sorted(set(given) - set(names))
        if strangers:
            msg = f"policies name seats that are not in the lobby: {', '.join(strangers)}"
            raise ValueError(msg)
        self.rules = rules
        self.seed = seed
        self.rng = Random(seed)  # noqa: S311 - game randomness, not cryptography
        self.pool = Pool(champions, rules)
        self.pack = pack
        self.slice: Slice | None = None
        self.players = [Player(name, health=rules.starting_health, rules=rules) for name in names]
        default: CombatResolver = (
            MarketResolver(pack, rules) if pack is not None else PowerResolver()
        )
        self.resolver: CombatResolver = resolver if resolver is not None else default
        self.policies: dict[str, Policy | None] = {n: given.get(n, greedy_policy) for n in names}
        self.rounds = round_sequence(rules)
        self.round_index = 0
        self.eliminated: list[str] = []
        self.phase = PHASE_BETWEEN
        self.current: RoundId | None = None

    @property
    def alive(self) -> list[Player]:
        """Return the players still in the match, in seat order."""
        return [player for player in self.players if player.alive]

    @property
    def finished(self) -> bool:
        """Return whether the match is over: one player left, or no rounds left."""
        between = self.phase == PHASE_BETWEEN
        return between and (len(self.alive) <= 1 or self.round_index >= len(self.rounds))

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

    def scout(self, name: str) -> list[SeatView]:
        """Return the public view of every other living seat, as ``name`` would scout them."""
        _ = self.player(name)
        return [seat_view(player) for player in self.alive if player.name != name]

    def preview_odds(self, name: str) -> list[tuple[str, float]]:
        """Return ``name``'s odds of beating each other living seat on bootstrapped market slices.

        The preview draws from its own random stream, so looking never changes the match.

        Raises:
            ValueError: If the game has no market pack.
        """
        if self.pack is None:
            msg = "the preview needs a market pack"
            raise ValueError(msg)
        seat = self.player(name)
        rng = Random(f"preview-{self.seed}-{self.round_index}")  # noqa: S311 - game randomness
        others = [player for player in self.alive if player.name != name]
        return [(other.name, preview(seat, other, self.pack, self.rules, rng)) for other in others]

    def start_round(self) -> RoundId:
        """Open the next round: deal the slice, pay income, run events, roll shops, bots plan.

        Raises:
            RuntimeError: If the match is finished or a round is already open.
        """
        if self.phase != PHASE_BETWEEN:
            msg = "finish the current round before starting another"
            raise RuntimeError(msg)
        if self.finished:
            msg = "the match is finished"
            raise RuntimeError(msg)
        round_id = self.rounds[self.round_index]
        self.round_index += 1
        self.current = round_id
        self.phase = PHASE_PLANNING
        self.slice = (
            self.pack.deal(self.rng, self.rules.slice_bars) if self.pack is not None else None
        )
        for player in self.alive:
            self.prepare(player, round_id)
        return round_id

    def finish_round(self) -> RoundReport:
        """Close the open round: settle augments, fight, apply damage, eliminate.

        Raises:
            RuntimeError: If no round is open.
        """
        if self.phase != PHASE_PLANNING or self.current is None:
            msg = "start a round first"
            raise RuntimeError(msg)
        round_id = self.current
        for player in self.alive:
            if player.pending_augments:
                _ = player.choose_augment(0)
        results = self.fight(round_id)
        fallen = [p.name for p in self.players if not p.alive and p.name not in self.eliminated]
        self.eliminated.extend(fallen)
        label = self.slice.label if self.slice is not None else None
        self.phase = PHASE_BETWEEN
        self.current = None
        return RoundReport(round_id, tuple(results), tuple(fallen), label)

    def step(self) -> RoundReport:
        """Play one whole round with every seat on its policy."""
        _ = self.start_round()
        return self.finish_round()

    def prepare(self, player: Player, round_id: RoundId) -> None:
        """Run a seat's start of round: income, experience, events, drops, shop, and its bot.

        Raises:
            ValueError: If the player has already been eliminated.
        """
        if not player.alive:
            msg = f"{player.name} has been eliminated and does not play"
            raise ValueError(msg)
        player.collect_income()
        player.add_xp(self.rules.xp_per_round)
        if round_id.is_augment:
            player.pending_augments = self.rng.sample(AUGMENTS, self.rules.augment_choices)
        if round_id.is_pve:
            drops = [
                self.rng.choice(COMPONENTS) for _ in range(self.rules.components_per_pve_round)
            ]
            player.components.extend(drops)
        if round_id.is_carousel:
            self.carousel(player, round_id)
        player.shop = roll_shop(player.level, self.pool, self.rng, self.rules)
        policy = self.policies[player.name]
        if policy is None:
            return
        if player.pending_augments:
            _ = player.choose_augment(0)
        policy(player, self.pool, self.rng)  # noqa: JPL07 - policies act by side effect

    def carousel(self, player: Player, round_id: RoundId) -> None:
        """Give the player a component and, bench permitting, a free champion scaled to the stage.

        Raises:
            ValueError: If called on a round that is not a carousel.
        """
        if not round_id.is_carousel:
            msg = f"round {round_id.label} is not a carousel"
            raise ValueError(msg)
        player.components.append(self.rng.choice(COMPONENTS))
        if len(player.bench) >= self.rules.bench_size:
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
        result = self.resolver.resolve(home, away, self.rng, CombatContext(round_id, self.slice))
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
        loser.take_damage(stage_damage(round_id.stage, self.rules) + result.survivors)
        return result

    def fight_market(self, player: Player, round_id: RoundId) -> CombatResult:
        """Fight the scripted Market board: win, draw, or take stage damage plus its survivors."""
        market = market_board(round_id, self.rules)
        context = CombatContext(round_id, self.slice)
        result = self.resolver.resolve(player, market, self.rng, context)
        self.settle_market(player, round_id, result)
        return result

    def settle_market(self, player: Player, round_id: RoundId, result: CombatResult) -> None:
        """Apply a PvE result: the streak, and damage when the Market won."""
        if result.is_draw:
            player.record_result(None)
        elif result.winner == player.name:
            player.record_result(True)
        else:
            player.record_result(False)
            player.take_damage(stage_damage(round_id.stage, self.rules) + result.survivors)

    def run(self) -> list[str]:
        """Play until the match is finished, every seat on its policy, and return the placements."""
        for _ in range(len(self.rounds)):
            if self.finished:
                break
            _ = self.step()
        return self.placements
