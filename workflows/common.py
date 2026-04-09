"""Shared workflow helpers for market scan, backtest, and analysis flows."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import json
import logging
import time

import pandas as pd

from api.cache import TTLCache
from analysis.candlestick_patterns import detect_latest_patterns
from analysis.indicators import add_indicators
from bluechip.detector import BlueChipDetector
from candlestick.patterns import detect_patterns
from config.settings import get_settings
from ranking.opportunity_ranker import rank_opportunities
from ranking.stock_ranker import build_ranked_views
from signals.signal_engine import build_trade_signal
from visualization.charts import save_mplfinance_chart, save_plotly_chart

from .errors import classify_workflow_exception
from .context import validate_historical_universe, validate_snapshot


logger = logging.getLogger(__name__)


_ranking_cache: TTLCache | None = None


def new_execution_id(workflow_name: str) -> str:
    """Generate a short execution identifier for workflow correlation."""
    normalized = workflow_name.strip().lower().replace(" ", "-") or "workflow"
    return f"{normalized}-{uuid4().hex[:10]}"


def log_workflow_event(
    workflow: str,
    execution_id: str,
    event: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit structured workflow log events with execution correlation.

    Args:
        workflow: Workflow name (scan, backtest, symbol-analysis).
        execution_id: Unique execution identifier.
        event: Event name for this log line.
        level: Logging level.
        **fields: Structured event fields.
    """
    payload = {
        "workflow": workflow,
        "execution_id": execution_id,
        "event": event,
        **fields,
    }
    logger.log(level, "%s", json.dumps(payload, sort_keys=True, default=str))


def _get_ranking_cache() -> TTLCache:
    """Return lazily initialized ranking cache."""
    global _ranking_cache
    if _ranking_cache is None:
        settings = get_settings()
        _ranking_cache = TTLCache(
            ttl_seconds=max(1.0, float(settings.cache_ranking_ttl_seconds)),
            max_entries=max(100, int(settings.cache_max_entries)),
        )
    return _ranking_cache


def _ranking_cache_key(bluechip_ranked: pd.DataFrame, signal_df: pd.DataFrame) -> str:
    """Build a stable cache key for ranking views."""
    bluechip_rows = bluechip_ranked[[col for col in ["symbol", "bluechip_score", "rank"] if col in bluechip_ranked.columns]]
    signal_rows = signal_df[[col for col in ["symbol", "signal", "confidence", "trade_score"] if col in signal_df.columns]]
    bluechip_repr = bluechip_rows.to_json(orient="records", date_format="iso")
    signal_repr = signal_rows.to_json(orient="records", date_format="iso")
    return f"rank:{hash(bluechip_repr)}:{hash(signal_repr)}"


