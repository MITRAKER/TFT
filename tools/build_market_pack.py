#!/usr/bin/env python3
r"""Build a market pack from Yahoo Finance responses, saved on disk or fetched.

Offline, from saved *chart* and *spark* responses (the test fixtures are a
ready example)::

    python tools/build_market_pack.py --from-dir tests/fixtures/market --name starter \\
        --out src/tft/packs/starter.json

Online, fetching daily bars for a list of symbols (unofficial endpoint; be
polite and cache the result)::

    python tools/build_market_pack.py --fetch AAPL,KO,XOM --range 3mo --interval 1d \\
        --name live --out packs/live.json

Origins come from ``--origins FILE`` (a JSON object mapping each origin to a
list of symbols); without it the starter mapping below is used, trimmed to the
symbols that are present.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tft.market import Dated, MarketPack, assemble, chart_bars, spark_bars

CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range}&interval={interval}"
)
USER_AGENT = "Mozilla/5.0 (tft market pack builder)"
TIMEOUT_SECONDS = 30

STARTER_ORIGINS: dict[str, tuple[str, ...]] = {
    "Equities": ("KO", "BAC", "HD", "CCL", "RCL", "BRK-B"),
    "Tech": ("AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "AMZN", "TSLA"),
    "Crypto": ("AMC", "PLUG", "LCID", "RIVN", "PLTR", "SOFI"),
    "Commodities": ("XOM", "GE", "F"),
    "Bonds": ("CI", "PNC", "BLK"),
    "Forex": ("JPM", "MS"),
}
"""The starter pack's stand-ins: US stocks grouped by the market they play the part of."""


def read_json(path: Path) -> Any:  # noqa: ANN401 - raw JSON
    """Read a JSON file, gzip-compressed when the name ends in ``.gz``."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def pieces_from_data(data: Any, origin: str) -> list[tuple[str, list[Dated]]]:  # noqa: ANN401 - raw JSON
    """Turn one Yahoo response into dated series.

    Raises:
        ValueError: If the data is neither a chart nor a spark response.
    """
    if isinstance(data, dict) and "chart" in data:
        return [chart_bars(data)]
    if isinstance(data, dict) and "spark" in data:
        return spark_bars(data)
    msg = f"{origin}: not a Yahoo chart or spark response"
    raise ValueError(msg)


def pieces_from_dir(directory: Path) -> list[tuple[str, list[Dated]]]:
    """Read every ``.json`` and ``.json.gz`` file in ``directory``.

    Raises:
        ValueError: If the directory holds no response files.
    """
    files = sorted(p for p in directory.iterdir() if p.name.endswith((".json", ".json.gz")))
    if not files:
        msg = f"no .json or .json.gz files in {directory}"
        raise ValueError(msg)
    pieces: list[tuple[str, list[Dated]]] = []
    for file in files:
        pieces.extend(pieces_from_data(read_json(file), file.name))
    return pieces


def fetch_chart(symbol: str, range_: str, interval: str) -> Any:  # noqa: ANN401 - raw JSON
    """Fetch one symbol's chart from Yahoo Finance."""
    url = CHART_URL.format(symbol=symbol, range=range_, interval=interval)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 - https, fixed host
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 - https, fixed host
        return json.load(response)


def load_origins(path: Path | None) -> dict[str, tuple[str, ...]]:
    """Return the origin mapping from ``path``, or the starter mapping.

    Raises:
        ValueError: If the file is not an object of symbol lists.
    """
    if path is None:
        return dict(STARTER_ORIGINS)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(v, list) for v in data.values()):
        msg = f"{path} must map each origin to a list of symbols"
        raise ValueError(msg)
    return {str(origin): tuple(str(s) for s in symbols) for origin, symbols in data.items()}


def add_source_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the offline and online source options."""
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--from-dir", type=Path, help="directory of saved Yahoo chart/spark JSON files"
    )
    source.add_argument("--fetch", help="comma-separated symbols to fetch from Yahoo Finance")
    parser.add_argument("--range", default="3mo", help="Yahoo range for --fetch (default 3mo)")
    parser.add_argument("--interval", default="1d", help="Yahoo interval for --fetch (default 1d)")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(prog="build_market_pack", description=__doc__.split("\n\n")[0])
    add_source_arguments(parser)
    parser.add_argument("--origins", type=Path, help="JSON file mapping origins to symbol lists")
    parser.add_argument("--name", required=True, help="pack name")
    parser.add_argument("--out", type=Path, required=True, help="output file (.json or .json.gz)")
    return parser.parse_args(argv)


def build(args: argparse.Namespace) -> MarketPack:
    """Collect the series and assemble the pack.

    Raises:
        ValueError: If no symbol could be read.
    """
    if args.from_dir is not None:
        pieces = pieces_from_dir(args.from_dir)
        source = f"saved Yahoo responses in {args.from_dir}"
    else:
        symbols = [symbol.strip() for symbol in args.fetch.split(",") if symbol.strip()]
        pieces = [chart_bars(fetch_chart(symbol, args.range, args.interval)) for symbol in symbols]
        source = f"Yahoo Finance chart, range {args.range}, interval {args.interval}"
    if not pieces:
        msg = "no series to build from"
        raise ValueError(msg)
    return assemble(
        args.name, pieces, load_origins(args.origins), interval=args.interval, source=source
    )


def describe(pack: MarketPack, out: Path) -> str:
    """Return a two-line summary of what the pack holds."""
    origins = ", ".join(f"{origin} ({len(symbols)})" for origin, symbols in pack.origins.items())
    span = f"{len(pack.dates)} dates {pack.dates[0]} to {pack.dates[-1]}"
    return f"{out}: {len(pack.symbols)} symbols, {span}\norigins: {origins}"


def main(argv: Sequence[str] | None = None) -> int:
    """Build the pack and report what it holds."""
    args = parse_args(argv)
    try:
        pack = build(args)
        pack.save(args.out)  # noqa: JPL07 - acts by side effect
    except (ValueError, OSError) as error:
        print(f"build_market_pack: error: {error}", file=sys.stderr)
        return 1
    print(describe(pack, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
