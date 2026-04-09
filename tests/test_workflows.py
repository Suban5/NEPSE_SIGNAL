"""Tests for extracted workflow modules."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
import json

import numpy as np
import pandas as pd
import pytest

from bluechip.detector import BlueChipDetector
from market.market_scanner import MarketScanner
from workflows.common import build_fundamentals_map, fetch_market_snapshot
from workflows.errors import WorkflowDataError, WorkflowRankingError, WorkflowValidationError
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


def _coordinator() -> Any:
    coordinator = SimpleNamespace()
    coordinator.get_market_snapshot = lambda force_refresh=False: _build_snapshot()
    coordinator.get_universe_with_history = lambda lookback_years=5, force_refresh=False: {
        "AAA": _build_history("AAA", 100.0),
        "BBB": _build_history("BBB", 200.0),
    }
    coordinator.fetch_company_fundamentals = lambda symbol: {
        "epsGrowth": 10.0,
        "salesGrowth": 8.0,
        "dividendYield": 3.0,
    }
    coordinator.normalize_fundamentals = lambda payload: {
        "earnings_growth": 10.0,
        "dividend_stability": 3.0,
        "revenue_growth": 8.0,
    }
    coordinator.get_historical = lambda symbol, start=None, end=None, force_refresh=False: _build_history(symbol, 100.0)
    return cast(Any, coordinator)


def test_market_scan_workflow_writes_outputs(tmp_path: Path) -> None:
    """Market scan workflow should produce ranking files and a typed context."""
    dependencies = MarketScanDependencies(
        coordinator=_coordinator(),
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
    assert isinstance(context.execution_id, str)
    assert context.execution_id
    assert benchmark_payload.get("execution_id") == context.execution_id
    assert benchmark_payload.get("summary") == context.to_summary()
    assert "timings" in benchmark_payload
    assert "total_seconds" in benchmark_payload
    assert context.to_summary()["workflow"] == "market_scan"
    assert context.to_summary()["selected_symbols"] == 2


def test_market_scan_workflow_classifies_empty_scan(tmp_path: Path) -> None:
    """Market scan should classify an empty universe as a data failure."""
    dependencies = MarketScanDependencies(
        coordinator=_coordinator(),
        scanner=MarketScanner(),
        detector=BlueChipDetector(),
        add_indicators_fn=lambda frame: frame,
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
    dependencies.scanner.scan = lambda snapshot, historical_universe: ([], {})

    try:
        run_market_scan_workflow(dependencies, tmp_path, top_n=2, plot=False)
    except WorkflowDataError as exc:
        assert exc.category == "data"
        assert exc.stage == "scan"
        assert "No symbols passed market universe filters." in str(exc)
    else:
        raise AssertionError("Expected WorkflowDataError")


def test_market_scan_workflow_classifies_ranking_failure(tmp_path: Path) -> None:
    """Market scan should classify ranking failures separately from upstream fetch errors."""
    dependencies = MarketScanDependencies(
        coordinator=_coordinator(),
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
        rank_opportunities_fn=lambda _df: (_ for _ in ()).throw(RuntimeError("ranking exploded")),
        build_ranked_views_fn=lambda bc, sig: {
            "top_bluechips": bc,
            "best_buy_signals": sig,
            "strong_momentum": sig,
            "high_risk_weak": sig,
        },
    )

    try:
        run_market_scan_workflow(dependencies, tmp_path, top_n=2, plot=False)
    except WorkflowRankingError as exc:
        assert exc.category == "ranking"
        assert exc.stage == "rank"
        assert "ranking exploded" in str(exc)
    else:
        raise AssertionError("Expected WorkflowRankingError")


def test_market_scan_workflow_rejects_non_positive_top_n(tmp_path: Path) -> None:
    """Market scan should reject non-positive top_n values before executing."""
    dependencies = MarketScanDependencies(
        coordinator=_coordinator(),
        scanner=MarketScanner(),
        detector=BlueChipDetector(),
        add_indicators_fn=lambda frame: frame,
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

    with pytest.raises(ValueError, match="top_n must be >= 1"):
        run_market_scan_workflow(dependencies, tmp_path, top_n=0, plot=False)


def test_market_backtest_workflow_writes_outputs(tmp_path: Path) -> None:
    """Market backtest workflow should produce portfolio outputs and selected symbols."""
    dependencies = MarketBacktestDependencies(
        coordinator=_coordinator(),
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
    assert isinstance(context.execution_id, str)
    assert context.execution_id
    assert benchmark_payload.get("execution_id") == context.execution_id
    assert benchmark_payload.get("summary") == context.to_summary()
    assert "timings" in benchmark_payload
    assert "total_seconds" in benchmark_payload
    assert context.to_summary()["workflow"] == "market_backtest"
    assert context.to_summary()["buy_symbols"] == len(context.selected_buy_symbols)
    assert "historical_validation" in benchmark_payload
    assert benchmark_payload["historical_validation"]["validated_symbols"] == len(context.selected_buy_symbols)
    assert context.historical_validation["sufficient_symbols"] >= 1
    assert context.portfolio_metrics["lookback_days"] == 20
    assert context.to_summary()["historical_symbols_validated"] == len(context.selected_buy_symbols)
    assert "portfolio_cagr" in context.to_summary()


def test_market_backtest_workflow_rejects_invalid_parameters(tmp_path: Path) -> None:
    """Market backtest should reject invalid numeric and enum inputs."""
    dependencies = MarketBacktestDependencies(
        coordinator=_coordinator(),
        scanner=MarketScanner(),
        detector=BlueChipDetector(),
        add_indicators_fn=lambda frame: frame,
        detect_patterns_fn=lambda _df: [],
        build_trade_signal_fn=lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            signal="BUY", confidence=0.9, indicators={}, patterns={}
        ),
        rank_opportunities_fn=lambda df: df,
    )

    with pytest.raises(ValueError, match="lookback_days must be >= 1"):
        run_market_backtest_workflow(dependencies, tmp_path, top_n=2, lookback_days=0, rebalance="static")

    with pytest.raises(ValueError, match="rebalance must be one of"):
        run_market_backtest_workflow(dependencies, tmp_path, top_n=2, lookback_days=20, rebalance="quarterly")


def test_symbol_analysis_workflow_returns_context() -> None:
    """Symbol analysis workflow should return a typed context with results."""
    dependencies = SymbolAnalysisDependencies(
        coordinator=_coordinator(),
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
    assert isinstance(context.execution_id, str)
    assert context.execution_id
    assert context.bluechip_score >= 0.0
    assert context.signal.signal == "BUY"
    assert context.backtest is not None
    summary = context.to_summary()
    assert summary["workflow"] == "symbol_analysis"
    assert summary["symbol"] == "AAA"
    assert summary["signal"] == "BUY"


def test_build_fundamentals_map_stops_after_first_failure() -> None:
    """Fundamentals fetch should disable repeated upstream calls after a failure."""

    class _Fetcher:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_company_fundamentals(self, symbol: str):
            self.calls += 1
            return {}

        def normalize_fundamentals(self, payload):
            return {
                "earnings_growth": 0.0,
                "dividend_stability": 0.0,
                "revenue_growth": 0.0,
            }

    fetcher = _Fetcher()
    result = build_fundamentals_map(fetcher, ["AAA", "BBB", "CCC"])

    assert fetcher.calls == 1
    assert set(result.keys()) == {"AAA", "BBB", "CCC"}
    assert all(values["earnings_growth"] == 0.0 for values in result.values())


def test_symbol_analysis_invalid_symbol_is_classified() -> None:
    """Single-symbol analysis should classify invalid symbols as validation errors."""
    dependencies = SymbolAnalysisDependencies(
        coordinator=_coordinator(),
        detector=BlueChipDetector(),
        detect_patterns_fn=lambda _df: [],
        build_trade_signal_fn=lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            symbol=symbol, signal="BUY", confidence=0.9, indicators={}, timestamp=pd.Timestamp("2025-01-01")
        ),
        add_indicators_fn=lambda frame: frame,
    )

    try:
        run_symbol_analysis_workflow(dependencies, symbol="", start_date=None, end_date=None)
    except WorkflowValidationError as exc:
        assert exc.category == "validation"
        assert exc.stage == "validate"
    else:
        raise AssertionError("Expected WorkflowValidationError")


def test_fetch_market_snapshot_logs_source_breakdown(caplog) -> None:
    """Snapshot fetch should log source summary when data_source is available."""
    coordinator = _coordinator()
    coordinator.get_market_snapshot = lambda force_refresh=False: _build_snapshot().assign(
        data_source=["historical_fallback", "security_master_fallback"]
    )

    with caplog.at_level("INFO"):
        snapshot = fetch_market_snapshot(coordinator, execution_id="test-exec", workflow_name="market_scan")

    assert len(snapshot) == 2
    assert '"event": "snapshot_source_breakdown"' in caplog.text
    assert "historical_fallback=1" in caplog.text
    assert "security_master_fallback=1" in caplog.text
