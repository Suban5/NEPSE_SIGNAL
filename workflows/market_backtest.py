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
    log_workflow_event,
    new_execution_id,
    rank_signal_frame,
)
from .errors import WorkflowDataError, WorkflowRankingError, classify_workflow_exception
from .context import MarketBacktestContext, validate_positive_int, validate_rebalance_mode


@dataclass(frozen=True)
class MarketBacktestDependencies:
    """Dependencies required to execute the market backtest workflow."""

    coordinator: Any
    scanner: MarketScanner
    detector: BlueChipDetector
    add_indicators_fn: Callable[[pd.DataFrame], pd.DataFrame]
    detect_patterns_fn: Callable[[pd.DataFrame], List[Any]]
    build_trade_signal_fn: Callable[[str, pd.DataFrame, List[Any], float], Any]
    rank_opportunities_fn: Callable[[pd.DataFrame], pd.DataFrame]


def _build_historical_validation(
    filtered_history: dict[str, pd.DataFrame],
    selected_symbols: list[str],
    lookback_days: int,
) -> dict[str, Any]:
    """Validate selected symbols have sufficient historical rows for backtesting."""
    sufficient_symbols: list[str] = []
    insufficient_symbols: list[str] = []
    missing_symbols: list[str] = []
    row_counts: dict[str, int] = {}

    for symbol in selected_symbols:
        history = filtered_history.get(symbol)
        if history is None:
            missing_symbols.append(symbol)
            row_counts[symbol] = 0
            continue

        required_columns = {"date", "close"}
        if not required_columns.issubset(set(history.columns)):
            insufficient_symbols.append(symbol)
            row_counts[symbol] = 0
            continue

        validated_history = history[["date", "close"]].copy()
        validated_history["date"] = pd.to_datetime(validated_history["date"], errors="coerce")
        validated_history["close"] = pd.to_numeric(validated_history["close"], errors="coerce")
        validated_history = validated_history.dropna(subset=["date", "close"]).tail(lookback_days)

        row_count = int(len(validated_history))
        row_counts[symbol] = row_count
        if row_count >= 2:
            sufficient_symbols.append(symbol)
        else:
            insufficient_symbols.append(symbol)

    return {
        "validated_symbols": int(len(selected_symbols)),
        "sufficient_symbols": int(len(sufficient_symbols)),
        "insufficient_symbols": int(len(insufficient_symbols)),
        "required_lookback_days": int(lookback_days),
        "sufficient_history_symbols": sufficient_symbols,
        "insufficient_history_symbols": insufficient_symbols,
        "missing_history_symbols": missing_symbols,
        "symbol_row_counts": row_counts,
    }


