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
from workflows.common import (
    build_fundamentals_map,
    build_symbol_signal_row,
    fetch_historical_universe,
    fetch_market_snapshot,
)
from workflows.errors import WorkflowDataError, WorkflowRankingError, WorkflowValidationError
from workflows.market_backtest import (
    MarketBacktestDependencies,
    _build_historical_validation,
    run_market_backtest_workflow,
)
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


def test_market_scan_workflow_does_not_emit_artifacts_on_ranking_failure(tmp_path: Path) -> None:
    """Market scan should leave no benchmark artifacts behind when ranking fails."""
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

    with pytest.raises(WorkflowRankingError):
        run_market_scan_workflow(dependencies, tmp_path, top_n=2, plot=False)

    assert not (tmp_path / "bluechip_ranked.csv").exists()
    assert not (tmp_path / "signal_summary.csv").exists()
    assert not (tmp_path / "scan_benchmark.json").exists()


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


def test_build_historical_validation_marks_missing_and_sparse_symbols() -> None:
    """Historical validation should classify missing and insufficient symbols separately."""
    filtered_history = {
        "AAA": _build_history("AAA", 100.0).head(3).copy(),
        "CCC": _build_history("CCC", 120.0).head(1).copy(),
    }

    validation = _build_historical_validation(filtered_history, ["AAA", "BBB", "CCC"], lookback_days=5)

    assert validation["validated_symbols"] == 3
    assert validation["sufficient_symbols"] == 1
    assert validation["insufficient_symbols"] == 1
    assert validation["sufficient_history_symbols"] == ["AAA"]
    assert validation["insufficient_history_symbols"] == ["CCC"]
    assert validation["missing_history_symbols"] == ["BBB"]
    assert validation["symbol_row_counts"] == {"AAA": 3, "BBB": 0, "CCC": 1}


def test_market_backtest_workflow_rejects_buy_symbols_without_sufficient_history(tmp_path: Path) -> None:
    """Market backtest should fail cleanly when BUY symbols do not have enough history."""
    dependencies = MarketBacktestDependencies(
        coordinator=_coordinator(),
        scanner=MarketScanner(),
        detector=BlueChipDetector(),
        add_indicators_fn=lambda frame: frame,
        detect_patterns_fn=lambda _df: [],
        build_trade_signal_fn=lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            signal="BUY", confidence=0.9, indicators={}, patterns={}
        ),
        rank_opportunities_fn=lambda df: pd.DataFrame({"symbol": ["AAA"], "signal": ["BUY"]}),
    )

    dependencies.scanner.scan = lambda snapshot, historical_universe: (
        ["AAA"],
        {"AAA": _build_history("AAA", 100.0).head(1).copy()},
    )

    def _build_feature_table_override(
        market_snapshot: pd.DataFrame,
        historical_data: dict[str, pd.DataFrame],
        fundamentals: dict[str, dict[object, object]] | None = None,
    ) -> pd.DataFrame:
        del market_snapshot, historical_data, fundamentals
        return pd.DataFrame({"symbol": ["AAA"], "bluechip_score": [0.91]})

    def _select_top_symbols_override(scored: pd.DataFrame, top_n: int) -> list[str]:
        del scored, top_n
        return ["AAA"]

    dependencies.detector.build_feature_table = _build_feature_table_override
    dependencies.detector.score_bluechips = lambda features: features
    dependencies.detector.select_top_symbols = _select_top_symbols_override

    with pytest.raises(WorkflowDataError, match="No BUY symbols have sufficient historical rows for backtest window."):
        run_market_backtest_workflow(dependencies, tmp_path, top_n=1, lookback_days=20, rebalance="static")

    assert not (tmp_path / "portfolio_backtest.json").exists()
    assert not (tmp_path / "portfolio_signal_set.csv").exists()
    assert not (tmp_path / "backtest_benchmark.json").exists()


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


