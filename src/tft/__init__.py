"""Ticker Fight Tactics: the engine package.

The product is a trading auto-battler (see ``docs/PRD.md``). :mod:`tft.economy`
holds the income rules, :mod:`tft.roster` the mock traits and champions, and
:mod:`tft.environment` the headless, deterministic game environment with its
pluggable combat resolver.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from tft.economy import (
    BASE_INCOME,
    MAX_INTEREST,
    MAX_STREAK_BONUS,
    interest,
    round_income,
    rounds_to_reach,
    streak_bonus,
)
from tft.environment import CombatResolver, Game, Player, PowerResolver, RoundId
from tft.roster import CHAMPIONS, TRAITS, Champion, Trait

try:
    __version__ = version("tft")
except PackageNotFoundError:  # pragma: no cover - only when the package is not installed
    __version__ = "0.0.0"

__all__ = [
    "BASE_INCOME",
    "CHAMPIONS",
    "MAX_INTEREST",
    "MAX_STREAK_BONUS",
    "TRAITS",
    "Champion",
    "CombatResolver",
    "Game",
    "Player",
    "PowerResolver",
    "RoundId",
    "Trait",
    "__version__",
    "interest",
    "round_income",
    "rounds_to_reach",
    "streak_bonus",
]
