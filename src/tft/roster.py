"""The mock roster: the traits and champions of the trading auto-battler.

Everything here is placeholder content for the product requirements document
(``docs/PRD.md``): names, costs, traits and ability text exist so that the
environment, the tests and the design discussion have concrete characters to
point at. The numbers are tuned for readability, not for balance.

Nothing is taken from Teamfight Tactics or any other game: no names, art or
data. Only the genre's conventions are used: cost tiers 1 to 5, one origin and
one class per champion, and trait breakpoints that reward distinct champions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

MIN_COST = 1
MAX_COST = 5


class TraitKind(StrEnum):
    """The two trait families; every champion has one of each."""

    ORIGIN = "origin"
    """The market the champion trades: Equities, Crypto, Bonds and so on."""

    CLASS = "class"
    """How the champion trades: Scalper, Swing, Momentum and so on."""


@dataclass(frozen=True)
class Trait:
    """A synergy: fielding enough distinct champions that share it unlocks tiers."""

    name: str
    kind: TraitKind
    summary: str
    breakpoints: tuple[int, ...]
    bonus_per_tier: tuple[int, ...]

    def __post_init__(self) -> None:
        """Validate the breakpoint table.

        Raises:
            ValueError: If there are no breakpoints, they are not ascending, or
                the bonus table has a different length.
        """
        pairs = zip(self.breakpoints, self.breakpoints[1:], strict=False)
        if not self.breakpoints or not all(low < high for low, high in pairs):
            msg = f"trait {self.name!r} needs ascending breakpoints, got {self.breakpoints}"
            raise ValueError(msg)
        if len(self.breakpoints) != len(self.bonus_per_tier):
            msg = f"trait {self.name!r} needs exactly one bonus per breakpoint"
            raise ValueError(msg)

    def tier(self, count: int) -> int:
        """Return the tier that ``count`` distinct champions unlock, 0 when none."""
        return sum(1 for threshold in self.breakpoints if count >= threshold)

    def bonus(self, count: int) -> int:
        """Return the power bonus in percent for ``count`` distinct champions."""
        tier = self.tier(count)
        return self.bonus_per_tier[tier - 1] if tier else 0


@dataclass(frozen=True)
class Champion:
    """A unit: a trading archetype with a market, a style, a cost and an ability."""

    name: str
    cost: int
    origin: str
    role: str
    ability: str
    ability_text: str
    power: int

    def __post_init__(self) -> None:
        """Validate the cost tier and the base power.

        Raises:
            ValueError: If the cost is outside 1 to 5 or the power is not positive.
        """
        if not MIN_COST <= self.cost <= MAX_COST:
            msg = f"champion {self.name!r} has cost {self.cost}; expected {MIN_COST} to {MAX_COST}"
            raise ValueError(msg)
        if self.power <= 0:
            msg = f"champion {self.name!r} needs a positive power, got {self.power}"
            raise ValueError(msg)

    @property
    def traits(self) -> tuple[str, str]:
        """Return the champion's origin and class names."""
        return (self.origin, self.role)


ORIGINS: tuple[Trait, ...] = (
    Trait(
        "Equities",
        TraitKind.ORIGIN,
        "Stocks: broad and liquid, the backbone of most boards.",
        (2, 4, 6),
        (10, 25, 45),
    ),
    Trait(
        "Tech",
        TraitKind.ORIGIN,
        "Growth names: momentum darlings that crash the hardest.",
        (2, 4, 6),
        (15, 35, 60),
    ),
    Trait(
        "Crypto",
        TraitKind.ORIGIN,
        "Volatile tokens: huge swings in both directions.",
        (2, 4),
        (20, 50),
    ),
    Trait(
        "Commodities",
        TraitKind.ORIGIN,
        "Oil, metals and grain: slow, heavy and hard to kill.",
        (2, 4),
        (10, 30),
    ),
    Trait(
        "Bonds",
        TraitKind.ORIGIN,
        "Fixed income: low power, steady interest.",
        (2, 4),
        (5, 15),
    ),
    Trait(
        "Forex",
        TraitKind.ORIGIN,
        "Currency pairs: fast, leveraged and always open.",
        (2, 4),
        (15, 35),
    ),
)
"""The markets a champion can trade."""

CLASSES: tuple[Trait, ...] = (
    Trait(
        "Scalper",
        TraitKind.CLASS,
        "Many tiny trades: attacks fast and dies fast.",
        (2, 4),
        (15, 40),
    ),
    Trait("Swing", TraitKind.CLASS, "Holds for days: balanced stats.", (2, 4), (10, 30)),
    Trait(
        "Momentum",
        TraitKind.CLASS,
        "Buys strength: power grows while the team is winning.",
        (2, 4, 6),
        (15, 35, 60),
    ),
    Trait(
        "Contrarian",
        TraitKind.CLASS,
        "Fades the crowd: stronger when behind.",
        (2, 4),
        (15, 40),
    ),
    Trait("Hedger", TraitKind.CLASS, "Buys protection: shields the board.", (2, 4), (10, 30)),
    Trait(
        "Arbitrageur",
        TraitKind.CLASS,
        "Exploits price gaps: steals gold on wins.",
        (2,),
        (25,),
    ),
    Trait(
        "Quant",
        TraitKind.CLASS,
        "Models everything: scales with the number of distinct traits.",
        (2, 4),
        (15, 40),
    ),
    Trait(
        "Whale",
        TraitKind.CLASS,
        "Moves markets alone: a synergy of one.",
        (1,),
        (30,),
    ),
)
"""The trading styles."""

