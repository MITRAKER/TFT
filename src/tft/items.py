"""Items: the risk tools a trader-champion carries into a market slice.

Eight components drop from PvE rounds and carousels. Any two combine into a
completed item whose effect is the sum of its parts: tighter stops, wider
targets, bigger size, drawdown shields, or an emblem that grants a trait when
one part is the Prospectus (the genre's spatula). A unit holds up to three
items. Everything here is data; the market resolver applies the effects.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

TENTHS = 10


class Component(StrEnum):
    """A basic item component."""

    STOP_ORDER = "Stop Order"
    LIMIT_ORDER = "Limit Order"
    VOLUME_FILTER = "Volume Filter"
    VOLATILITY_GAUGE = "Volatility Gauge"
    HEDGE_TICKET = "Hedge Ticket"
    CASH_BUFFER = "Cash Buffer"
    MARGIN_NOTE = "Margin Note"
    PROSPECTUS = "Prospectus"


@dataclass(frozen=True)
class Effect:
    """What an item does to the unit that holds it.

    Multipliers are in tenths (``10`` means unchanged); percentages add up.
    """

    stop_tenths: int = TENTHS
    target_tenths: int = TENTHS
    size_percent: int = 0
    shield_percent: int = 0
    trait: str | None = None
    extra_slots: int = 0

    def combine(self, other: Effect) -> Effect:
        """Return the effect of holding both."""
        return Effect(
            self.stop_tenths * other.stop_tenths // TENTHS,
            self.target_tenths * other.target_tenths // TENTHS,
            self.size_percent + other.size_percent,
            self.shield_percent + other.shield_percent,
            self.trait or other.trait,
            self.extra_slots + other.extra_slots,
        )


COMPONENT_EFFECTS: dict[Component, Effect] = {
    Component.STOP_ORDER: Effect(stop_tenths=8),
    Component.LIMIT_ORDER: Effect(target_tenths=13),
    Component.VOLUME_FILTER: Effect(size_percent=15),
    Component.VOLATILITY_GAUGE: Effect(shield_percent=15),
    Component.HEDGE_TICKET: Effect(shield_percent=25),
    Component.CASH_BUFFER: Effect(size_percent=-10, shield_percent=35),
    Component.MARGIN_NOTE: Effect(size_percent=40, shield_percent=-20),
    Component.PROSPECTUS: Effect(),
}
"""What each component contributes."""

EMBLEMS: dict[Component, str] = {
    Component.STOP_ORDER: "Equities",
    Component.LIMIT_ORDER: "Tech",
    Component.VOLUME_FILTER: "Crypto",
    Component.VOLATILITY_GAUGE: "Forex",
    Component.HEDGE_TICKET: "Bonds",
    Component.CASH_BUFFER: "Commodities",
    Component.MARGIN_NOTE: "Whale",
}
"""The trait a Prospectus grants when combined with each other component."""

ITEM_NAMES: dict[frozenset[Component], str] = {
    frozenset({Component.STOP_ORDER}): "Trailing Stop",
    frozenset({Component.LIMIT_ORDER}): "Scaling Out",
    frozenset({Component.VOLUME_FILTER}): "Block Trade",
    frozenset({Component.VOLATILITY_GAUGE}): "Vega Cannon",
    frozenset({Component.HEDGE_TICKET}): "Full Hedge",
    frozenset({Component.CASH_BUFFER}): "War Chest",
    frozenset({Component.MARGIN_NOTE}): "Max Leverage",
    frozenset({Component.PROSPECTUS}): "Index Fund",
    frozenset({Component.STOP_ORDER, Component.LIMIT_ORDER}): "Bracket Order",
    frozenset({Component.STOP_ORDER, Component.VOLUME_FILTER}): "Liquidity Stop",
    frozenset({Component.STOP_ORDER, Component.VOLATILITY_GAUGE}): "ATR Stop",
    frozenset({Component.STOP_ORDER, Component.HEDGE_TICKET}): "Collar",
    frozenset({Component.STOP_ORDER, Component.CASH_BUFFER}): "Capital Preservation",
    frozenset({Component.STOP_ORDER, Component.MARGIN_NOTE}): "Margin Call Guard",
    frozenset({Component.LIMIT_ORDER, Component.VOLUME_FILTER}): "Iceberg Order",
    frozenset({Component.LIMIT_ORDER, Component.VOLATILITY_GAUGE}): "Volatility Target",
    frozenset({Component.LIMIT_ORDER, Component.HEDGE_TICKET}): "Covered Call",
    frozenset({Component.LIMIT_ORDER, Component.CASH_BUFFER}): "Patient Capital",
    frozenset({Component.LIMIT_ORDER, Component.MARGIN_NOTE}): "Leveraged Target",
    frozenset({Component.VOLUME_FILTER, Component.VOLATILITY_GAUGE}): "Breakout Scanner",
    frozenset({Component.VOLUME_FILTER, Component.HEDGE_TICKET}): "Dark Pool",
    frozenset({Component.VOLUME_FILTER, Component.CASH_BUFFER}): "Dollar-Cost Average",
    frozenset({Component.VOLUME_FILTER, Component.MARGIN_NOTE}): "Momentum Machine",
    frozenset({Component.VOLATILITY_GAUGE, Component.HEDGE_TICKET}): "Straddle",
    frozenset({Component.VOLATILITY_GAUGE, Component.CASH_BUFFER}): "Dry Powder",
    frozenset({Component.VOLATILITY_GAUGE, Component.MARGIN_NOTE}): "Vol Harvester",
    frozenset({Component.HEDGE_TICKET, Component.CASH_BUFFER}): "Treasury Ladder",
    frozenset({Component.HEDGE_TICKET, Component.MARGIN_NOTE}): "Pairs Trade",
    frozenset({Component.CASH_BUFFER, Component.MARGIN_NOTE}): "Credit Line",
}
"""Completed item names; a Prospectus with another component is that component's emblem."""


@dataclass(frozen=True)
class Item:
    """A completed item: its name, the two components it came from, and its effect."""

    name: str
    components: tuple[Component, Component]
    effect: Effect


def craft(first: Component, second: Component) -> Item:
    """Combine two components into a completed item.

    Raises:
        ValueError: If either value is not a component.
    """
    if first not in COMPONENT_EFFECTS or second not in COMPONENT_EFFECTS:
        msg = f"craft needs two components, got {first!r} and {second!r}"
        raise ValueError(msg)
    pair = frozenset({first, second})
    if pair == {Component.PROSPECTUS}:
        return Item(ITEM_NAMES[pair], (first, second), Effect(extra_slots=1))
    if Component.PROSPECTUS in pair:
        partner = next(component for component in pair if component is not Component.PROSPECTUS)
        trait = EMBLEMS[partner]
        effect = COMPONENT_EFFECTS[partner].combine(Effect(trait=trait))
        return Item(f"{trait} Emblem", (first, second), effect)
    effect = COMPONENT_EFFECTS[first].combine(COMPONENT_EFFECTS[second])
    return Item(ITEM_NAMES[pair], (first, second), effect)


def combined_effect(items: Iterable[Item]) -> Effect:
    """Return the total effect of ``items``."""
    total = Effect()
    for item in items:
        total = total.combine(item.effect)
    return total
