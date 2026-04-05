"""Tests for market scanner and universe filtering."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market.market_scanner import MarketScanner


def test_market_scanner_filters_universe() -> None:
    snapshot = pd.DataFrame(
        [
            {"symbol": "AAA", "market_cap": 1000},
            {"symbol": "BBB", "market_cap": 500},
        ]
    )
    historical = {
        "AAA": pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=200, freq="D"),
                "close": np.linspace(100, 120, 200),
                "volume": np.full(200, 3000),
            }
        ),
        "BBB": pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=100, freq="D"),
                "close": np.linspace(100, 105, 100),
                "volume": np.full(100, 200),
            }
        ),
    }

    scanner = MarketScanner()
    symbols, filtered = scanner.scan(snapshot, historical)
    assert symbols == ["AAA"]
    assert list(filtered.keys()) == ["AAA"]
