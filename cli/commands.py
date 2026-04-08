"""CLI command handlers for the NEPSE analyzer."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import pandas as pd

from analysis.candlestick_patterns import detect_latest_patterns
from analysis.indicators import add_indicators
from backtesting.backtest_engine import run_backtest, run_portfolio_backtest
from bluechip.detector import BlueChipDetector, BlueChipScoringConfig
from candlestick.patterns import detect_patterns
from market.market_scanner import MarketScanner
from nepse_api.factory import build_data_fetch_coordinator
from ranking.opportunity_ranker import rank_opportunities
from ranking.stock_ranker import build_ranked_views
from signals.signal_engine import build_trade_signal
from visualization.charts import save_mplfinance_chart, save_plotly_chart
from workflows.common import build_historical_signal_frame as workflow_build_historical_signal_frame
from workflows.market_backtest import MarketBacktestDependencies, run_market_backtest_workflow
from workflows.market_scan import MarketScanDependencies, run_market_scan_workflow
from workflows.symbol_analysis import SymbolAnalysisDependencies, run_symbol_analysis_workflow


logger = logging.getLogger(__name__)


def _emit_workflow_event(command: str, workflow_id: str, phase: str, status: str, **payload: object) -> None:
    """Emit a structured workflow event for CLI tracing."""
    logger.info(
        json.dumps(
            {
                "workflow_id": workflow_id,
                "command": command,
                "phase": phase,
                "status": status,
                **payload,
            },
            default=str,
        )
    )


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Optional list of arguments to parse. If None, uses sys.argv.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(description="NEPSE Blue-Chip + Signal Analyzer")
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan-market", help="Scan full market and rank opportunities")
    scan_parser.add_argument("--top-n", type=int, default=15, help="Top N blue-chip stocks for deep scan")
    scan_parser.add_argument("--plot", action="store_true", help="Generate mplfinance and plotly charts")
    scan_parser.add_argument("--sector-relative", action="store_true", help="Blend sector-relative blue-chip ranking")
    scan_parser.add_argument("--output", type=str, default="output", help="Output folder path")
    scan_parser.add_argument("--force-refresh", action="store_true", help="Force refresh data from API, bypass local cache")

    backtest_parser = subparsers.add_parser("backtest-market", help="Backtest portfolio from market signals")
    backtest_parser.add_argument("--top-n", type=int, default=20, help="Top N blue-chip symbols for signal set")
    backtest_parser.add_argument("--lookback-days", type=int, default=252, help="Backtest lookback trading days")
    backtest_parser.add_argument(
        "--rebalance",
        type=str,
        choices=["static", "weekly", "monthly"],
        default="static",
        help="Portfolio rebalance mode",
    )
    backtest_parser.add_argument("--sector-relative", action="store_true", help="Blend sector-relative blue-chip ranking")
    backtest_parser.add_argument("--output", type=str, default="output", help="Output folder path")
    backtest_parser.add_argument("--force-refresh", action="store_true", help="Force refresh data from API, bypass local cache")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a single stock symbol")
    analyze_parser.add_argument("symbol", type=str, help="Stock symbol (e.g. NABIL)")
    analyze_parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    analyze_parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    analyze_parser.add_argument("--sector-relative", action="store_true", help="Blend sector-relative blue-chip ranking")

    health_parser = subparsers.add_parser("health-check", help="Validate NEPSE API connectivity and data fetch")
    health_parser.add_argument("--symbol", type=str, help="Optional symbol for historical data check (e.g. NABIL)")

    top_volume_parser = subparsers.add_parser("top-volume", help="Show highest-volume stocks in live market")
    top_volume_parser.add_argument("--limit", type=int, default=10, help="Number of symbols to show")
    top_volume_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh snapshot from API, bypass local cache",
    )

    api_parser = subparsers.add_parser("run-api", help="Run FastAPI wrapper for Postman/API usage")
    api_parser.add_argument("--host", type=str, default="0.0.0.0", help="API server host")
    api_parser.add_argument("--port", type=int, default=8000, help="API server port")
    api_parser.add_argument("--reload", action="store_true", help="Enable autoreload for development")

    parser.add_argument("--scan-market", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--symbol", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--plot", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output", type=str, default="output", help=argparse.SUPPRESS)
    parser.add_argument("--top-n", type=int, default=15, help=argparse.SUPPRESS)
    parser.add_argument("--start-date", type=str, help=argparse.SUPPRESS)
    parser.add_argument("--end-date", type=str, help=argparse.SUPPRESS)
    return parser.parse_args(args)


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Parse date string in YYYY-MM-DD format.

    Args:
        value: Date string.

    Returns:
        Parsed date or None.
    """
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _build_signal_row(
    symbol: str,
    bluechip_score: float,
    signal_type: str,
    confidence: float,
    indicators: Dict[str, float],
    patterns: Dict[str, bool],
) -> Dict[str, float | str | bool]:
    """Build signal output row."""
    return {
        "symbol": symbol,
        "bluechip_score": round(bluechip_score, 4),
        "signal": signal_type,
        "confidence": confidence,
        **indicators,
        **patterns,
    }


