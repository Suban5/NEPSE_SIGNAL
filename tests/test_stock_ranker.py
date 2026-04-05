"""Tests for stock ranking views."""

from __future__ import annotations

import pandas as pd

from ranking.stock_ranker import build_ranked_views


def test_build_ranked_views_handles_bluechip_score_column_collision() -> None:
    bluechip_df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "bluechip_score": [0.9, 0.6],
            "volatility": [0.2, 0.4],
            "cagr": [0.3, 0.1],
            "rank": [1, 2],
        }
    )

    signal_df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "signal": ["BUY", "SELL"],
            "confidence": [0.8, 0.5],
            "bluechip_score": [0.9, 0.6],
            "close": [120.0, 90.0],
            "sma50": [110.0, 95.0],
            "sma200": [100.0, 100.0],
            "macd": [1.2, -0.5],
            "macd_signal": [0.8, -0.1],
            "rsi14": [60.0, 45.0],
        }
    )

    views = build_ranked_views(bluechip_df, signal_df)

    assert "best_buy_signals" in views
    assert not views["best_buy_signals"].empty
    assert views["best_buy_signals"].iloc[0]["symbol"] == "AAA"
    assert "bluechip_score" in views["best_buy_signals"].columns
