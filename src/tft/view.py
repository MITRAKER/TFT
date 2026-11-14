"""JSON views of a match for clients: what a seat sees, what a spectator sees, the catalogue.

Everything here returns plain dictionaries, lists, strings, numbers, booleans
and ``None``, ready for ``json.dumps``. A seat sees its own state in full and
the public state of the other seats (board, health, level, gold, streak): never
their shops, benches or inventories.
"""

from __future__ import annotations

from dataclasses import asdict
from itertools import combinations_with_replacement
from typing import Any

from tft.combat import unit_symbol
from tft.economy import BASE_INCOME, interest, round_income, streak_bonus
from tft.environment import AUGMENTS, Augment, Game, Player, RoundId, RoundReport, Unit, sell_value
from tft.items import COMPONENT_EFFECTS, Component, Effect, Item, craft
from tft.lessons import RoundSummary
from tft.market import MarketPack
from tft.roster import CHAMPIONS, TRAITS, trait_counts_for
from tft.rules import Rules
from tft.strategies import DESCRIPTIONS

Json = dict[str, Any]

TENTHS = 10
PHASE_FINISHED = "finished"


def effect_text(effect: Effect) -> str:
    """Describe an item effect in a short line, for tooltips."""
    parts = (
        (effect.stop_tenths != TENTHS, f"stop x{effect.stop_tenths / TENTHS:g}"),
        (effect.target_tenths != TENTHS, f"target x{effect.target_tenths / TENTHS:g}"),
        (effect.size_percent != 0, f"size {effect.size_percent:+d}%"),
        (effect.shield_percent != 0, f"drawdown shield {effect.shield_percent:+d}%"),
        (effect.trait is not None, f"counts as {effect.trait}"),
        (effect.extra_slots != 0, f"+{effect.extra_slots} board slot"),
    )
    return ", ".join(text for applies, text in parts if applies) or "no effect"


def item_view(item: Item) -> Json:
    """Return an item's name, the components it was made from and what it does."""
    return {
        "name": item.name,
        "components": [str(component) for component in item.components],
        "effect": effect_text(item.effect),
    }


def augment_view(augment: Augment) -> Json:
    """Return an augment's name, tier and text."""
    return {"name": augment.name, "tier": augment.tier, "text": augment.text}


def unit_view(unit: Unit, index: int, pack: MarketPack | None, rules: Rules) -> Json:
    """Return a unit as a client draws it; ``index`` is its number for actions."""
    champion = unit.champion
    cell = unit.position
    symbol = None
    if pack is not None and cell is not None:
        symbol = unit_symbol(pack, champion.origin, cell[1])
    return {
        "index": index,
        "name": champion.name,
        "cost": champion.cost,
        "origin": champion.origin,
        "role": champion.role,
        "star": unit.star,
        "power": unit.power(rules),
        "items": [item_view(item) for item in unit.items],
        "traits": list(unit.traits),
        "cell": list(cell) if cell is not None else None,
        "symbol": symbol,
        "sell": sell_value(champion.cost, unit.star, rules),
    }


def trait_views(player: Player) -> list[Json]:
    """Return the traits on the seat's board with counts, tiers and bonuses, strongest first."""
    counts = trait_counts_for(player.board_entries())
    views = [
        {
            "name": name,
            "kind": str(TRAITS[name].kind),
            "count": count,
            "tier": TRAITS[name].tier(count),
            "breakpoints": list(TRAITS[name].breakpoints),
            "bonus": TRAITS[name].bonus(count),
            "summary": TRAITS[name].summary,
        }
        for name, count in counts.items()
        if name in TRAITS
    ]
    return sorted(views, key=lambda view: (-view["tier"], -view["count"], view["name"]))


def shop_view(player: Player) -> list[Json | None]:
    """Return the shop slots; an empty slot is ``None``."""
    return [
        None
        if champion is None
        else {
            "slot": slot,
            "name": champion.name,
            "cost": champion.cost,
            "origin": champion.origin,
            "role": champion.role,
            "affordable": player.gold >= champion.cost,
        }
        for slot, champion in enumerate(player.shop)
    ]


def income_view(player: Player) -> Json:
    """Return what the seat will be paid at the start of the next round, by part."""
    return {
        "base": BASE_INCOME,
        "interest": interest(player.gold),
        "streak": streak_bonus(player.streak),
        "total": round_income(player.gold, player.streak),
    }


