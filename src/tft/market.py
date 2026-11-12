"""Market packs: the real historical bars that decide combat.

A pack holds one bar series per symbol, all aligned on the same dates, and a
map from each origin (the market a champion trades) to the symbols that stand
for it. Each round the game deals one **slice**, a window of consecutive bars
shared by the whole lobby, and the market resolver scores every board on it.

Packs are plain JSON (optionally gzip-compressed) so they can be versioned
next to replays. ``tools/build_market_pack.py`` builds them from Yahoo Finance
*chart* and *spark* responses, offline or fetched. Close-only sources (spark)
produce bars whose open, high and low equal the close; intraday chart data is
aggregated into one daily bar per session.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from random import Random
from typing import Any

FORMAT_VERSION = 1
BAR_FIELDS = 5
MIN_BARS = 2


@dataclass(frozen=True)
class Bar:
    """One period of trading: open, high, low, close and volume."""

    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        """Validate the bar.

        Raises:
            ValueError: If a price is not positive or the high and low do not bracket the rest.
        """
        prices = (self.open, self.high, self.low, self.close)
        if min(prices) <= 0:
            msg = f"bar prices must be positive, got {prices}"
            raise ValueError(msg)
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            msg = f"bar high and low must bracket open and close, got {prices}"
            raise ValueError(msg)

    @classmethod
    def from_close(cls, close: float) -> Bar:
        """Return a bar that only knows its close."""
        return cls(close, close, close, close, 0.0)

    def to_json(self) -> list[float]:
        """Return ``[open, high, low, close, volume]``."""
        return [self.open, self.high, self.low, self.close, self.volume]

    @classmethod
    def from_json(cls, data: object) -> Bar:
        """Rebuild a bar from ``[open, high, low, close, volume]``.

        Raises:
            ValueError: If the data is not five numbers.
        """
        if not isinstance(data, list) or len(data) != BAR_FIELDS:
            msg = f"a bar is a list of five numbers, got {data!r}"
            raise ValueError(msg)
        if not all(isinstance(item, int | float) and not isinstance(item, bool) for item in data):
            msg = f"a bar is a list of five numbers, got {data!r}"
            raise ValueError(msg)
        return cls(*(float(item) for item in data))


@dataclass(frozen=True)
class Series:
    """A symbol's bars, one per date of the pack."""

    symbol: str
    bars: tuple[Bar, ...]

    def returns(self) -> tuple[float, ...]:
        """Return the close-to-close returns, one fewer than the bars."""
        closes = [bar.close for bar in self.bars]
        return tuple(closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)))


@dataclass(frozen=True)
class Slice:
    """The window of bars one round is fought on, the same dates for every symbol."""

    start: int
    dates: tuple[str, ...]
    bars: Mapping[str, tuple[Bar, ...]]

    @property
    def label(self) -> str:
        """Return ``first date to last date``."""
        return f"{self.dates[0]} to {self.dates[-1]}"


