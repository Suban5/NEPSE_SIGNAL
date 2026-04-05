"""Opportunity ranking module."""

from __future__ import annotations

import pandas as pd


def rank_opportunities(signal_df: pd.DataFrame) -> pd.DataFrame:
    """Rank trading opportunities using weighted trade score.

    TradeScore =
        0.4 * SignalStrength +
        0.3 * TrendStrength +
        0.2 * VolumeMomentum +
        0.1 * PatternConfidence
    """
    if signal_df.empty:
        return signal_df

    out = signal_df.copy()
    out["signal_strength"] = out["confidence"].clip(lower=0, upper=1)
    out["trend_strength"] = (out["close"] > out["sma50"]).astype(float) * 0.5 + (
        out["macd"] > out["macd_signal"]
    ).astype(float) * 0.5
    out["volume_momentum"] = out["volume_trend"].fillna(0).clip(lower=0, upper=2) / 2

    bullish_patterns = ["bullish_engulfing", "hammer", "morning_star"]
    existing_patterns = [col for col in bullish_patterns if col in out.columns]
    if existing_patterns:
        out["pattern_confidence"] = out[existing_patterns].astype(float).mean(axis=1)
    else:
        out["pattern_confidence"] = 0.0

    out["trade_score"] = (
        0.4 * out["signal_strength"]
        + 0.3 * out["trend_strength"]
        + 0.2 * out["volume_momentum"]
        + 0.1 * out["pattern_confidence"]
    )

    return out.sort_values(["trade_score", "confidence"], ascending=False).reset_index(drop=True)
