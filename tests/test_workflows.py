"""Tests for extracted workflow modules."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
import json

import numpy as np
import pandas as pd

from bluechip.detector import BlueChipDetector
from market.market_scanner import MarketScanner
from workflows.market_backtest import MarketBacktestDependencies, run_market_backtest_workflow
from workflows.market_scan import MarketScanDependencies, run_market_scan_workflow
from workflows.symbol_analysis import SymbolAnalysisDependencies, run_symbol_analysis_workflow


def _build_snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "sector": ["Banking", "Hydro"],
            "market_cap": [1_000_000_000, 500_000_000],
            "open": [100.0, 200.0],
            "high": [105.0, 205.0],
            "low": [95.0, 195.0],
            "close": [102.0, 198.0],
            "volume": [10_000, 8_000],
        }
    )


def _build_history(symbol: str, base: float) -> pd.DataFrame:
    close = np.linspace(base, base * 1.15, 220)
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=len(close), freq="D"),
            "symbol": symbol,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": np.full(len(close), 5_000),
            "turnover": np.full(len(close), 250_000),
        }
    )


def _fetcher() -> Any:
    fetcher = SimpleNamespace()
    fetcher.fetch_daily_market_snapshot = lambda: _build_snapshot()
    fetcher.fetch_symbols = lambda: _build_snapshot()[["symbol", "sector", "market_cap"]]
    fetcher.fetch_universe_with_history = lambda lookback_years=5: {
        "AAA": _build_history("AAA", 100.0),
        "BBB": _build_history("BBB", 200.0),
    }
    fetcher.fetch_company_fundamentals = lambda symbol: {"epsGrowth": 10.0, "salesGrowth": 8.0, "dividendYield": 3.0}
    fetcher.normalize_fundamentals = lambda payload: {
        "earnings_growth": 10.0,
        "dividend_stability": 3.0,
        "revenue_growth": 8.0,
    }
    fetcher.fetch_historical_ohlcv = lambda symbol, start_date=None, end_date=None: _build_history(symbol, 100.0)
    return cast(Any, fetcher)


def test_market_scan_workflow_writes_outputs(tmp_path: Path) -> None:
    """Market scan workflow should produce ranking files and a typed context."""
    dependencies = MarketScanDependencies(
        fetcher=_fetcher(),
        scanner=MarketScanner(),
        detector=BlueChipDetector(),
        add_indicators_fn=lambda frame: frame.assign(
            sma20=frame["close"],
            sma50=frame["close"],
            sma200=frame["close"],
            ema20=frame["close"],
            rsi14=50.0,
            macd=0.1,
            macd_signal=0.05,
            bb_upper=frame["close"] + 2,
            bb_lower=frame["close"] - 2,
            volume_sma20=frame["volume"],
            volume_trend=1.0,
        ),
        detect_patterns_fn=lambda _df: [],
        build_trade_signal_fn=lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            signal="BUY", confidence=0.9, indicators={}, patterns={}
        ),
        rank_opportunities_fn=lambda df: df,
        build_ranked_views_fn=lambda bc, sig: {
            "top_bluechips": bc,
            "best_buy_signals": sig,
            "strong_momentum": sig,
            "high_risk_weak": sig,
        },
    )

    context = run_market_scan_workflow(dependencies, tmp_path, top_n=2, plot=False)

    assert context.top_n == 2
    assert not context.bluechip_ranked.empty
    assert (tmp_path / "bluechip_ranked.csv").exists()
    assert (tmp_path / "signal_summary.csv").exists()
    assert (tmp_path / "scan_benchmark.json").exists()
    benchmark_payload = json.loads((tmp_path / "scan_benchmark.json").read_text(encoding="utf-8"))
    assert "timings" in benchmark_payload
    assert "total_seconds" in benchmark_payload


def test_market_backtest_workflow_writes_outputs(tmp_path: Path) -> None:
    """Market backtest workflow should produce portfolio outputs and selected symbols."""
    dependencies = MarketBacktestDependencies(
        fetcher=_fetcher(),
        scanner=MarketScanner(),
        detector=BlueChipDetector(),
        add_indicators_fn=lambda frame: frame.assign(
            sma20=frame["close"],
            sma50=frame["close"],
            sma200=frame["close"],
            ema20=frame["close"],
            rsi14=50.0,
            macd=0.1,
            macd_signal=0.05,
            bb_upper=frame["close"] + 2,
            bb_lower=frame["close"] - 2,
            volume_sma20=frame["volume"],
            volume_trend=1.0,
        ),
        detect_patterns_fn=lambda _df: [],
        build_trade_signal_fn=lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            signal="BUY", confidence=0.9, indicators={}, patterns={}
        ),
        rank_opportunities_fn=lambda df: df,
    )

    context = run_market_backtest_workflow(dependencies, tmp_path, top_n=2, lookback_days=20, rebalance="static")

    assert context.rebalance == "static"
    assert (tmp_path / "portfolio_backtest.json").exists()
    assert (tmp_path / "portfolio_signal_set.csv").exists()
    assert (tmp_path / "backtest_benchmark.json").exists()
    benchmark_payload = json.loads((tmp_path / "backtest_benchmark.json").read_text(encoding="utf-8"))
    assert "timings" in benchmark_payload
    assert "total_seconds" in benchmark_payload


def test_symbol_analysis_workflow_returns_context() -> None:
    """Symbol analysis workflow should return a typed context with results."""
    dependencies = SymbolAnalysisDependencies(
        fetcher=_fetcher(),
        detector=BlueChipDetector(),
        detect_patterns_fn=lambda _df: [],
        build_trade_signal_fn=lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            symbol=symbol, signal="BUY", confidence=0.9, indicators={}, timestamp=pd.Timestamp("2025-01-01")
        ),
        add_indicators_fn=lambda frame: frame.assign(
            sma20=frame["close"],
            sma50=frame["close"],
            sma200=frame["close"],
            ema20=frame["close"],
            rsi14=50.0,
            macd=0.1,
            macd_signal=0.05,
            bb_upper=frame["close"] + 2,
            bb_lower=frame["close"] - 2,
            volume_sma20=frame["volume"],
            volume_trend=1.0,
        ),
    )

    context = run_symbol_analysis_workflow(dependencies, symbol="AAA", start_date=None, end_date=None)

    assert context.symbol == "AAA"
    assert context.bluechip_score >= 0.0
    assert context.signal.signal == "BUY"
    assert context.backtest is not None