@dataclass
class MarketPack:
    """Aligned bar series for a set of symbols, grouped by the origin they represent."""

    name: str
    interval: str
    source: str
    dates: tuple[str, ...]
    origins: dict[str, tuple[str, ...]]
    series: dict[str, Series] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the pack.

        Raises:
            ValueError: If the dates are too few, a series has the wrong length,
                or an origin names a symbol the pack does not hold.
        """
        if len(self.dates) < MIN_BARS:
            msg = f"a pack needs at least {MIN_BARS} dates"
            raise ValueError(msg)
        for symbol, series in self.series.items():
            if len(series.bars) != len(self.dates) or series.symbol != symbol:
                msg = f"series {symbol!r} must hold one bar per pack date"
                raise ValueError(msg)
        for origin, symbols in self.origins.items():
            missing = [symbol for symbol in symbols if symbol not in self.series]
            if not symbols or missing:
                msg = f"origin {origin!r} needs symbols from the pack, missing {missing}"
                raise ValueError(msg)

    @property
    def symbols(self) -> tuple[str, ...]:
        """Return every symbol in the pack, sorted."""
        return tuple(sorted(self.series))

    def symbols_for(self, origin: str) -> tuple[str, ...]:
        """Return the symbols that stand for ``origin``, or every symbol when it is unmapped."""
        return self.origins.get(origin) or self.symbols

    def window(self, start: int, length: int) -> Slice:
        """Return the slice of ``length`` bars starting at bar ``start``.

        Raises:
            ValueError: If the window does not fit in the pack.
        """
        if length < MIN_BARS or start < 0 or start + length > len(self.dates):
            msg = f"a window of {length} bars at {start} does not fit {len(self.dates)} dates"
            raise ValueError(msg)
        bars = {
            symbol: series.bars[start : start + length] for symbol, series in self.series.items()
        }
        return Slice(start, self.dates[start : start + length], bars)

    def deal(self, rng: Random, length: int, avoid: int | None = None) -> Slice:
        """Deal a random slice of ``length`` bars, never the window that starts at ``avoid``.

        Passing the previous round's start as ``avoid`` keeps two rounds in a row
        from being fought on the same days, when the pack has more than one window.
        """
        starts = [start for start in range(len(self.dates) - length + 1) if start != avoid]
        if not starts:
            return self.window(0, length)
        return self.window(rng.choice(starts), length)

    def to_json(self) -> dict[str, Any]:
        """Return the pack as plain JSON data."""
        return {
            "format": FORMAT_VERSION,
            "name": self.name,
            "interval": self.interval,
            "source": self.source,
            "dates": list(self.dates),
            "origins": {origin: list(symbols) for origin, symbols in self.origins.items()},
            "series": {
                symbol: [bar.to_json() for bar in series.bars]
                for symbol, series in sorted(self.series.items())
            },
        }

    @classmethod
    def from_json(cls, data: object) -> MarketPack:
        """Rebuild a pack from JSON data.

        Raises:
            ValueError: If the data is not a pack of a known format.
        """
        if not isinstance(data, dict) or data.get("format") != FORMAT_VERSION:
            msg = f"not a market pack of format {FORMAT_VERSION}"
            raise ValueError(msg)
        try:
            series = {
                str(symbol): Series(str(symbol), tuple(Bar.from_json(item) for item in bars))
                for symbol, bars in data["series"].items()
            }
            origins = {
                str(origin): tuple(str(s) for s in symbols)
                for origin, symbols in data["origins"].items()
            }
            return cls(
                str(data["name"]),
                str(data["interval"]),
                str(data.get("source", "")),
                tuple(str(date) for date in data["dates"]),
                origins,
                series,
            )
        except (KeyError, TypeError, AttributeError) as error:
            msg = f"market pack data is incomplete: {error}"
            raise ValueError(msg) from error

    def save(self, path: Path) -> None:
        """Write the pack as JSON, gzip-compressed when the name ends in ``.gz``."""
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_json(), separators=(",", ":"))
        if path.suffix == ".gz":
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                _ = handle.write(text)
        else:
            _ = path.write_text(text + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> MarketPack:
        """Read a pack written by :meth:`save`."""
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                return cls.from_json(json.load(handle))
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))


def load_builtin(name: str = "starter") -> MarketPack:
    """Load a pack that ships inside the package.

    Raises:
        ValueError: If no built-in pack has that name.
    """
    resource = files("tft").joinpath(f"packs/{name}.json")
    if not resource.is_file():
        msg = f"no built-in market pack named {name!r}"
        raise ValueError(msg)
    return MarketPack.from_json(json.loads(resource.read_text(encoding="utf-8")))


# Builders: Yahoo Finance responses to dated bars -----------------------------


Dated = tuple[str, Bar]
"""A bar and the local trading date it belongs to."""


def local_date(timestamp: int, gmtoffset: int) -> str:
    """Return the exchange-local date of a Unix ``timestamp`` given the exchange's UTC offset."""
    return datetime.fromtimestamp(timestamp + gmtoffset, UTC).date().isoformat()


