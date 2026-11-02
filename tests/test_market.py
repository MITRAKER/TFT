"""Tests for :mod:`tft.market`."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from random import Random

import pytest

from tft.market import (
    Bar,
    MarketPack,
    Series,
    aggregate_daily,
    assemble,
    chart_bars,
    load_builtin,
    local_date,
    spark_bars,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "market"


def tiny_pack() -> MarketPack:
    dates = tuple(f"2026-01-{day:02d}" for day in range(1, 13))
    up = Series("UP", tuple(Bar(100 + i, 101 + i, 99 + i, 100.5 + i, 10) for i in range(12)))
    down = Series("DOWN", tuple(Bar.from_close(100 - 2 * i) for i in range(12)))
    return MarketPack(
        "tiny",
        "1d",
        "test",
        dates,
        {"Equities": ("UP",), "Tech": ("DOWN",)},
        {"UP": up, "DOWN": down},
    )


def test_bar_validation_and_json() -> None:
    bar = Bar(10, 12, 9, 11, 5)
    assert Bar.from_json(bar.to_json()) == bar
    assert Bar.from_close(7).high == 7
    with pytest.raises(ValueError, match="positive"):
        Bar(0, 1, 1, 1)
    with pytest.raises(ValueError, match="bracket"):
        Bar(10, 10, 9, 12)
    for bad in ([1, 2, 3], [1, 2, 3, 4, "x"], [True, 1, 1, 1, 1], "bar"):
        with pytest.raises(ValueError, match="five numbers"):
            Bar.from_json(bad)


def test_series_returns() -> None:
    series = Series("X", (Bar.from_close(100), Bar.from_close(110), Bar.from_close(99)))
    assert [round(r, 4) for r in series.returns()] == [0.1, -0.1]


def test_pack_validation() -> None:
    pack = tiny_pack()
    with pytest.raises(ValueError, match="at least 2 dates"):
        MarketPack("x", "1d", "", ("2026-01-01",), {}, {})
    short = Series("UP", pack.series["UP"].bars[:3])
    with pytest.raises(ValueError, match="one bar per pack date"):
        MarketPack("x", "1d", "", pack.dates, {}, {"UP": short})
    with pytest.raises(ValueError, match="missing"):
        MarketPack("x", "1d", "", pack.dates, {"Crypto": ("NOPE",)}, dict(pack.series))


def test_pack_symbols_windows_and_deals() -> None:
    pack = tiny_pack()
    assert pack.symbols == ("DOWN", "UP")
    assert pack.symbols_for("Equities") == ("UP",)
    assert pack.symbols_for("Forex") == ("DOWN", "UP")
    window = pack.window(2, 4)
    assert window.dates == pack.dates[2:6]
    assert window.label == "2026-01-03 to 2026-01-06"
    assert len(window.bars["UP"]) == 4
    dealt = pack.deal(Random(3), 5)
    assert 0 <= dealt.start <= 7
    for start, length in ((0, 1), (-1, 3), (9, 4)):
        with pytest.raises(ValueError, match="does not fit"):
            pack.window(start, length)


def test_pack_json_round_trip_plain_and_gzip(tmp_path: Path) -> None:
    pack = tiny_pack()
    assert MarketPack.from_json(pack.to_json()) == pack
    plain, packed = tmp_path / "p.json", tmp_path / "p.json.gz"
    pack.save(plain)
    pack.save(packed)
    assert MarketPack.load(plain) == pack
    assert MarketPack.load(packed) == pack
    assert json.loads(plain.read_text())["format"] == 1
    with gzip.open(packed, "rt") as handle:
        assert json.load(handle)["name"] == "tiny"
    with pytest.raises(ValueError, match="not a market pack"):
        MarketPack.from_json({"format": 9})
    with pytest.raises(ValueError, match="incomplete"):
        MarketPack.from_json({"format": 1, "name": "x"})


def test_builtin_starter_pack() -> None:
    pack = load_builtin()
    assert pack.name == "starter"
    assert len(pack.symbols) == 29
    assert len(pack.dates) == 60
    assert set(pack.origins) == {"Equities", "Tech", "Crypto", "Commodities", "Bonds", "Forex"}
    tsla = pack.series["TSLA"].bars[0]
    assert tsla.high > tsla.low
    with pytest.raises(ValueError, match="no built-in"):
        load_builtin("nothing")


def test_local_date_uses_the_exchange_offset() -> None:
    assert local_date(1_761_000_000, -14_400) == "2025-10-20"


def test_chart_bars_aggregates_intraday_into_daily() -> None:
    with gzip.open(FIXTURES / "TSLA-60d5m.json.gz", "rt") as handle:
        data = json.load(handle)
    symbol, dated = chart_bars(data)
    assert symbol == "TSLA"
    assert len(dated) == 60
    date, bar = dated[0]
    assert date == "2026-07-27"
    assert bar.high >= max(bar.open, bar.close) >= min(bar.open, bar.close) >= bar.low
    assert bar.volume > 0
    with pytest.raises(ValueError, match="not a Yahoo chart"):
        chart_bars({"chart": {}})
    empty = {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "X"},
                    "timestamp": [1],
                    "indicators": {
                        "quote": [
                            {"open": [None], "high": [1], "low": [1], "close": [1], "volume": [1]}
                        ]
                    },
                }
            ]
        }
    }
    with pytest.raises(ValueError, match="no complete bars"):
        chart_bars(empty)


def test_aggregate_daily_merges_bars_of_one_date() -> None:
    merged = aggregate_daily(
        [("d", Bar(10, 11, 9, 10.5, 1)), ("d", Bar(10.5, 13, 10, 12, 2)), ("e", Bar.from_close(5))]
    )
    assert merged == [("d", Bar(10, 13, 9, 12, 3)), ("e", Bar.from_close(5))]


def test_spark_bars_reads_daily_closes() -> None:
    data = json.loads((FIXTURES / "spark-3mo-a.json").read_text())
    pieces = spark_bars(data)
    assert len(pieces) == 19
    symbol, dated = pieces[0]
    assert symbol == "AMZN"
    assert len(dated) == 65
    assert dated[0][1].high == dated[0][1].low
    with pytest.raises(ValueError, match="not a Yahoo spark"):
        spark_bars({"spark": None})
    with pytest.raises(ValueError, match="no complete series"):
        spark_bars({"spark": {"result": []}})


def test_assemble_aligns_dates_and_prefers_rich_series() -> None:
    rich = [
        ("2026-01-01", Bar(1, 2, 0.5, 1.5)),
        ("2026-01-02", Bar(1.5, 2, 1, 1.8)),
        ("2026-01-03", Bar(1.8, 2, 1, 1.9)),
    ]
    flat = [
        ("2026-01-02", Bar.from_close(9)),
        ("2026-01-03", Bar.from_close(9)),
        ("2026-01-04", Bar.from_close(9)),
    ]
    other = [("2026-01-02", Bar.from_close(5)), ("2026-01-03", Bar.from_close(6))]
    pack = assemble(
        "t", [("A", flat), ("A", rich), ("B", other)], {"Equities": ["A", "ZZZ"], "Tech": ["ZZZ"]}
    )
    assert pack.dates == ("2026-01-02", "2026-01-03")
    assert pack.series["A"].bars[0].high == 2
    assert pack.origins == {"Equities": ("A",)}
    with pytest.raises(ValueError, match="share only"):
        assemble("t", [("A", rich[:1]), ("B", other)], {})