TRAITS: dict[str, Trait] = {trait.name: trait for trait in (*ORIGINS, *CLASSES)}
"""Every trait by name."""

BASE_POWER: dict[int, int] = {1: 10, 2: 14, 3: 20, 4: 28, 5: 40}
"""Mock one-star power by cost tier."""


def _unit(name: str, cost: int, origin: str, role: str, ability: str, text: str) -> Champion:
    """Build a roster champion with the mock power of its cost tier."""
    return Champion(name, cost, origin, role, ability, text, BASE_POWER[cost])


CHAMPIONS: tuple[Champion, ...] = (
    # 1-cost
    _unit(
        "Pip Squeak", 1, "Forex", "Scalper", "Tick Hunt", "Every third attack in a row lands twice."
    ),
    _unit(
        "Index Drone",
        1,
        "Equities",
        "Quant",
        "Rebalance",
        "Copies the strongest ally's trait bonus for a moment.",
    ),
    _unit(
        "Hodl Hamster",
        1,
        "Crypto",
        "Contrarian",
        "Diamond Paws",
        "Gains a shield when below half health.",
    ),
    _unit(
        "Barrel Bo",
        1,
        "Commodities",
        "Swing",
        "Roll Over",
        "Heals a little at the start of every round.",
    ),
    _unit("Coupon Clerk", 1, "Bonds", "Hedger", "Yield Shield", "Shields the allies next to it."),
    _unit(
        "Candle Reader",
        1,
        "Tech",
        "Momentum",
        "Engulfing",
        "Hits harder right after an ally scores a big hit.",
    ),
    # 2-cost
    _unit(
        "Gap Gazelle",
        2,
        "Equities",
        "Momentum",
        "Gap and Go",
        "Opens the fight with a burst of speed.",
    ),
    _unit(
        "Mean Reverend",
        2,
        "Equities",
        "Contrarian",
        "Back to the Mean",
        "Heals the most damaged ally toward average health.",
    ),
    _unit(
        "Spread Spider",
        2,
        "Forex",
        "Arbitrageur",
        "Pip Web",
        "Slows two enemies and steals a little gold on a win.",
    ),
    _unit(
        "Gold Bug",
        2,
        "Commodities",
        "Hedger",
        "Safe Haven",
        "Takes less damage while the team is losing.",
    ),
    _unit(
        "Stable Coin",
        2,
        "Crypto",
        "Hedger",
        "The Peg",
        "Cannot drop below a fixed health until the peg breaks.",
    ),
    _unit(
        "Yield Yeti",
        2,
        "Bonds",
        "Swing",
        "Coupon Crush",
        "Slams the ground; damage scales with banked gold.",
    ),
    # 3-cost
    _unit(
        "Breakout Bull",
        3,
        "Equities",
        "Momentum",
        "Opening Range Breakout",
        "Charges when the price closes above the opening range.",
    ),
    _unit(
        "Bear Baron",
        3,
        "Equities",
        "Contrarian",
        "Bear Raid",
        "Deals bonus damage to the enemy with the most power.",
    ),
    _unit(
        "Vol Vampire",
        3,
        "Tech",
        "Quant",
        "Implied Volatility",
        "Drains health from enemies in proportion to their swings.",
    ),
    _unit(
        "Carry Caravan", 3, "Forex", "Swing", "Carry Trade", "Earns gold every round it survives."
    ),
    _unit(
        "Miner Mole",
        3,
        "Crypto",
        "Scalper",
        "Hash Rate",
        "Attack speed ramps up the longer the fight lasts.",
    ),
    _unit(
        "Crude Colossus",
        3,
        "Commodities",
        "Momentum",
        "Supply Shock",
        "Knocks back a line of enemies.",
    ),
    # 4-cost
    _unit(
        "Market Maker",
        4,
        "Equities",
        "Arbitrageur",
        "Bid-Ask Bite",
        "Takes a cut of every trade on the board.",
    ),
    _unit(
        "Fed Whisperer",
        4,
        "Bonds",
        "Quant",
        "Rate Decision",
        "Raises or lowers every unit's speed for the round.",
    ),
    _unit(
        "Flash Crash",
        4,
        "Tech",
        "Scalper",
        "Liquidity Vacuum",
        "Pulls enemies together and detonates.",
    ),
    _unit(
        "Whale Watcher",
        4,
        "Crypto",
        "Whale",
        "Order Wall",
        "Builds a wall that absorbs a huge amount of damage.",
    ),
    # 5-cost
    _unit(
        "Black Swan",
        5,
        "Equities",
        "Contrarian",
        "Tail Event",
        "Hits the whole enemy board when the team is behind.",
    ),
    _unit(
        "Central Banker",
        5,
        "Bonds",
        "Whale",
        "Quantitative Easing",
        "Prints gold and heals the board with it.",
    ),
    _unit(
        "Algo Overlord",
        5,
        "Tech",
        "Quant",
        "Backtest Everything",
        "Replays the fight once and keeps the better result.",
    ),
)
"""The v0 roster: twenty-five original trader-champions."""