def run_market_backtest_workflow(
    dependencies: MarketBacktestDependencies,
    output_dir: Path,
    top_n: int,
    lookback_days: int,
    rebalance: str,
    force_refresh: bool = False,
) -> MarketBacktestContext:
    """Execute the portfolio backtest workflow and return the produced context.
    
    Args:
        dependencies: Workflow dependencies.
        output_dir: Output directory path.
        top_n: Number of top stocks to analyze.
        lookback_days: Number of days to backtest.
        rebalance: Rebalancing strategy.
        force_refresh: If True, bypass cache and fetch fresh data from API.
    """
    started_at = time.perf_counter()
    normalized_top_n = validate_positive_int(top_n, "top_n")
    normalized_lookback_days = validate_positive_int(lookback_days, "lookback_days")
    normalized_rebalance = validate_rebalance_mode(rebalance)
    execution_id = new_execution_id("market-backtest")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_workflow_event(
        workflow="market_backtest",
        execution_id=execution_id,
        event="workflow_started",
        top_n=normalized_top_n,
        lookback_days=normalized_lookback_days,
        rebalance=normalized_rebalance,
        force_refresh=bool(force_refresh),
        output_dir=str(output_dir),
    )

    fetch_started = time.perf_counter()
    snapshot = fetch_market_snapshot(
        dependencies.coordinator,
        force_refresh=force_refresh,
        execution_id=execution_id,
        workflow_name="market_backtest",
    )
    historical_universe = fetch_historical_universe(
        dependencies.coordinator,
        lookback_years=5,
        force_refresh=force_refresh,
        execution_id=execution_id,
        workflow_name="market_backtest",
    )
    try:
        symbols, filtered_history = dependencies.scanner.scan(snapshot=snapshot, historical_universe=historical_universe)
    except Exception as exc:
        raise classify_workflow_exception("market_backtest", "scan", exc) from exc
    fetch_elapsed = time.perf_counter() - fetch_started
    if not symbols:
        raise WorkflowDataError("market_backtest", "scan", "No symbols passed market universe filters.")

    score_started = time.perf_counter()
    try:
        fundamentals_map = build_fundamentals_map(dependencies.coordinator, symbols)
        features = dependencies.detector.build_feature_table(snapshot, filtered_history, fundamentals=fundamentals_map)
        bluechip_ranked = dependencies.detector.score_bluechips(features)
    except Exception as exc:
        raise classify_workflow_exception("market_backtest", "score", exc) from exc
    score_elapsed = time.perf_counter() - score_started
    if bluechip_ranked.empty:
        raise WorkflowRankingError("market_backtest", "score", "No stocks qualified for blue-chip scoring.")

    selected_symbols: List[str] = dependencies.detector.select_top_symbols(bluechip_ranked, normalized_top_n)
    signal_started = time.perf_counter()
    try:
        signal_rows = compute_symbol_signal_rows(
            symbols=selected_symbols,
            filtered_history=filtered_history,
            bluechip_ranked=bluechip_ranked,
            add_indicators_fn=dependencies.add_indicators_fn,
            detect_patterns_fn=dependencies.detect_patterns_fn,
            build_trade_signal_fn=dependencies.build_trade_signal_fn,
        )
    except Exception as exc:
        raise classify_workflow_exception("market_backtest", "signal", exc) from exc
    signal_elapsed = time.perf_counter() - signal_started

    rank_started = time.perf_counter()
    try:
        signal_df = dependencies.rank_opportunities_fn(pd.DataFrame(signal_rows))
    except Exception as exc:
        raise classify_workflow_exception("market_backtest", "rank", exc) from exc
    buy_symbols = signal_df.loc[signal_df["signal"] == "BUY", "symbol"].tolist() if not signal_df.empty else []
    rank_elapsed = time.perf_counter() - rank_started

    historical_validation = _build_historical_validation(
        filtered_history=filtered_history,
        selected_symbols=buy_symbols,
        lookback_days=normalized_lookback_days,
    )
    backtested_symbols = historical_validation["sufficient_history_symbols"]
    if buy_symbols and not backtested_symbols:
        raise WorkflowDataError(
            "market_backtest",
            "backtest",
            "No BUY symbols have sufficient historical rows for backtest window.",
        )

    backtest_started = time.perf_counter()
    try:
        portfolio_result: PortfolioBacktestResult = run_portfolio_backtest(
            historical_universe=filtered_history,
            selected_symbols=backtested_symbols,
            lookback_days=normalized_lookback_days,
            rebalance=normalized_rebalance,
        )
    except Exception as exc:
        raise classify_workflow_exception("market_backtest", "backtest", exc) from exc
    backtest_elapsed = time.perf_counter() - backtest_started

    metrics = {
        "symbols_count": portfolio_result.symbols_count,
        "selected_buy_symbols": buy_symbols,
        "backtested_symbols": backtested_symbols,
        "cagr": portfolio_result.cagr,
        "max_drawdown": portfolio_result.max_drawdown,
        "sharpe_ratio": portfolio_result.sharpe_ratio,
        "total_return": portfolio_result.total_return,
        "lookback_days": normalized_lookback_days,
        "rebalance": normalized_rebalance,
    }

    total_elapsed = time.perf_counter() - started_at
    context = MarketBacktestContext(
        output_dir=output_dir,
        top_n=normalized_top_n,
        lookback_days=normalized_lookback_days,
        rebalance=normalized_rebalance,
        execution_id=execution_id,
        snapshot=snapshot,
        historical_universe=historical_universe,
        symbols=symbols,
        filtered_history=filtered_history,
        bluechip_ranked=bluechip_ranked,
        signal_df=signal_df,
        selected_buy_symbols=buy_symbols,
        backtested_symbols=backtested_symbols,
        historical_validation=historical_validation,
        portfolio_metrics=metrics,
    )
    write_benchmark_snapshot(
        output_dir=output_dir,
        file_name="backtest_benchmark.json",
        payload={
            "execution_id": execution_id,
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
                "backtested_symbols": int(len(backtested_symbols)),
                "top_n": normalized_top_n,
                "lookback_days": normalized_lookback_days,
                "rebalance": normalized_rebalance,
            },
            "historical_validation": historical_validation,
            "summary": context.to_summary(),
        },
    )
    log_workflow_event(
        workflow="market_backtest",
        execution_id=execution_id,
        event="workflow_completed",
        total_seconds=round(total_elapsed, 6),
        symbols=int(len(symbols)),
        buy_symbols=int(len(buy_symbols)),
    )

    try:
        (output_dir / "portfolio_backtest.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        signal_df.to_csv(output_dir / "portfolio_signal_set.csv", index=False)
    except Exception as exc:
        raise classify_workflow_exception("market_backtest", "persist", exc) from exc

    return context
