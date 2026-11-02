"""The installed package version must be the single version declared in pyproject.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

import tft

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_version_matches_pyproject() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert tft.__version__ == data["project"]["version"], (
        "install the package first: python -m pip install -e ."
    )
