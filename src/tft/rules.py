"""Every tunable number of the game in one place, loadable from a TOML file.

``Rules()`` is the default rule set. ``Rules.from_toml(path)`` reads a file
whose keys are the field names below, ``to_toml()`` writes the current values
back so a rule set can be checked in next to a match replay, and ``digest()``
fingerprints it so a replay refuses to run under different rules.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

COST_TIERS = (1, 2, 3, 4, 5)
ODDS_TOTAL = 100
INT_KEY_TABLES = (
    "pool_sizes",
    "shop_odds",
    "xp_to_next_level",
    "stage_base_damage",
    "star_power_tenths",
)
"""Tables whose keys are integers; TOML only has string keys, so they are converted."""


def _default_pool_sizes() -> dict[int, int]:
    return {1: 30, 2: 25, 3: 18, 4: 10, 5: 9}


def _default_shop_odds() -> dict[int, tuple[int, ...]]:
    return {
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


def _default_xp() -> dict[int, int]:
    return {1: 2, 2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 48, 8: 80, 9: 84}


def _default_stage_damage() -> dict[int, int]:
    return {1: 0, 2: 2, 3: 5, 4: 8, 5: 10, 6: 12, 7: 17}


def _default_star_power() -> dict[int, int]:
    return {1: 10, 2: 18, 3: 32}


@dataclass(frozen=True)
class Rules:
    """The rule set: lobby, economy, shop, levels, rounds, damage and the mock Market."""

    starting_health: int = 100
    lobby_size: int = 8
    min_players: int = 2
    shop_size: int = 5
    bench_size: int = 9
    max_level: int = 10
    reroll_cost: int = 2
    xp_purchase_cost: int = 4
    xp_per_purchase: int = 4
    xp_per_round: int = 2
    copies_to_star_up: int = 3
    max_star: int = 3
    opening_rounds: int = 3
    rounds_per_stage: int = 7
    stages: int = 7
    carousel_round: int = 4
    boss_round: int = 7
    augment_rounds: tuple[tuple[int, int], ...] = ((2, 1), (3, 2), (4, 2))
    augment_choices: int = 3
    market_power_per_stage: int = 6
    market_boss_factor_tenths: int = 15
    market_survivors: int = 2
    econ_reserve: int = 10
    slice_bars: int = 10
    risk_penalty_tenths: int = 5
    preview_samples: int = 200
    components_per_pve_round: int = 1
    max_items_per_unit: int = 3
    trade_cost_bps: int = 5
    momentum_lookback: int = 3
    stop_percent: int = 2
    target_percent: int = 4
    reversion_threshold_tenths: int = 15
    hedge_floor_percent: int = 2
    hedge_premium_tenths: int = 5
    whale_leverage_tenths: int = 20
    arb_capture_percent: int = 20
    pool_sizes: dict[int, int] = field(default_factory=_default_pool_sizes)
    shop_odds: dict[int, tuple[int, ...]] = field(default_factory=_default_shop_odds)
    xp_to_next_level: dict[int, int] = field(default_factory=_default_xp)
    stage_base_damage: dict[int, int] = field(default_factory=_default_stage_damage)
    star_power_tenths: dict[int, int] = field(default_factory=_default_star_power)

    def __post_init__(self) -> None:
        """Check the rule set is playable.

        Raises:
            ValueError: If a count is not positive, a table has the wrong keys,
                or a shop odds row does not add up to 100.
        """
        self._check_counts()
        self._check_tables()

    def _check_counts(self) -> None:
        """Validate the scalar settings."""
        positive = {
            name: getattr(self, name)
            for name in (
                "starting_health",
                "lobby_size",
                "shop_size",
                "bench_size",
                "max_level",
                "reroll_cost",
                "xp_purchase_cost",
                "xp_per_purchase",
                "xp_per_round",
                "copies_to_star_up",
                "max_star",
                "opening_rounds",
                "rounds_per_stage",
                "stages",
                "augment_choices",
                "market_power_per_stage",
                "market_boss_factor_tenths",
                "slice_bars",
                "preview_samples",
                "max_items_per_unit",
                "momentum_lookback",
                "stop_percent",
                "target_percent",
                "whale_leverage_tenths",
            )
        }
        bad = sorted(name for name, value in positive.items() if value <= 0)
        if bad:
            msg = f"these rules must be positive: {', '.join(bad)}"
            raise ValueError(msg)
        signed = (
            "risk_penalty_tenths",
            "components_per_pve_round",
            "trade_cost_bps",
            "reversion_threshold_tenths",
            "hedge_floor_percent",
            "hedge_premium_tenths",
            "arb_capture_percent",
            "econ_reserve",
        )
        negative = sorted(name for name in signed if getattr(self, name) < 0)
        if negative:
            msg = f"these rules must not be negative: {', '.join(negative)}"
            raise ValueError(msg)
        if self.slice_bars < 2:  # noqa: PLR2004
            msg = "slice_bars must be at least 2"
            raise ValueError(msg)
        if not 2 <= self.min_players <= self.lobby_size:  # noqa: PLR2004
            msg = "min_players must be at least 2 and at most lobby_size"
            raise ValueError(msg)
        in_stage = (self.carousel_round, self.boss_round)
        if any(not 1 <= number <= self.rounds_per_stage for number in in_stage):
            msg = "carousel_round and boss_round must fall inside a stage"
            raise ValueError(msg)

    def _check_tables(self) -> None:
        """Validate the lookup tables."""
        if set(self.pool_sizes) != set(COST_TIERS):
            msg = "pool_sizes needs exactly the cost tiers 1 to 5"
            raise ValueError(msg)
        if set(self.shop_odds) != set(range(1, self.max_level + 1)):
            msg = "shop_odds needs one row per level from 1 to max_level"
            raise ValueError(msg)
        for level, row in self.shop_odds.items():
            if len(row) != len(COST_TIERS) or sum(row) != ODDS_TOTAL or min(row) < 0:
                msg = f"shop_odds row for level {level} must be five percentages adding up to 100"
                raise ValueError(msg)
        if set(self.xp_to_next_level) != set(range(1, self.max_level)):
            msg = "xp_to_next_level needs one entry per level from 1 to max_level - 1"
            raise ValueError(msg)
        if set(self.star_power_tenths) != set(range(1, self.max_star + 1)):
            msg = "star_power_tenths needs one entry per star from 1 to max_star"
            raise ValueError(msg)
        if 1 not in self.stage_base_damage:
            msg = "stage_base_damage needs at least stage 1"
            raise ValueError(msg)

    @property
    def max_rounds(self) -> int:
        """Return the number of rounds in a full match."""
        return self.opening_rounds + (self.stages - 1) * self.rounds_per_stage

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> Rules:
        """Build a rule set from parsed TOML data; missing keys keep their defaults.

        Raises:
            ValueError: If a key is unknown or a table is not a table.
        """
        unknown = sorted(set(data) - {setting.name for setting in fields(cls)})
        if unknown:
            msg = f"unknown rules: {', '.join(unknown)}"
            raise ValueError(msg)
        values: dict[str, Any] = {}
        for key, raw in data.items():
            if key in INT_KEY_TABLES:
                if not isinstance(raw, dict):
                    msg = f"{key} must be a table"
                    raise ValueError(msg)
                values[key] = {
                    int(k): tuple(v) if isinstance(v, list) else v for k, v in raw.items()
                }
            elif key == "augment_rounds" and isinstance(raw, list):
                values[key] = tuple(tuple(pair) for pair in raw)
            else:
                values[key] = raw
        return cls(**values)

    @classmethod
    def from_toml(cls, path: Path) -> Rules:
        """Read a rule set from a TOML file."""
        return cls.from_mapping(tomllib.loads(path.read_text(encoding="utf-8")))

    def to_toml(self) -> str:
        """Write the rule set as TOML that :meth:`from_toml` reads back unchanged."""
        scalars: list[str] = []
        tables: list[str] = []
        for setting in fields(self):
            value = getattr(self, setting.name)
            if isinstance(value, dict):
                tables += render_table(setting.name, value)
            else:
                scalars.append(f"{setting.name} = {toml_value(value)}")
        header = "# Ticker Fight Tactics rule set: every number the engine uses."
        return "\n".join([header, *scalars, *tables]) + "\n"

    def digest(self) -> str:
        """Return a short fingerprint of the rule set for replays."""
        return hashlib.sha256(self.to_toml().encode("utf-8")).hexdigest()[:16]


def render_table(name: str, table: Mapping[object, object]) -> list[str]:
    """Render one TOML table: a blank line, the header and one line per key."""
    return ["", f"[{name}]", *(f"{key} = {toml_value(item)}" for key, item in table.items())]


def toml_scalar(value: object) -> str:
    """Render a bool, int or string as a TOML value.

    Raises:
        TypeError: For any other type.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    msg = f"cannot write {type(value).__name__} as TOML"
    raise TypeError(msg)


def toml_value(value: object) -> str:
    """Render a scalar, a list of scalars, or a list of lists of scalars as TOML."""
    if not isinstance(value, list | tuple):
        return toml_scalar(value)
    items = []
    for item in value:
        if isinstance(item, list | tuple):
            items.append("[" + ", ".join(toml_scalar(inner) for inner in item) + "]")
        else:
            items.append(toml_scalar(item))
    return "[" + ", ".join(items) + "]"


DEFAULT_RULES = Rules()
"""The rule set a match uses unless told otherwise."""
