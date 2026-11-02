"""Tests for tools/build_market_pack.py (importable through pytest's ``pythonpath``)."""

from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import build_market_pack as tool
from tft.market import MarketPack

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "market"


def test_build_from_the_fixture_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "pack.json.gz"
    assert tool.main(["--from-dir", str(FIXTURES), "--name", "fixture", "--out", str(out)]) == 0
    pack = MarketPack.load(out)
    assert pack.name == "fixture"
    assert len(pack.symbols) == 29
    assert "TSLA" in pack.origins["Tech"]
    text = capsys.readouterr().out
    assert "29 symbols" in text
    assert "origins:" in text


def test_pieces_from_data_rejects_unknown_shapes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a Yahoo chart or spark"):
        tool.pieces_from_data({"nope": 1}, "x")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match=r"no \.json"):
        tool.pieces_from_dir(empty)
    assert (
        tool.main(["--from-dir", str(empty), "--name", "x", "--out", str(tmp_path / "o.json")]) == 1
    )


def test_load_origins(tmp_path: Path) -> None:
    assert tool.load_origins(None) == tool.STARTER_ORIGINS
    path = tmp_path / "origins.json"
    path.write_text('{"Equities": ["KO"]}', encoding="utf-8")
    assert tool.load_origins(path) == {"Equities": ("KO",)}
    path.write_text('{"Equities": "KO"}', encoding="utf-8")
    with pytest.raises(ValueError, match="must map"):
        tool.load_origins(path)


def test_fetch_path_with_a_fake_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = json.loads((FIXTURES / "spark-3mo-a.json").read_text())
    entry = sample["spark"]["result"][0]
    response = entry["response"][0]
    chart = {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "AMZN", "gmtoffset": -14400},
                    "timestamp": response["timestamp"],
                    "indicators": {
                        "quote": [
                            {
                                "open": response["indicators"]["quote"][0]["close"],
                                "high": response["indicators"]["quote"][0]["close"],
                                "low": response["indicators"]["quote"][0]["close"],
                                "close": response["indicators"]["quote"][0]["close"],
                                "volume": [1] * len(response["timestamp"]),
                            }
                        ]
                    },
                }
            ]
        }
    }
    seen: list[str] = []

    class FakeResponse(io.BytesIO):
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        seen.append(request.full_url)
        assert timeout > 0
        return FakeResponse(json.dumps(chart).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = tmp_path / "live.json"
    args = ["--fetch", "AMZN, AMZN", "--range", "1mo", "--name", "live", "--out", str(out)]
    assert tool.main(args) == 0
    assert (
        seen == ["https://query1.finance.yahoo.com/v8/finance/chart/AMZN?range=1mo&interval=1d"] * 2
    )
    pack = MarketPack.load(out)
    assert pack.symbols == ("AMZN",)
    assert pack.origins == {"Tech": ("AMZN",)}
