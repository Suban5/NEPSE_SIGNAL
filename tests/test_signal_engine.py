"""Tests for signal generation and fundamentals normalization."""

from __future__ import annotations

import pandas as pd

from analysis.signal_engine import generate_signal
from nepse_api.data_fetcher import NepseDataFetcher


def _build_signal_df() -> pd.DataFrame:
    """Create a minimal frame that satisfies signal-engine requirements."""
    return pd.DataFrame(
        {
            "close": [100.0, 101.0],
            "sma20": [99.5, 99.8],
            "sma50": [101.2, 100.5],
            "sma200": [98.0, 98.2],
            "ema20": [99.7, 100.1],
            "rsi14": [42.0, 44.0],
            "macd": [0.2, 0.3],
            "macd_signal": [0.25, 0.28],
            "bb_upper": [103.0, 103.2],
            "bb_lower": [97.0, 97.1],
            "volume": [1000, 1300],
            "volume_sma20": [900, 950],
            "volume_trend": [1.1, 1.3],
        }
    )


def test_generate_signal_emits_buy_with_two_of_four_buy_conditions() -> None:
    """BUY should trigger when buy score reaches at least 0.5."""
    df = _build_signal_df()
    patterns = {
        "bullish_engulfing": False,
        "hammer": False,
        "morning_star": False,
        "bearish_engulfing": False,
        "shooting_star": False,
        "evening_star": False,
        "doji": False,
    }

    result = generate_signal("TEST", df, patterns, bluechip_score=0.7)

    assert result.signal == "BUY"
    assert result.confidence > 0.5


def test_normalize_fundamentals_supports_alias_fields() -> None:
    """Fundamentals normalization should map common alias field names."""
    payload = {
        "epsGrowth": 12.5,
        "salesGrowth": 9.0,
        "dividendYield": 4.0,
    }

    normalized = NepseDataFetcher.normalize_fundamentals(payload)

    assert normalized["earnings_growth"] == 12.5
    assert normalized["revenue_growth"] == 9.0
    assert normalized["dividend_stability"] == 4.0
