"""Tests for technical indicators."""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.indicators import add_indicators


def _sample_ohlcv(rows: int = 240) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = np.linspace(100, 200, rows)
    data = pd.DataFrame(
        {
            "date": dates,
            "open": close - 1,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.linspace(1000, 3000, rows),
        }
    )
    return data


def test_add_indicators_returns_expected_columns() -> None:
    df = _sample_ohlcv()
    result = add_indicators(df)
    expected_columns = {
        "sma20",
        "sma50",
        "sma200",
        "ema20",
        "rsi14",
        "macd",
        "macd_signal",
        "bb_upper",
        "bb_lower",
        "volume_trend",
    }
    assert expected_columns.issubset(set(result.columns))


def test_add_indicators_rejects_missing_columns() -> None:
    bad_df = pd.DataFrame({"date": ["2024-01-01"], "close": [100]})
    try:
        add_indicators(bad_df)
    except ValueError as exc:
        assert "Missing required OHLCV columns" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing OHLCV columns")