def chart_bars(data: Mapping[str, Any]) -> tuple[str, list[Dated]]:
    """Read a Yahoo *chart* response into dated bars; intraday bars are grouped into daily bars.

    Raises:
        ValueError: If the response holds no usable result.
    """
    try:
        result = data["chart"]["result"][0]
        meta = result["meta"]
        quote = result["indicators"]["quote"][0]
        timestamps = result["timestamp"]
    except (KeyError, IndexError, TypeError) as error:
        msg = f"not a Yahoo chart response: {error}"
        raise ValueError(msg) from error
    symbol = str(meta["symbol"])
    offset = int(meta.get("gmtoffset", 0))
    raw = zip(
        timestamps,
        quote["open"],
        quote["high"],
        quote["low"],
        quote["close"],
        quote["volume"],
        strict=True,
    )
    dated = [
        (
            local_date(int(ts), offset),
            Bar(float(op), float(hi), float(lo), float(cl), float(vol or 0)),
        )
        for ts, op, hi, lo, cl, vol in raw
        if None not in (op, hi, lo, cl)
    ]
    if not dated:
        msg = f"chart for {symbol} holds no complete bars"
        raise ValueError(msg)
    return symbol, aggregate_daily(dated)


def aggregate_daily(dated: Sequence[Dated]) -> list[Dated]:
    """Merge the bars of each date into one daily bar: first open, max high, min low, last close."""
    merged: dict[str, Bar] = {}
    for date, bar in dated:
        previous = merged.get(date)
        if previous is None:
            merged[date] = bar
            continue
        merged[date] = Bar(
            previous.open,
            max(previous.high, bar.high),
            min(previous.low, bar.low),
            bar.close,
            previous.volume + bar.volume,
        )
    return sorted(merged.items())


def spark_bars(data: Mapping[str, Any]) -> list[tuple[str, list[Dated]]]:
    """Read a Yahoo *spark* response (daily closes for several symbols) into dated bars.

    Raises:
        ValueError: If the response holds no usable result.
    """
    try:
        results = data["spark"]["result"]
    except (KeyError, TypeError) as error:
        msg = f"not a Yahoo spark response: {error}"
        raise ValueError(msg) from error
    pieces: list[tuple[str, list[Dated]]] = []
    for entry in results:
        response = entry["response"][0]
        offset = int(response["meta"].get("gmtoffset", 0))
        closes = response["indicators"]["quote"][0]["close"]
        timestamps = response["timestamp"]
        dated = [
            (local_date(int(ts), offset), Bar.from_close(float(close)))
            for ts, close in zip(timestamps, closes, strict=True)
            if close is not None
        ]
        if dated:
            pieces.append((str(entry["symbol"]), aggregate_daily(dated)))
    if not pieces:
        msg = "spark response holds no complete series"
        raise ValueError(msg)
    return pieces


def assemble(
    name: str,
    pieces: Iterable[tuple[str, Sequence[Dated]]],
    origins: Mapping[str, Sequence[str]],
    *,
    interval: str = "1d",
    source: str = "",
) -> MarketPack:
    """Align dated series on their common dates and build a pack.

    Symbols that appear more than once keep the richer series (the one with real
    highs and lows, else the longer one). Origins that name symbols outside the
    pack are trimmed to the symbols present.

    Raises:
        ValueError: If no dates are common to every series.
    """
    chosen: dict[str, dict[str, Bar]] = {}
    for symbol, dated in pieces:
        candidate = dict(dated)
        current = chosen.get(symbol)
        if current is None or richness(candidate) > richness(current):
            chosen[symbol] = candidate
    common = sorted(set.intersection(*(set(bars) for bars in chosen.values()))) if chosen else []
    if len(common) < MIN_BARS:
        msg = f"the series share only {len(common)} dates; a pack needs at least {MIN_BARS}"
        raise ValueError(msg)
    series = {
        symbol: Series(symbol, tuple(bars[date] for date in common))
        for symbol, bars in chosen.items()
    }
    trimmed = {
        origin: tuple(symbol for symbol in symbols if symbol in series)
        for origin, symbols in origins.items()
    }
    kept = {origin: symbols for origin, symbols in trimmed.items() if symbols}
    return MarketPack(name, interval, source, tuple(common), kept, series)


def richness(bars: Mapping[str, Bar]) -> tuple[int, int]:
    """Rank a series: real highs and lows first, then length."""
    ranged = sum(1 for bar in bars.values() if bar.high != bar.low)
    return (ranged, len(bars))
