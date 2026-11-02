"""Tests for :mod:`tft.rules`."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

from tft.rules import DEFAULT_RULES, Rules, toml_value


def test_defaults_describe_a_full_match() -> None:
    assert DEFAULT_RULES.max_rounds == 45
    assert len(DEFAULT_RULES.digest()) == 16
    assert Rules().digest() == DEFAULT_RULES.digest()
    assert Rules(stages=2).digest() != DEFAULT_RULES.digest()


def test_toml_round_trip_is_exact() -> None:
    text = DEFAULT_RULES.to_toml()
    assert text.startswith("# Ticker Fight Tactics rule set")
    assert Rules.from_mapping(tomllib.loads(text)) == DEFAULT_RULES


def test_from_toml_applies_overrides(tmp_path: Path) -> None:
    path = tmp_path / "rules.toml"
    path.write_text(
        "stages = 2\naugment_rounds = [[2, 1]]\n[pool_sizes]\n1 = 5\n2 = 5\n3 = 5\n4 = 5\n5 = 5\n",
        encoding="utf-8",
    )
    rules = Rules.from_toml(path)
    assert rules.max_rounds == 10
    assert rules.augment_rounds == ((2, 1),)
    assert rules.pool_sizes == dict.fromkeys(range(1, 6), 5)
    assert rules.shop_odds == DEFAULT_RULES.shop_odds


def test_from_mapping_rejects_unknown_keys_and_bad_tables() -> None:
    with pytest.raises(ValueError, match="unknown rules: bogus"):
        Rules.from_mapping({"bogus": 1})
    with pytest.raises(ValueError, match="must be a table"):
        Rules.from_mapping({"pool_sizes": 3})


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"shop_size": 0}, "positive"),
        ({"min_players": 1}, "min_players"),
        ({"min_players": 9}, "min_players"),
        ({"carousel_round": 9}, "inside a stage"),
        ({"pool_sizes": {1: 1}}, "pool_sizes"),
        ({"max_level": 3}, "shop_odds"),
        ({"shop_odds": {**DEFAULT_RULES.shop_odds, 1: (99, 0, 0, 0, 0)}}, "adding up to 100"),
        ({"shop_odds": {**DEFAULT_RULES.shop_odds, 1: (100, 0, 0, 0)}}, "five percentages"),
        ({"xp_to_next_level": {1: 2}}, "xp_to_next_level"),
        ({"star_power_tenths": {1: 10}}, "star_power_tenths"),
        ({"stage_base_damage": {2: 2}}, "stage_base_damage"),
    ],
)
def test_validation_rejects_unplayable_rules(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Rules(**overrides)


def test_toml_value_renders_supported_types() -> None:
    assert toml_value(True) == "true"
    assert toml_value(7) == "7"
    assert toml_value('a "q"') == '"a \\"q\\""'
    assert toml_value((1, [2, 3])) == "[1, [2, 3]]"
    with pytest.raises(TypeError, match="cannot write"):
        toml_value(1.5)