def _format_score_breakdown(breakdown_dict: dict | None) -> str:
    """Format score breakdown into human-readable string for CLI display.

    Args:
        breakdown_dict: Dictionary with component scores (market_cap, volume, stability, trend, fundamental, sector)

    Returns:
        Formatted string like: "mkt=0.85 vol=0.72 stab=0.68 trend=0.91 fund=0.45 sec=0.70"
    """
    if not breakdown_dict:
        return "N/A"
    
    try:
        components = {
            "mkt": breakdown_dict.get("market_cap", 0.0),
            "vol": breakdown_dict.get("volume", 0.0),
            "stab": breakdown_dict.get("stability", 0.0),
            "trend": breakdown_dict.get("trend", 0.0),
            "fund": breakdown_dict.get("fundamental", 0.0),
            "sec": breakdown_dict.get("sector", 0.0),
        }
        parts = [f"{key}={val:.2f}" for key, val in components.items()]
        return " ".join(parts)
    except (TypeError, ValueError, AttributeError):
        return "N/A"


def _save_outputs(
    output_dir: Path,
    bluechip_ranked: pd.DataFrame,
    signal_df: pd.DataFrame,
    views: Dict[str, pd.DataFrame],
) -> None:
    """Save computed outputs as CSV files."""
    bluechip_ranked.to_csv(output_dir / "bluechip_ranked.csv", index=False)
    signal_df.to_csv(output_dir / "signal_summary.csv", index=False)
    views["best_buy_signals"].to_csv(output_dir / "best_buy_signals.csv", index=False)
    views["best_buy_signals"].to_csv(output_dir / "top_buy_signals.csv", index=False)
    views["strong_momentum"].to_csv(output_dir / "strong_momentum.csv", index=False)
    views["high_risk_weak"].to_csv(output_dir / "high_risk_weak.csv", index=False)


def _legacy_mode_requested(args: argparse.Namespace) -> bool:
    """Return True when legacy flag-style invocation is used."""
    return bool(args.scan_market or args.symbol)


def _log_ranked_summary(views: Dict[str, pd.DataFrame]) -> None:
    """Log concise ranking summary with top bluechip scores and breakdowns."""
    logger.info("Top Blue-Chip Stocks: %d", len(views["top_bluechips"]))
    logger.info("Best Buy Signals: %d", len(views["best_buy_signals"]))
    logger.info("Strong Momentum Stocks: %d", len(views["strong_momentum"]))
    logger.info("High Risk / Weak Stocks: %d", len(views["high_risk_weak"]))
    
    # Log top-5 bluechips with score breakdowns for transparency
    if not views["top_bluechips"].empty:
        logger.info("--- Top 5 Blue-Chip Scores (with component breakdown) ---")
        top_5 = views["top_bluechips"].head(5)
        for _, row in top_5.iterrows():
            symbol = row.get("symbol", "?")
            score = row.get("bluechip_score", 0.0)
            breakdown = _format_score_breakdown(row.get("score_breakdown"))
            logger.info("  %s: %.4f | %s", symbol, score, breakdown)


