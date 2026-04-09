from __future__ import annotations

"""Stock ranking views for dashboard categories."""

from typing import Dict

import pandas as pd

from bluechip.detector import BlueChipDetector


def build_ranked_views(bluechip_df: pd.DataFrame, signal_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Build categorized ranking tables.

    Args:
        bluechip_df: Blue-chip scored DataFrame.
        signal_df: Technical signal DataFrame.

    Returns:
        Mapping of category name to ranked DataFrame.
    """
    if bluechip_df.empty:
        return {
            "top_bluechips": pd.DataFrame(),
            "best_buy_signals": pd.DataFrame(),
            "strong_momentum": pd.DataFrame(),
            "high_risk_weak": pd.DataFrame(),
        }

    if signal_df.empty or "symbol" not in signal_df.columns:
        return {
            "top_bluechips": bluechip_df.sort_values("bluechip_score", ascending=False).head(20),
            "best_buy_signals": pd.DataFrame(),
            "strong_momentum": pd.DataFrame(),
            "high_risk_weak": pd.DataFrame(),
        }

    merged = BlueChipDetector.merge_bluechip_scores(signal_df, bluechip_df)

    top_bluechips = bluechip_df.sort_values("bluechip_score", ascending=False).head(20)
    if not top_bluechips.empty:
        top_bluechips = top_bluechips.copy()
        top_bluechips["bluechip_rank"] = top_bluechips["bluechip_score"].rank(method="dense", ascending=False).astype(int)
        top_bluechips["bluechip_percentile"] = top_bluechips["bluechip_score"].rank(pct=True).round(4)
        if "volatility" in top_bluechips.columns:
            top_bluechips["volatility_rank"] = top_bluechips["volatility"].rank(method="dense", ascending=True).astype(int)
        if "cagr" in top_bluechips.columns:
            top_bluechips["cagr_rank"] = top_bluechips["cagr"].rank(method="dense", ascending=False).astype(int)

        max_bluechip_score = float(top_bluechips["bluechip_score"].max())
        top_bluechips["score_gap_from_top"] = (max_bluechip_score - top_bluechips["bluechip_score"]).round(4)

    best_buy_signals = merged[merged["signal"] == "BUY"].sort_values(
        ["confidence", "bluechip_score"], ascending=False
    )
    strong_momentum = merged[
        (merged["macd"] > merged["macd_signal"])
        & (merged["rsi14"].between(50, 70, inclusive="both"))
        & (merged["close"] > merged["sma200"])
    ].sort_values(["bluechip_score", "confidence"], ascending=False)

    weak_threshold = bluechip_df["bluechip_score"].quantile(0.25)
    vol_threshold = bluechip_df["volatility"].quantile(0.75)
    high_risk_weak = merged[
        (merged["bluechip_score"] <= weak_threshold)
        | (merged["volatility"] >= vol_threshold)
        | (merged["signal"] == "SELL")
    ].sort_values(["bluechip_score", "volatility"], ascending=[True, False])

    return {
        "top_bluechips": top_bluechips,
        "best_buy_signals": best_buy_signals,
        "strong_momentum": strong_momentum,
        "high_risk_weak": high_risk_weak,
    }

