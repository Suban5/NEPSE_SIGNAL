"""Tests for opportunity ranking."""

from __future__ import annotations

import pandas as pd

from ranking.opportunity_ranker import rank_opportunities


def test_rank_opportunities_orders_by_trade_score() -> None:
    df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "confidence": [0.9, 0.5],
            "close": [110.0, 90.0],
            "sma50": [100.0, 95.0],
            "macd": [1.2, -0.2],
            "macd_signal": [0.8, 0.1],
            "volume_trend": [1.5, 0.8],
            "bullish_engulfing": [True, False],
            "hammer": [False, False],
            "morning_star": [False, False],
        }
    )

    ranked = rank_opportunities(df)
    assert "trade_score" in ranked.columns
    assert "trade_score_breakdown" in ranked.columns
    assert "ranking_rationale" in ranked.columns
    assert "trade_score_rank" in ranked.columns
    assert "confidence_rank" in ranked.columns
    assert "relative_trade_score" in ranked.columns
    assert ranked.iloc[0]["symbol"] == "AAA"
    assert ranked.iloc[0]["trade_score_rank"] == 1
    assert ranked.iloc[0]["relative_trade_score"] <= 1.0
    assert isinstance(ranked.iloc[0]["trade_score_breakdown"], dict)
    assert "signal_strength" in ranked.iloc[0]["trade_score_breakdown"]
    assert "trade_score=" in ranked.iloc[0]["ranking_rationale"]