def _build_bluechip_detector(sector_relative: bool) -> BlueChipDetector:
    """Create a blue-chip detector with optional sector-relative scoring."""
    detector_factory = BlueChipDetector
    config = BlueChipScoringConfig(sector_relative=sector_relative)
    try:
        return detector_factory(config=config)
    except TypeError:
        return detector_factory()


def _build_historical_signal_frame(
    symbol: str,
    technical_df: pd.DataFrame,
    bluechip_score: float,
) -> pd.DataFrame:
    """Compatibility shim for the historical signal frame helper."""
    return workflow_build_historical_signal_frame(symbol, technical_df, bluechip_score, detect_patterns, build_trade_signal)


def scan_market(args: argparse.Namespace) -> None:
    """Execute full-market scan and ranking workflow.

    Args:
        args: CLI arguments.
    """
    output_dir = Path(args.output)
    run_market_scan_workflow(
        MarketScanDependencies(
            coordinator=build_data_fetch_coordinator(),
            scanner=MarketScanner(),
            detector=_build_bluechip_detector(bool(getattr(args, "sector_relative", False))),
            add_indicators_fn=add_indicators,
            detect_patterns_fn=detect_patterns,
            build_trade_signal_fn=build_trade_signal,
            rank_opportunities_fn=rank_opportunities,
            build_ranked_views_fn=build_ranked_views,
        ),
        output_dir=output_dir,
        top_n=args.top_n,
        plot=args.plot,


        force_refresh=bool(getattr(args, "force_refresh", False)),
    )


def backtest_market(args: argparse.Namespace) -> None:
    """Run portfolio-level backtest over generated market signals.

    Args:
        args: CLI arguments.
    """
    run_market_backtest_workflow(
        MarketBacktestDependencies(
            coordinator=build_data_fetch_coordinator(),
            scanner=MarketScanner(),
            detector=_build_bluechip_detector(bool(getattr(args, "sector_relative", False))),
            add_indicators_fn=add_indicators,
            detect_patterns_fn=detect_patterns,
            build_trade_signal_fn=build_trade_signal,
            rank_opportunities_fn=rank_opportunities,
        ),
        output_dir=Path(args.output),
        top_n=args.top_n,
        lookback_days=args.lookback_days,
        rebalance=args.rebalance,
        force_refresh=bool(getattr(args, "force_refresh", False)),
    )
def scan_symbol(args: argparse.Namespace) -> None:
    """Execute single-symbol analysis workflow.

    Args:
        args: CLI arguments.
    """
    context = run_symbol_analysis_workflow(
        SymbolAnalysisDependencies(
            coordinator=build_data_fetch_coordinator(),
            detector=_build_bluechip_detector(bool(getattr(args, "sector_relative", False))),
            detect_patterns_fn=detect_patterns,
            build_trade_signal_fn=build_trade_signal,
            add_indicators_fn=add_indicators,
        ),
        symbol=getattr(args, "symbol", None),
        start_date=getattr(args, "start_date", None),
        end_date=getattr(args, "end_date", None),
    )

    logger.info("Symbol: %s", context.symbol)
    logger.info("Blue-Chip Score: %.4f", context.bluechip_score)
    logger.info("Signal: %s", context.signal.signal)
    logger.info("Confidence: %.2f", context.signal.confidence)
    logger.info("Technical Indicators: %s", context.signal.indicators)
    logger.info("Patterns: %s", detect_latest_patterns(context.technical_df))
    logger.info(
        "Backtest Metrics: CAGR=%.4f, MaxDrawdown=%.4f, WinRate=%.4f, Sharpe=%.4f",
        context.backtest.cagr,
        context.backtest.max_drawdown,
        context.backtest.win_rate,
        context.backtest.sharpe_ratio,
    )


