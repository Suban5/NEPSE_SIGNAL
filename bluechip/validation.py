"""Blue-chip scoring validation and comparison helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from backtesting.backtest_engine import PortfolioBacktestResult, run_portfolio_backtest


@dataclass(frozen=True)
class BlueChipValidationReport:
    """Validation report for blue-chip scoring."""

    top_n: int
    feature_importance: Dict[str, float]
    top_symbols: List[str]
    score_breakdown: List[Dict[str, Any]]
    sector_summary: List[Dict[str, Any]]
    portfolio_backtest: Optional[PortfolioBacktestResult] = None
    benchmark_backtest: Optional[PortfolioBacktestResult] = None


def build_bluechip_validation_report(
    bluechip_df: pd.DataFrame,
    historical_universe: Optional[Dict[str, pd.DataFrame]] = None,
    top_n: int = 10,
) -> BlueChipValidationReport:
    """Build a validation report for the blue-chip ranking output."""
    if bluechip_df.empty:
        return BlueChipValidationReport(
            top_n=top_n,
            feature_importance={},
            top_symbols=[],
            score_breakdown=[],
            sector_summary=[],
        )

    top_frame = bluechip_df.head(top_n)
    feature_importance = {}
    if "score_breakdown" in bluechip_df.columns and not bluechip_df.empty:
        sample_breakdown = bluechip_df.iloc[0]["score_breakdown"]
        if isinstance(sample_breakdown, dict):
            feature_importance = {key: float(value) for key, value in sample_breakdown.items()}

    portfolio_backtest = None
    benchmark_backtest = None
    if historical_universe:
        selected_symbols = top_frame["symbol"].tolist()
        portfolio_backtest = run_portfolio_backtest(historical_universe, selected_symbols, lookback_days=252)
        benchmark_backtest = run_portfolio_backtest(
            historical_universe,
            list(historical_universe.keys()),
            lookback_days=252,
        )

    sector_summary = (
        bluechip_df.groupby("sector", dropna=False)["bluechip_score"].agg(["mean", "max", "count"]).reset_index().to_dict(orient="records")
        if "sector" in bluechip_df.columns
        else []
    )

    return BlueChipValidationReport(
        top_n=top_n,
        feature_importance=feature_importance,
        top_symbols=top_frame["symbol"].tolist(),
        score_breakdown=top_frame[[col for col in ["symbol", "sector", "bluechip_score", "base_bluechip_score", "rank"] if col in top_frame.columns]].to_dict(orient="records"),
        sector_summary=sector_summary,
        portfolio_backtest=portfolio_backtest,
        benchmark_backtest=benchmark_backtest,
    )