def public_seat(player: Player, pack: MarketPack | None, rules: Rules) -> Json:
    """Return what everybody may know about a seat."""
    return {
        "name": player.name,
        "health": player.health,
        "max_health": rules.starting_health,
        "level": player.level,
        "gold": player.gold,
        "streak": player.streak,
        "alive": player.alive,
        "board": [unit_view(unit, index, pack, rules) for index, unit in enumerate(player.board)],
        "traits": trait_views(player),
    }


def private_seat(player: Player, pack: MarketPack | None, rules: Rules) -> Json:
    """Return everything the seat's own player sees."""
    units = [unit_view(unit, index, pack, rules) for index, unit in enumerate(player.units)]
    fielded = len(player.board)
    view = public_seat(player, pack, rules)
    view.update(
        {
            "xp": player.xp,
            "xp_needed": rules.xp_to_next_level.get(player.level),
            "board_limit": player.board_limit,
            "board": units[:fielded],
            "bench": units[fielded:],
            "shop": shop_view(player),
            "components": [str(component) for component in player.components],
            "items": [item_view(item) for item in player.items],
            "augments": [augment_view(augment) for augment in player.augments],
            "offer": [augment_view(augment) for augment in player.pending_augments],
            "income": income_view(player),
            "odds": list(rules.shop_odds[player.level]),
        }
    )
    return view


def round_view(round_id: RoundId | None, game: Game) -> Json | None:
    """Return the open round, or ``None`` between rounds."""
    if round_id is None:
        return None
    return {
        "label": round_id.label,
        "stage": round_id.stage,
        "number": round_id.number,
        "pve": round_id.is_pve,
        "carousel": round_id.is_carousel,
        "augment": round_id.is_augment,
        "index": game.round_index,
        "total": len(game.rounds),
    }


def board_view(rules: Rules) -> Json:
    """Return the grid and what its rows do."""
    return {
        "rows": rules.board_rows,
        "cols": rules.board_cols,
        "row_size": list(rules.row_size_percent),
        "row_shield": list(rules.row_shield_percent),
        "cover": rules.cover_shield_percent,
        "exposed": rules.exposed_penalty_percent,
    }


def match_state(game: Game, seat: str | None) -> Json:
    """Return the match as ``seat`` sees it, or as a spectator sees it when ``seat`` is ``None``."""
    rules, pack = game.rules, game.pack
    others = [player for player in game.players if player.name != seat]
    own = private_seat(game.player(seat), pack, rules) if seat is not None else None
    return {
        "phase": PHASE_FINISHED if game.finished else game.phase,
        "mode": "market" if pack is not None else "power",
        "pack": pack.name if pack is not None else None,
        "round": round_view(game.current, game),
        "rounds_played": game.round_index,
        "board": board_view(rules),
        "costs": {
            "reroll": rules.reroll_cost,
            "xp": rules.xp_purchase_cost,
            "xp_gain": rules.xp_per_purchase,
        },
        "seat": own,
        "others": [public_seat(player, pack, rules) for player in others],
        "placements": game.placements if game.finished else None,
    }


def report_view(report: RoundReport) -> Json:
    """Return a round's fights and eliminations."""
    return {
        "round": report.round_id.label,
        "slice": report.slice_label,
        "fights": [
            {
                "home": result.home or result.winner,
                "away": result.away or result.loser,
                "winner": result.winner,
                "loser": result.loser,
                "draw": result.is_draw,
                "survivors": result.survivors,
                "home_score": result.home_score,
                "away_score": result.away_score,
            }
            for result in report.results
        ],
        "eliminated": list(report.eliminated),
    }


def summary_view(summary: RoundSummary) -> Json:
    """Return a round summary as plain data."""
    return asdict(summary)


def catalog(rules: Rules) -> Json:
    """Return the static content a client needs for tooltips: champions, traits, items, augments."""
    pairs = combinations_with_replacement(Component, 2)
    return {
        "champions": [
            {
                "name": champion.name,
                "cost": champion.cost,
                "origin": champion.origin,
                "role": champion.role,
                "ability": champion.ability,
                "text": champion.ability_text,
                "power": champion.power,
            }
            for champion in CHAMPIONS
        ],
        "traits": [
            {
                "name": trait.name,
                "kind": str(trait.kind),
                "summary": trait.summary,
                "breakpoints": list(trait.breakpoints),
                "bonuses": list(trait.bonus_per_tier),
            }
            for trait in TRAITS.values()
        ],
        "strategies": dict(DESCRIPTIONS),
        "components": [
            {"name": str(component), "effect": effect_text(COMPONENT_EFFECTS[component])}
            for component in Component
        ],
        "items": [item_view(craft(first, second)) for first, second in pairs],
        "augments": [augment_view(augment) for augment in AUGMENTS],
        "board": board_view(rules),
    }