def health_check(args: argparse.Namespace) -> None:
    """Run connectivity and data-readiness checks for NEPSE data source.

    Args:
        args: CLI arguments.
    """
    fetcher = build_data_fetch_coordinator()
    logger.info("Health check started")

    snapshot = fetcher.get_market_snapshot()
    if snapshot.empty:
        raise RuntimeError("Health check failed: snapshot endpoint returned no rows")
    logger.info("Snapshot check passed | rows=%d", len(snapshot))

    target_symbol = getattr(args, "symbol", None)
    if target_symbol:
        symbol = str(target_symbol).upper().strip()
    else:
        symbol = str(snapshot.iloc[0].get("symbol", "")).upper().strip()

    if not symbol:
        raise RuntimeError("Health check failed: unable to determine symbol for historical check")

    history = fetcher.get_historical(symbol=symbol, start=None, end=None)
    if history.empty:
        raise RuntimeError(f"Health check failed: historical endpoint returned no rows for {symbol}")

    logger.info(
        "Historical check passed | symbol=%s rows=%d range=%s to %s",
        symbol,
        len(history),
        history.iloc[0]["date"],
        history.iloc[-1]["date"],
    )
    logger.info("Health check completed successfully")


def top_volume(args: argparse.Namespace) -> None:
    """Show top traded-volume symbols from live market snapshot.

    Args:
        args: CLI arguments.
    """
    fetcher = build_data_fetch_coordinator()
    limit = max(1, int(getattr(args, "limit", 10)))
    force_refresh = bool(getattr(args, "force_refresh", False))

    snapshot = fetcher.get_market_snapshot(force_refresh=force_refresh)

    if snapshot.empty:
        raise RuntimeError("Top-volume failed: market snapshot is empty")

    if "volume" not in snapshot.columns:
        raise RuntimeError("Top-volume failed: snapshot has no volume column")

    out = snapshot.copy()
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0.0)
    out = out.sort_values("volume", ascending=False).head(limit)

    selected_columns = [col for col in ["symbol", "close", "volume", "turnover", "data_source", "sector"] if col in out.columns]
    logger.info("Top %d live-market symbols by volume", limit)
    logger.info("\n%s", out[selected_columns].to_string(index=False))


def run_api(args: argparse.Namespace) -> None:
    """Run FastAPI wrapper server.

    Args:
        args: CLI arguments.
    """
    import uvicorn

    logger.info("Starting API server on %s:%d (reload=%s)", args.host, args.port, bool(args.reload))
    uvicorn.run("api_server:app", host=args.host, port=args.port, reload=bool(args.reload))


def run(args: argparse.Namespace) -> None:
    """Run command dispatch with support for modern and legacy CLI styles."""
    workflow_id = str(uuid4())
    command_name = getattr(args, "command", None) or ("legacy" if _legacy_mode_requested(args) else "unknown")
    _emit_workflow_event(command_name, workflow_id, "start", "started")
    try:
        if args.command == "scan-market":
            scan_market(args)
        elif args.command == "analyze":
            scan_symbol(args)
        elif args.command == "backtest-market":
            backtest_market(args)
        elif args.command == "health-check":
            health_check(args)
        elif args.command == "top-volume":
            top_volume(args)
        elif args.command == "run-api":
            run_api(args)
        elif _legacy_mode_requested(args):
            if args.scan_market:
                scan_market(args)
            elif args.symbol:
                scan_symbol(args)
        else:
            raise SystemExit(
                "Usage: python main.py scan-market [--top-n N --plot] OR "
                "python main.py analyze <SYMBOL> [--start-date YYYY-MM-DD --end-date YYYY-MM-DD] OR "
                "python main.py backtest-market [--top-n N --lookback-days D] OR "
                "python main.py health-check [--symbol SYMBOL] OR "
                "python main.py top-volume [--limit N --force-refresh] OR "
                "python main.py run-api [--host HOST --port PORT --reload]"
            )
    finally:
        _emit_workflow_event(command_name, workflow_id, "end", "completed")
