"""Market backtest workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List

import json
import pandas as pd
import time

from backtesting.backtest_engine import PortfolioBacktestResult, run_portfolio_backtest
from bluechip.detector import BlueChipDetector
from market.market_scanner import MarketScanner

from .common import (
    build_fundamentals_map,
    compute_symbol_signal_rows,
    write_benchmark_snapshot,
    detect_market_patterns,
    fetch_historical_universe,
    fetch_market_snapshot,
    rank_signal_frame,
)
from .context import MarketBacktestContext


@dataclass(frozen=True)
class MarketBacktestDependencies:
    """Dependencies required to execute the market backtest workflow."""

    fetcher: Any
    scanner: MarketScanner
    detector: BlueChipDetector
    add_indicators_fn: Callable[[pd.DataFrame], pd.DataFrame]
    detect_patterns_fn: Callable[[pd.DataFrame], List[Any]]
    build_trade_signal_fn: Callable[[str, pd.DataFrame, List[Any], float], Any]
    rank_opportunities_fn: Callable[[pd.DataFrame], pd.DataFrame]


def run_market_backtest_workflow(
    dependencies: MarketBacktestDependencies,
    output_dir: Path,
    top_n: int,
    lookback_days: int,
    rebalance: str,
) -> MarketBacktestContext:
    """Execute the portfolio backtest workflow and return the produced context."""
    started_at = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    fetch_started = time.perf_counter()
    snapshot = fetch_market_snapshot(dependencies.fetcher)
    historical_universe = fetch_historical_universe(dependencies.fetcher, lookback_years=5)
    symbols, filtered_history = dependencies.scanner.scan(snapshot=snapshot, historical_universe=historical_universe)
    fetch_elapsed = time.perf_counter() - fetch_started
    if not symbols:
        raise RuntimeError("No symbols passed market universe filters.")

    score_started = time.perf_counter()
    fundamentals_map = build_fundamentals_map(dependencies.fetcher, symbols)
    features = dependencies.detector.build_feature_table(snapshot, filtered_history, fundamentals=fundamentals_map)
    bluechip_ranked = dependencies.detector.score_bluechips(features)
    score_elapsed = time.perf_counter() - score_started
    if bluechip_ranked.empty:
        raise RuntimeError("No stocks qualified for blue-chip scoring.")

    selected_symbols: List[str] = bluechip_ranked.head(top_n)["symbol"].tolist()
    signal_started = time.perf_counter()
    signal_rows = compute_symbol_signal_rows(
        symbols=selected_symbols,
        filtered_history=filtered_history,
        bluechip_ranked=bluechip_ranked,
        add_indicators_fn=dependencies.add_indicators_fn,
        detect_patterns_fn=dependencies.detect_patterns_fn,
        build_trade_signal_fn=dependencies.build_trade_signal_fn,
    )
    signal_elapsed = time.perf_counter() - signal_started

    rank_started = time.perf_counter()
    signal_df = dependencies.rank_opportunities_fn(pd.DataFrame(signal_rows))
    buy_symbols = signal_df.loc[signal_df["signal"] == "BUY", "symbol"].tolist() if not signal_df.empty else []
    rank_elapsed = time.perf_counter() - rank_started

    backtest_started = time.perf_counter()
    portfolio_result: PortfolioBacktestResult = run_portfolio_backtest(
        historical_universe=filtered_history,
        selected_symbols=buy_symbols,
        lookback_days=lookback_days,
        rebalance=rebalance,
    )
    backtest_elapsed = time.perf_counter() - backtest_started

    metrics = {
        "symbols_count": portfolio_result.symbols_count,
        "selected_buy_symbols": buy_symbols,
        "cagr": portfolio_result.cagr,
        "max_drawdown": portfolio_result.max_drawdown,
        "sharpe_ratio": portfolio_result.sharpe_ratio,
        "total_return": portfolio_result.total_return,
        "lookback_days": lookback_days,
        "rebalance": rebalance,
    }

    total_elapsed = time.perf_counter() - started_at
    write_benchmark_snapshot(
        output_dir=output_dir,
        file_name="backtest_benchmark.json",
        payload={
            "total_seconds": round(total_elapsed, 6),
            "timings": {
                "fetch_seconds": round(fetch_elapsed, 6),
                "score_seconds": round(score_elapsed, 6),
                "signal_seconds": round(signal_elapsed, 6),
                "rank_seconds": round(rank_elapsed, 6),
                "backtest_seconds": round(backtest_elapsed, 6),
            },
            "input": {
                "snapshot_rows": int(len(snapshot)),
                "universe_symbols": int(len(symbols)),
                "selected_symbols": int(len(selected_symbols)),
                "buy_symbols": int(len(buy_symbols)),
                "top_n": int(top_n),
                "lookback_days": int(lookback_days),
                "rebalance": rebalance,
            },
        },
    )

    (output_dir / "portfolio_backtest.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    signal_df.to_csv(output_dir / "portfolio_signal_set.csv", index=False)

    return MarketBacktestContext(
        output_dir=output_dir,
        top_n=top_n,
        lookback_days=lookback_days,
        rebalance=rebalance,
        snapshot=snapshot,
        historical_universe=historical_universe,
        symbols=symbols,
        filtered_history=filtered_history,
        bluechip_ranked=bluechip_ranked,
        signal_df=signal_df,
        selected_buy_symbols=buy_symbols,
    )
