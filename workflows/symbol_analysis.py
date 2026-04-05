"""Single-symbol analysis workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional

import pandas as pd

from analysis.signal_engine import SignalResult
from backtesting.backtest_engine import BacktestResult, run_backtest
from bluechip.detector import BlueChipDetector
from nepse_api.data_fetcher import NepseDataFetcher

from .common import (
    build_fundamentals_map,
    build_historical_signal_frame,
    build_technical_frame,
    detect_market_patterns,
    fetch_market_snapshot,
)
from .context import SymbolAnalysisContext, validate_symbol


@dataclass(frozen=True)
class SymbolAnalysisDependencies:
    """Dependencies required to execute a single-symbol analysis workflow."""

    fetcher: NepseDataFetcher
    detector: BlueChipDetector
    detect_patterns_fn: Callable[[pd.DataFrame], List[Any]]
    build_trade_signal_fn: Callable[[str, pd.DataFrame, List[Any], float], Any]
    add_indicators_fn: Callable[[pd.DataFrame], pd.DataFrame]


def run_symbol_analysis_workflow(
    dependencies: SymbolAnalysisDependencies,
    symbol: Optional[str],
    start_date: Optional[pd.Timestamp | str],
    end_date: Optional[pd.Timestamp | str],
) -> SymbolAnalysisContext:
    """Execute a single-symbol analysis workflow and return the produced context."""
    normalized_symbol = validate_symbol(symbol)
    history = dependencies.fetcher.fetch_historical_ohlcv(
        normalized_symbol,
        start_date=pd.to_datetime(start_date).date() if start_date is not None else None,
        end_date=pd.to_datetime(end_date).date() if end_date is not None else None,
    )
    if history.empty:
        raise RuntimeError(f"No historical OHLCV found for {normalized_symbol}")

    snapshot = fetch_market_snapshot(dependencies.fetcher)
    fundamentals_map = build_fundamentals_map(dependencies.fetcher, [normalized_symbol])
    feature_df = dependencies.detector.build_feature_table(
        snapshot,
        {normalized_symbol: history},
        fundamentals=fundamentals_map,
    )
    scored = dependencies.detector.score_bluechips(feature_df)
    bluechip_score = float(scored["bluechip_score"].iloc[0]) if not scored.empty else 0.0

    technical_df = dependencies.add_indicators_fn(history)
    pattern_map = detect_market_patterns(technical_df)
    pattern_results = dependencies.detect_patterns_fn(technical_df)
    signal = dependencies.build_trade_signal_fn(normalized_symbol, technical_df, pattern_results, bluechip_score)

    signal_df = build_historical_signal_frame(normalized_symbol, technical_df, bluechip_score, dependencies.detect_patterns_fn, dependencies.build_trade_signal_fn)
    backtest: BacktestResult = run_backtest(signal_df, signal_column="signal")

    return SymbolAnalysisContext(
        symbol=normalized_symbol,
        history=history,
        snapshot=snapshot,
        feature_df=feature_df,
        bluechip_score=bluechip_score,
        technical_df=technical_df,
        signal=signal,
        backtest=backtest,
    )