CHAMPIONS_BY_NAME: dict[str, Champion] = {champion.name: champion for champion in CHAMPIONS}
"""Every roster champion by name."""


def champion(name: str) -> Champion:
    """Return the roster champion called ``name``.

    Raises:
        KeyError: If no champion has that name.
    """
    if name not in CHAMPIONS_BY_NAME:
        msg = f"no champion named {name!r}"
        raise KeyError(msg)
    return CHAMPIONS_BY_NAME[name]


def champions_of_cost(cost: int) -> tuple[Champion, ...]:
    """Return the roster champions of one cost tier, in roster order.

    Raises:
        ValueError: If ``cost`` is outside 1 to 5.
    """
    if not MIN_COST <= cost <= MAX_COST:
        msg = f"cost must be {MIN_COST} to {MAX_COST}, got {cost}"
        raise ValueError(msg)
    return tuple(unit for unit in CHAMPIONS if unit.cost == cost)


TraitEntry = tuple[str, Iterable[str]]
"""A champion's name and every trait it counts for, emblems included."""


def trait_counts_for(entries: Iterable[TraitEntry]) -> dict[str, int]:
    """Count the distinct champions per trait, the genre's rule for synergies."""
    distinct: dict[str, set[str]] = {}
    for name, names in entries:
        distinct.setdefault(name, set()).update(names)
    counts: Counter[str] = Counter()
    for names in distinct.values():
        counts.update(names)
    return dict(counts)


def active_traits_for(
    entries: Iterable[TraitEntry], traits: Mapping[str, Trait] = TRAITS
) -> dict[str, int]:
    """Return the unlocked tier of every known trait that is active on ``entries``."""
    counts = trait_counts_for(entries)
    tiers = {name: traits[name].tier(count) for name, count in counts.items() if name in traits}
    return {name: tier for name, tier in tiers.items() if tier > 0}


def synergy_bonus_for(entries: Iterable[TraitEntry], traits: Mapping[str, Trait] = TRAITS) -> int:
    """Return the total trait power bonus in percent for ``entries``."""
    counts = trait_counts_for(entries)
    return sum(traits[name].bonus(count) for name, count in counts.items() if name in traits)


def trait_counts(champions: Iterable[Champion]) -> dict[str, int]:
    """Count the distinct champions per trait, the genre's rule for synergies."""
    return trait_counts_for((unit.name, unit.traits) for unit in champions)


def active_traits(
    champions: Iterable[Champion], traits: Mapping[str, Trait] = TRAITS
) -> dict[str, int]:
    """Return the unlocked tier of every trait that is active on ``champions``."""
    return active_traits_for(((unit.name, unit.traits) for unit in champions), traits)


def synergy_bonus(champions: Iterable[Champion], traits: Mapping[str, Trait] = TRAITS) -> int:
    """Return the total trait power bonus in percent for ``champions``."""
    return synergy_bonus_for(((unit.name, unit.traits) for unit in champions), traits)


def validate_roster(
    champions: Sequence[Champion] = CHAMPIONS, traits: Mapping[str, Trait] = TRAITS
) -> None:
    """Check that the roster is consistent.

    Raises:
        ValueError: If a name repeats, a trait is unknown or of the wrong kind,
            or a cost tier has no champion.
    """
    names = [unit.name for unit in champions]
    if len(set(names)) != len(names):
        msg = "champion names must be unique"
        raise ValueError(msg)
    for unit in champions:
        origin, role = traits.get(unit.origin), traits.get(unit.role)
        if origin is None or origin.kind is not TraitKind.ORIGIN:
            msg = f"{unit.name!r} has an unknown origin {unit.origin!r}"
            raise ValueError(msg)
        if role is None or role.kind is not TraitKind.CLASS:
            msg = f"{unit.name!r} has an unknown class {unit.role!r}"
            raise ValueError(msg)
    costs = {unit.cost for unit in champions}
    missing = [cost for cost in range(MIN_COST, MAX_COST + 1) if cost not in costs]
    if missing:
        msg = f"no champion for cost tiers {missing}"
        raise ValueError(msg)
