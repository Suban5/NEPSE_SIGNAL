"""Market scan workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List
import time

import pandas as pd

from bluechip.detector import BlueChipDetector
from market.market_scanner import MarketScanner

from .common import (
    build_ranked_views_cached,
    build_fundamentals_map,
    compute_symbol_signal_rows,
    fetch_historical_universe,
    fetch_market_snapshot,
    log_workflow_event,
    log_ranked_summary,
    new_execution_id,
    save_outputs,
    write_benchmark_snapshot,
    render_charts,
)
from .errors import WorkflowDataError, WorkflowRankingError, classify_workflow_exception
from .context import MarketScanContext


@dataclass(frozen=True)
class MarketScanDependencies:
    """Dependencies required to execute the market scan workflow."""

    coordinator: Any
    scanner: MarketScanner
    detector: BlueChipDetector
    add_indicators_fn: Callable[[pd.DataFrame], pd.DataFrame]
    detect_patterns_fn: Callable[[pd.DataFrame], List[Any]]
    build_trade_signal_fn: Callable[[str, pd.DataFrame, List[Any], float], Any]
    rank_opportunities_fn: Callable[[pd.DataFrame], pd.DataFrame]
    build_ranked_views_fn: Callable[[pd.DataFrame, pd.DataFrame], Dict[str, pd.DataFrame]]


def run_market_scan_workflow(
    dependencies: MarketScanDependencies,
    output_dir: Path,
    top_n: int,
    plot: bool,
    save_chart_fn: Callable[[pd.DataFrame, str, str], None] = render_charts,
    force_refresh: bool = False,
) -> MarketScanContext:
    """Execute the full market scan workflow and return the produced context.
    
    Args:
        dependencies: Workflow dependencies.
        output_dir: Output directory path.
        top_n: Number of top stocks to analyze.
        plot: Whether to generate charts.
        save_chart_fn: Function to save charts.
        force_refresh: If True, bypass cache and fetch fresh data from API.
    """
    started_at = time.perf_counter()
    execution_id = new_execution_id("market-scan")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_workflow_event(
        workflow="market_scan",
        execution_id=execution_id,
        event="workflow_started",
        top_n=int(top_n),
        plot=bool(plot),
        force_refresh=bool(force_refresh),
        output_dir=str(output_dir),
    )

    fetch_started = time.perf_counter()
    snapshot = fetch_market_snapshot(
        dependencies.coordinator,
        force_refresh=force_refresh,
        execution_id=execution_id,
        workflow_name="market_scan",
    )
    historical_universe = fetch_historical_universe(
        dependencies.coordinator,
        lookback_years=5,
        force_refresh=force_refresh,
        execution_id=execution_id,
        workflow_name="market_scan",
    )
    try:
        symbols, filtered_history = dependencies.scanner.scan(snapshot=snapshot, historical_universe=historical_universe)
    except Exception as exc:
        raise classify_workflow_exception("market_scan", "scan", exc) from exc
    fetch_elapsed = time.perf_counter() - fetch_started
    if not symbols:
        raise WorkflowDataError("market_scan", "scan", "No symbols passed market universe filters.")

    score_started = time.perf_counter()
    try:
        fundamentals_map = build_fundamentals_map(dependencies.coordinator, symbols)
        features = dependencies.detector.build_feature_table(snapshot, filtered_history, fundamentals=fundamentals_map)
        bluechip_ranked = dependencies.detector.score_bluechips(features)
    except Exception as exc:
        raise classify_workflow_exception("market_scan", "score", exc) from exc
    score_elapsed = time.perf_counter() - score_started
    if bluechip_ranked.empty:
        raise WorkflowRankingError("market_scan", "score", "No stocks qualified for blue-chip scoring.")

    selected_symbols: List[str] = bluechip_ranked.head(top_n)["symbol"].tolist()
    signal_started = time.perf_counter()
    try:
        signal_rows = compute_symbol_signal_rows(
            symbols=selected_symbols,
            filtered_history=filtered_history,
            bluechip_ranked=bluechip_ranked,
            add_indicators_fn=dependencies.add_indicators_fn,
            detect_patterns_fn=dependencies.detect_patterns_fn,
            build_trade_signal_fn=dependencies.build_trade_signal_fn,
            plot=plot,
            chart_dir=str(output_dir / "charts") if plot else None,
            save_chart_fn=save_chart_fn,
        )
    except Exception as exc:
        raise classify_workflow_exception("market_scan", "signal", exc) from exc
    signal_elapsed = time.perf_counter() - signal_started

    rank_started = time.perf_counter()
    try:
        signal_df = dependencies.rank_opportunities_fn(pd.DataFrame(signal_rows))
        views = build_ranked_views_cached(
            bluechip_ranked=bluechip_ranked,
            signal_df=signal_df,
            build_ranked_views_fn=dependencies.build_ranked_views_fn,
        )
    except Exception as exc:
        raise classify_workflow_exception("market_scan", "rank", exc) from exc
    rank_elapsed = time.perf_counter() - rank_started

    save_started = time.perf_counter()
    try:
        save_outputs(output_dir, bluechip_ranked, signal_df, views)
    except Exception as exc:
        raise classify_workflow_exception("market_scan", "persist", exc) from exc
    save_elapsed = time.perf_counter() - save_started
    log_ranked_summary(views, execution_id=execution_id, workflow_name="market_scan")

    total_elapsed = time.perf_counter() - started_at
    write_benchmark_snapshot(
        output_dir=output_dir,
        file_name="scan_benchmark.json",
        payload={
            "execution_id": execution_id,
            "total_seconds": round(total_elapsed, 6),
            "timings": {
                "fetch_seconds": round(fetch_elapsed, 6),
                "score_seconds": round(score_elapsed, 6),
                "signal_seconds": round(signal_elapsed, 6),
                "rank_seconds": round(rank_elapsed, 6),
                "save_seconds": round(save_elapsed, 6),
            },
            "input": {
                "snapshot_rows": int(len(snapshot)),
                "universe_symbols": int(len(symbols)),
                "selected_symbols": int(len(selected_symbols)),
                "top_n": int(top_n),
                "plot": bool(plot),
            },
        },
    )
    log_workflow_event(
        workflow="market_scan",
        execution_id=execution_id,
        event="workflow_completed",
        total_seconds=round(total_elapsed, 6),
        symbols=int(len(symbols)),
        selected_symbols=int(len(selected_symbols)),
    )

    return MarketScanContext(
        output_dir=output_dir,
        top_n=top_n,
        plot=plot,
        execution_id=execution_id,
        snapshot=snapshot,
        historical_universe=historical_universe,
        symbols=symbols,
        filtered_history=filtered_history,
        bluechip_ranked=bluechip_ranked,
        signal_df=signal_df,
    )
