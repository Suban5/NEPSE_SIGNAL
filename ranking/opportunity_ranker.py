"""Opportunity ranking module."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def _build_trade_score_breakdown(row: pd.Series) -> Dict[str, float]:
    """Build weighted trade-score breakdown for explainability."""
    signal_strength = float(row.get("signal_strength", 0.0))
    trend_strength = float(row.get("trend_strength", 0.0))
    volume_momentum = float(row.get("volume_momentum", 0.0))
    pattern_confidence = float(row.get("pattern_confidence", 0.0))

    return {
        "signal_strength": round(0.4 * signal_strength, 4),
        "trend_strength": round(0.3 * trend_strength, 4),
        "volume_momentum": round(0.2 * volume_momentum, 4),
        "pattern_confidence": round(0.1 * pattern_confidence, 4),
    }


def _build_ranking_rationale(row: pd.Series) -> str:
    """Build concise text rationale for ranked opportunity rows."""
    components = [
        f"trade_score={float(row.get('trade_score', 0.0)):.3f}",
        f"signal={str(row.get('signal', 'N/A'))}",
        f"confidence={float(row.get('confidence', 0.0)):.3f}",
        f"signal_strength={float(row.get('signal_strength', 0.0)):.3f}",
        f"trend_strength={float(row.get('trend_strength', 0.0)):.3f}",
        f"volume_momentum={float(row.get('volume_momentum', 0.0)):.3f}",
        f"pattern_confidence={float(row.get('pattern_confidence', 0.0)):.3f}",
    ]
    return ", ".join(components)


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

    out = out.sort_values(["trade_score", "confidence"], ascending=False).reset_index(drop=True)

    out["trade_score_breakdown"] = out.apply(_build_trade_score_breakdown, axis=1)
    out["trade_score_rank"] = out["trade_score"].rank(method="dense", ascending=False).astype(int)
    out["confidence_rank"] = out["confidence"].rank(method="dense", ascending=False).astype(int)
    if "bluechip_score" in out.columns:
        out["bluechip_rank"] = out["bluechip_score"].rank(method="dense", ascending=False).astype(int)

    max_trade_score = float(out["trade_score"].max()) if not out.empty else 0.0
    if max_trade_score > 0.0:
        out["relative_trade_score"] = (out["trade_score"] / max_trade_score).round(4)
    else:
        out["relative_trade_score"] = 0.0

    out["ranking_rationale"] = out.apply(_build_ranking_rationale, axis=1)

    return out
