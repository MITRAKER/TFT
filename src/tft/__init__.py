"""TFT package.

The modules in this package are the product code. :mod:`tft.economy` is a small
example module that ships with the repository scaffold so every pipeline stage has
real code to exercise; replace or extend it with the product's own modules.
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

try:
    __version__ = version("tft")
except PackageNotFoundError:  # pragma: no cover - only when the package is not installed
    __version__ = "0.0.0"

__all__ = [
    "BASE_INCOME",
    "MAX_INTEREST",
    "MAX_STREAK_BONUS",
    "__version__",
    "interest",
    "round_income",
    "rounds_to_reach",
    "streak_bonus",
]