def build_fundamentals_map(fetcher: Any, symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """Fetch and normalize fundamentals for a symbol list.

    If the first fundamentals request fails or returns an empty payload, the
    function stops calling the upstream endpoint for the remaining symbols and
    falls back to default metrics. This prevents retry storms when the
    fundamentals endpoint is unavailable.
    """
    fundamentals_map: Dict[str, Dict[str, float]] = {}
    fundamentals_enabled = True
    for symbol in symbols:
        if not fundamentals_enabled:
            fundamentals_map[symbol] = {
                "earnings_growth": 0.0,
                "dividend_stability": 0.0,
                "revenue_growth": 0.0,
            }
            continue

        try:
            payload = fetcher.fetch_company_fundamentals(symbol)
            normalized = fetcher.normalize_fundamentals(payload)
            fundamentals_map[symbol] = normalized
            if not payload:
                logger.warning("Fundamentals endpoint unavailable; skipping remaining fundamentals requests")
                fundamentals_enabled = False
        except Exception as exc:
            failure = classify_workflow_exception("market_scan", "fundamentals", exc)
            logger.debug(
                "Fundamentals unavailable for %s: %s (%s/%s)",
                symbol,
                exc,
                failure.category,
                failure.stage,
            )
            fundamentals_map[symbol] = {
                "earnings_growth": 0.0,
                "dividend_stability": 0.0,
                "revenue_growth": 0.0,
            }
            fundamentals_enabled = False
    return fundamentals_map


def compute_symbol_signal_rows(
    symbols: List[str],
    filtered_history: Dict[str, pd.DataFrame],
    bluechip_ranked: pd.DataFrame,
    add_indicators_fn: Callable[[pd.DataFrame], pd.DataFrame],
    detect_patterns_fn: Callable[[pd.DataFrame], List[Any]],
    build_trade_signal_fn: Callable[[str, pd.DataFrame, List[Any], float], Any],
    plot: bool = False,
    chart_dir: Optional[str] = None,
    save_chart_fn: Optional[Callable[[pd.DataFrame, str, str], None]] = None,
) -> List[Dict[str, float | str | bool]]:
    """Compute signal rows with bounded concurrency and deterministic ordering."""
    settings = get_settings()
    max_workers = max(1, int(settings.market_parallel_workers))

    def _build_for_symbol(symbol: str) -> Optional[Dict[str, float | str | bool]]:
        history = filtered_history.get(symbol)
        if history is None or history.empty:
            return None

        technical_df = add_indicators_fn(history)
        pattern_map = detect_market_patterns(technical_df)
        pattern_results = detect_patterns_fn(technical_df)
        bluechip_score = BlueChipDetector.get_symbol_score(bluechip_ranked, symbol, default=0.0)
        signal = build_trade_signal_fn(symbol, technical_df, pattern_results, bluechip_score)

        if plot and chart_dir and save_chart_fn is not None:
            save_chart_fn(technical_df, symbol, chart_dir)

        return build_signal_row(
            symbol=symbol,
            bluechip_score=bluechip_score,
            signal_type=signal.signal,
            confidence=signal.confidence,
            indicators=signal.indicators,
            patterns=pattern_map,
        )

    rows_by_symbol: Dict[str, Dict[str, float | str | bool]] = {}
    ordered_symbols = list(symbols)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_by_symbol: Dict[str, Future[Optional[Dict[str, float | str | bool]]]] = {
            symbol: executor.submit(_build_for_symbol, symbol)
            for symbol in ordered_symbols
        }
        for symbol in ordered_symbols:
            try:
                row = future_by_symbol[symbol].result()
            except Exception as exc:
                failure = classify_workflow_exception("signal", "ranking", exc)
                logger.warning(
                    "Signal generation failed for %s: %s (%s/%s)",
                    symbol,
                    exc,
                    failure.category,
                    failure.stage,
                )
                continue
            if row is not None:
                rows_by_symbol[symbol] = row

    return [rows_by_symbol[symbol] for symbol in ordered_symbols if symbol in rows_by_symbol]


def build_ranked_views_cached(
    bluechip_ranked: pd.DataFrame,
    signal_df: pd.DataFrame,
    build_ranked_views_fn: Callable[[pd.DataFrame, pd.DataFrame], Dict[str, pd.DataFrame]],
) -> Dict[str, pd.DataFrame]:
    """Build ranked views with a short TTL cache."""
    cache = _get_ranking_cache()
    cache_key = _ranking_cache_key(bluechip_ranked, signal_df)
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return {name: frame.copy() for name, frame in cached.items()}

    views = build_ranked_views_fn(bluechip_ranked, signal_df)
    cache.set(cache_key, {name: frame.copy() for name, frame in views.items()})
    return views


def write_benchmark_snapshot(output_dir: Path, file_name: str, payload: Dict[str, Any]) -> None:
    """Write benchmark/timing payload as JSON artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / file_name).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")




def fetch_market_snapshot(
    coordinator: Any,
    force_refresh: bool = False,
    execution_id: str = "",
    workflow_name: str = "workflow",
) -> pd.DataFrame:
    """Fetch live snapshot via coordinator.
    
    Args:
        coordinator: Data fetch coordinator instance.
        force_refresh: If True, bypass cache and fetch from API.
    """
    log_workflow_event(
        workflow=workflow_name,
        execution_id=execution_id,
        event="fetch_market_snapshot_started",
        force_refresh=bool(force_refresh),
    )
    try:
        snapshot = coordinator.get_market_snapshot(force_refresh=force_refresh)
        validate_snapshot(snapshot)
    except Exception as exc:
        failure = classify_workflow_exception(workflow_name, "fetch", exc)
        log_workflow_event(
            workflow=workflow_name,
            execution_id=execution_id,
            event="workflow_failed",
            level=logging.ERROR,
            stage=failure.stage,
            category=failure.category,
            error_type=exc.__class__.__name__,
            retriable=failure.retriable,
            message=str(exc),
        )
        raise failure from exc

    log_workflow_event(
        workflow=workflow_name,
        execution_id=execution_id,
        event="fetch_market_snapshot_completed",
        row_count=int(len(snapshot)),
    )
    log_snapshot_source_summary(snapshot, execution_id=execution_id, workflow_name=workflow_name)
    return snapshot


def log_snapshot_source_summary(
    snapshot: pd.DataFrame,
    execution_id: str = "",
    workflow_name: str = "workflow",
) -> None:
    """Log row count breakdown by snapshot data source when available."""
    if "data_source" not in snapshot.columns:
        return

    source_counts = snapshot["data_source"].fillna("unknown").astype(str).value_counts()
    if source_counts.empty:
        return

    breakdown = ", ".join([f"{source}={int(count)}" for source, count in source_counts.items()])
    log_workflow_event(
        workflow=workflow_name,
        execution_id=execution_id,
        event="snapshot_source_breakdown",
        breakdown=breakdown,
    )


def fetch_historical_universe(
    coordinator: Any,
    lookback_years: int = 5,
    force_refresh: bool = False,
    execution_id: str = "",
    workflow_name: str = "workflow",
) -> Dict[str, pd.DataFrame]:
    """Fetch and validate the historical market universe.
    
    Args:
        coordinator: Data fetch coordinator instance.
        lookback_years: Number of years of history to retrieve.
        force_refresh: If True, bypass cache and fetch from API.
    """
    log_workflow_event(
        workflow=workflow_name,
        execution_id=execution_id,
        event="fetch_historical_universe_started",
        lookback_years=int(lookback_years),
        force_refresh=bool(force_refresh),
    )
    try:
        historical_universe = coordinator.get_universe_with_history(
            lookback_years=lookback_years,
            force_refresh=force_refresh,
        )
        validate_historical_universe(historical_universe)
    except Exception as exc:
        failure = classify_workflow_exception(workflow_name, "fetch", exc)
        log_workflow_event(
            workflow=workflow_name,
            execution_id=execution_id,
            event="workflow_failed",
            level=logging.ERROR,
            stage=failure.stage,
            category=failure.category,
            error_type=exc.__class__.__name__,
            retriable=failure.retriable,
            message=str(exc),
        )
        raise failure from exc

    log_workflow_event(
        workflow=workflow_name,
        execution_id=execution_id,
        event="fetch_historical_universe_completed",
        symbol_count=int(len(historical_universe)),
    )
    return historical_universe
def build_signal_row(
    symbol: str,
    bluechip_score: float,
    signal_type: str,
    confidence: float,
    indicators: Dict[str, float],
    patterns: Dict[str, bool],
) -> Dict[str, float | str | bool]:
    """Build a flat signal output row."""
    return {
        "symbol": symbol,
        "bluechip_score": round(bluechip_score, 4),
        "signal": signal_type,
        "confidence": confidence,
        **indicators,
        **patterns,
    }


def save_outputs(
    output_dir: Path,
    bluechip_ranked: pd.DataFrame,
    signal_df: pd.DataFrame,
    views: Dict[str, pd.DataFrame],
) -> None:
    """Persist ranking outputs to CSV files."""
    bluechip_ranked.to_csv(output_dir / "bluechip_ranked.csv", index=False)
    signal_df.to_csv(output_dir / "signal_summary.csv", index=False)
    views["best_buy_signals"].to_csv(output_dir / "best_buy_signals.csv", index=False)
    views["best_buy_signals"].to_csv(output_dir / "top_buy_signals.csv", index=False)
    views["strong_momentum"].to_csv(output_dir / "strong_momentum.csv", index=False)
    views["high_risk_weak"].to_csv(output_dir / "high_risk_weak.csv", index=False)


def log_ranked_summary(
    views: Dict[str, pd.DataFrame],
    execution_id: str = "",
    workflow_name: str = "workflow",
) -> None:
    """Log concise ranking summary."""
    log_workflow_event(
        workflow=workflow_name,
        execution_id=execution_id,
        event="ranked_summary",
        top_bluechips=int(len(views["top_bluechips"])),
        best_buy_signals=int(len(views["best_buy_signals"])),
        strong_momentum=int(len(views["strong_momentum"])),
        high_risk_weak=int(len(views["high_risk_weak"])),
    )


def build_historical_signal_frame(
    symbol: str,
    technical_df: pd.DataFrame,
    bluechip_score: float,
    detect_patterns_fn: Callable[[pd.DataFrame], List[Any]] = detect_patterns,
    build_trade_signal_fn: Callable[[str, pd.DataFrame, List[Any], float], Any] = build_trade_signal,
) -> pd.DataFrame:
    """Build a date-aligned historical signal frame."""
    if technical_df.empty or "date" not in technical_df.columns or "close" not in technical_df.columns:
        return pd.DataFrame(columns=["date", "close", "signal"])

    out = technical_df[["date", "close"]].copy().sort_values("date").reset_index(drop=True)
    signals: List[str] = []
    for index in range(len(technical_df)):
        if index < 1:
            signals.append("HOLD")
            continue

        window_df = technical_df.iloc[: index + 1]
        pattern_results = detect_patterns_fn(window_df)
        signal = build_trade_signal_fn(symbol, window_df, pattern_results, bluechip_score)
        signals.append(signal.signal)

    out["signal"] = signals
    return out


def build_technical_frame(history: pd.DataFrame) -> pd.DataFrame:
    """Add indicators to a price history frame."""
    return add_indicators(history)


def detect_market_patterns(technical_df: pd.DataFrame) -> Dict[str, bool]:
    """Detect latest candlestick patterns for a technical frame."""
    return detect_latest_patterns(technical_df)


def rank_signal_frame(signal_df: pd.DataFrame) -> pd.DataFrame:
    """Rank signal output using the opportunity ranker."""
    return rank_opportunities(signal_df)


def build_ranked_views_for_market(bluechip_ranked: pd.DataFrame, signal_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Build categorized ranking tables."""
    return build_ranked_views(bluechip_ranked, signal_df)


def render_charts(technical_df: pd.DataFrame, symbol: str, output_dir: str) -> None:
    """Render available charts for a symbol."""
    save_mplfinance_chart(technical_df, symbol=symbol, output_dir=output_dir)
    save_plotly_chart(technical_df, symbol=symbol, output_dir=output_dir)