def test_workflow_summaries_share_common_contract_fields(tmp_path: Path) -> None:
    """Workflow summaries should expose shared keys for cross-layer contract alignment."""
    scan_dependencies = MarketScanDependencies(
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
    backtest_dependencies = MarketBacktestDependencies(
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
    symbol_dependencies = SymbolAnalysisDependencies(
        coordinator=_coordinator(),
        detector=BlueChipDetector(),
        detect_patterns_fn=lambda _df: [],
        build_trade_signal_fn=lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            symbol=symbol,
            signal="BUY",
            confidence=0.9,
            indicators={},
            timestamp=pd.Timestamp("2025-01-01"),
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

    scan_summary = run_market_scan_workflow(scan_dependencies, tmp_path / "scan", top_n=2, plot=False).to_summary()
    backtest_summary = run_market_backtest_workflow(
        backtest_dependencies,
        tmp_path / "backtest",
        top_n=2,
        lookback_days=20,
        rebalance="static",
    ).to_summary()
    symbol_summary = run_symbol_analysis_workflow(
        symbol_dependencies,
        symbol="AAA",
        start_date=None,
        end_date=None,
    ).to_summary()

    required_shared_keys = {"workflow", "execution_id"}
    assert required_shared_keys.issubset(scan_summary)
    assert required_shared_keys.issubset(backtest_summary)
    assert required_shared_keys.issubset(symbol_summary)


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


def test_build_symbol_signal_row_returns_none_for_missing_history() -> None:
    """Symbol row builder should skip symbols with no historical rows."""
    result = build_symbol_signal_row(
        symbol="AAA",
        history=pd.DataFrame(),
        bluechip_ranked=pd.DataFrame({"symbol": ["AAA"], "bluechip_score": [0.9]}),
        add_indicators_fn=lambda frame: frame,
        detect_patterns_fn=lambda _df: [],
        build_trade_signal_fn=lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            signal="BUY", confidence=0.9, indicators={}, patterns={}
        ),
    )

    assert result is None


def test_build_symbol_signal_row_builds_expected_payload() -> None:
    """Symbol row builder should produce the signal payload for one symbol."""
    history = _build_history("AAA", 100.0).head(5).copy()

    result = build_symbol_signal_row(
        symbol="AAA",
        history=history,
        bluechip_ranked=pd.DataFrame({"symbol": ["AAA"], "bluechip_score": [0.88]}),
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
            signal="BUY", confidence=0.9, indicators={"ema20": 1.0}, patterns={}
        ),
    )

    assert result is not None
    assert result["symbol"] == "AAA"
    assert result["signal"] == "BUY"
    assert result["confidence"] == 0.9
    assert result["bluechip_score"] == round(0.88, 4)


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


def test_fetch_historical_universe_logs_completion(caplog) -> None:
    """Historical universe fetch should log completion metadata."""
    coordinator = _coordinator()

    with caplog.at_level("INFO"):
        historical_universe = fetch_historical_universe(
            coordinator,
            execution_id="test-exec",
            workflow_name="market_scan",
        )

    assert set(historical_universe.keys()) == {"AAA", "BBB"}
    assert '"event": "fetch_historical_universe_completed"' in caplog.text


def test_fetch_historical_universe_classifies_validation_errors() -> None:
    """Historical universe fetch should classify malformed payloads as validation failures."""
    coordinator = _coordinator()
    coordinator.get_universe_with_history = lambda lookback_years=5, force_refresh=False: {
        "AAA": pd.DataFrame({"date": pd.date_range("2025-01-01", periods=3), "close": [1.0, 2.0, 3.0]})
    }

    with pytest.raises(WorkflowValidationError, match="missing columns") as exc_info:
        fetch_historical_universe(
            coordinator,
            execution_id="test-exec",
            workflow_name="market_scan",
        )

    assert exc_info.value.stage == "fetch"


def test_market_scan_workflow_logs_stage_completion_metadata(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Market scan should emit structured stage completion logs with symbol scope metadata."""
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

    with caplog.at_level("INFO"):
        run_market_scan_workflow(dependencies, tmp_path, top_n=2, plot=False)

    assert '"event": "stage_completed"' in caplog.text
    assert '"stage": "fetch"' in caplog.text
    assert '"stage": "scan"' in caplog.text
    assert '"stage": "score"' in caplog.text
    assert '"stage": "rank"' in caplog.text
    assert '"symbol_scope"' in caplog.text


def test_market_scan_workflow_logs_stage_failure_metadata(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Market scan should emit structured stage failure logs with category and symbol scope."""
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

    with caplog.at_level("INFO"):
        with pytest.raises(WorkflowRankingError):
            run_market_scan_workflow(dependencies, tmp_path, top_n=2, plot=False)

    assert '"event": "stage_failed"' in caplog.text
    assert '"stage": "rank"' in caplog.text
    assert '"category": "ranking"' in caplog.text
    assert '"symbol_scope"' in caplog.text
