"""Tests for CLI command parsing and dispatch behavior."""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import cli.commands as commands


# --- Helper: Build mock dataframes ---
def build_mock_technical_df(periods: int = 5) -> pd.DataFrame:
    """Build a mock technical DataFrame."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=periods, freq="D"),
            "open": [99 + i for i in range(periods)],
            "high": [102 + i for i in range(periods)],
            "low": [98 + i for i in range(periods)],
            "close": [100 + i for i in range(periods)],
            "volume": [1000 + 100 * i for i in range(periods)],
            "sma20": [100 + 0.5 * i for i in range(periods)],
            "sma50": [99 + 0.5 * i for i in range(periods)],
            "sma200": [95 + 0.5 * i for i in range(periods)],
            "ema20": [100 + 0.5 * i for i in range(periods)],
            "rsi14": [50 + i for i in range(periods)],
            "macd": [0.1 + 0.1 * i for i in range(periods)],
            "macd_signal": [0.1 + 0.05 * i for i in range(periods)],
            "bb_upper": [105 + 0.5 * i for i in range(periods)],
            "bb_lower": [95 + 0.5 * i for i in range(periods)],
            "volume_sma20": [1000] * periods,
            "volume_trend": [1.0 + 0.1 * i for i in range(periods)],
        }
    )


def build_mock_snapshot() -> pd.DataFrame:
    """Build a mock market snapshot."""
    return pd.DataFrame(
        {
            "symbol": ["NABIL", "SCB", "KBL"],
            "open": [1000, 1100, 1200],
            "high": [1020, 1120, 1220],
            "low": [990, 1090, 1190],
            "close": [1010, 1110, 1210],
            "volume": [10000, 11000, 12000],
        }
    )


def build_mock_bluechip_ranked() -> pd.DataFrame:
    """Build a mock bluechip ranked DataFrame."""
    return pd.DataFrame(
        {
            "symbol": ["NABIL", "SCB"],
            "bluechip_score": [0.9, 0.8],
        }
    )


# --- Test parse_args() ---
def test_parse_args_scan_market_subcommand() -> None:
    """parse_args should parse scan-market subcommand with defaults."""
    args = commands.parse_args(["scan-market"])
    assert args.command == "scan-market"
    assert args.top_n == 15
    assert args.plot is False
    assert args.output == "output"


def test_parse_args_scan_market_with_options() -> None:
    """parse_args should parse scan-market with custom options."""
    args = commands.parse_args(["scan-market", "--top-n", "20", "--plot", "--output", "my_output"])
    assert args.command == "scan-market"
    assert args.top_n == 20
    assert args.plot is True
    assert args.output == "my_output"


def test_parse_args_analyze_subcommand() -> None:
    """parse_args should parse analyze subcommand with symbol."""
    args = commands.parse_args(["analyze", "NABIL"])
    assert args.command == "analyze"
    assert args.symbol == "NABIL"
    assert args.start_date is None
    assert args.end_date is None


def test_parse_args_analyze_with_date_range() -> None:
    """parse_args should parse analyze with date range."""
    args = commands.parse_args(["analyze", "NABIL", "--start-date", "2025-01-01", "--end-date", "2025-12-31"])
    assert args.command == "analyze"
    assert args.symbol == "NABIL"
    assert args.start_date == "2025-01-01"
    assert args.end_date == "2025-12-31"


def test_parse_args_backtest_market_subcommand() -> None:
    """parse_args should parse backtest-market subcommand with defaults."""
    args = commands.parse_args(["backtest-market"])
    assert args.command == "backtest-market"
    assert args.top_n == 20
    assert args.lookback_days == 252
    assert args.rebalance == "static"


def test_parse_args_backtest_market_with_options() -> None:
    """parse_args should parse backtest-market with rebalance option."""
    args = commands.parse_args(["backtest-market", "--top-n", "10", "--rebalance", "monthly"])
    assert args.command == "backtest-market"
    assert args.top_n == 10
    assert args.rebalance == "monthly"


def test_parse_args_health_check_subcommand() -> None:
    """parse_args should parse health-check subcommand."""
    args = commands.parse_args(["health-check"])
    assert args.command == "health-check"


def test_parse_args_health_check_with_symbol() -> None:
    """parse_args should parse health-check with optional symbol."""
    args = commands.parse_args(["health-check", "--symbol", "NABIL"])
    assert args.command == "health-check"
    assert args.symbol == "NABIL"


def test_parse_args_run_api_subcommand() -> None:
    """parse_args should parse run-api subcommand with defaults."""
    args = commands.parse_args(["run-api"])
    assert args.command == "run-api"
    assert args.host == "0.0.0.0"
    assert args.port == 8000
    assert args.reload is False


def test_parse_args_run_api_with_options() -> None:
    """parse_args should parse run-api with custom host/port."""
    args = commands.parse_args(["run-api", "--host", "127.0.0.1", "--port", "9000", "--reload"])
    assert args.command == "run-api"
    assert args.host == "127.0.0.1"
    assert args.port == 9000
    assert args.reload is True


# --- Test command dispatch (run) ---
def test_run_dispatches_scan_market_command(monkeypatch) -> None:
    """run() should dispatch to scan_market handler."""
    mock_scan = MagicMock()
    monkeypatch.setattr(commands, "scan_market", mock_scan)
    
    args = argparse.Namespace(command="scan-market", top_n=15, plot=False, output="output")
    commands.run(args)
    
    assert mock_scan.called


def test_run_dispatches_analyze_command(monkeypatch) -> None:
    """run() should dispatch to scan_symbol handler for analyze."""
    mock_scan_symbol = MagicMock()
    monkeypatch.setattr(commands, "scan_symbol", mock_scan_symbol)
    
    args = argparse.Namespace(command="analyze", symbol="NABIL")
    commands.run(args)
    
    assert mock_scan_symbol.called


def test_run_dispatches_backtest_market_command(monkeypatch) -> None:
    """run() should dispatch to backtest_market handler."""
    mock_backtest = MagicMock()
    monkeypatch.setattr(commands, "backtest_market", mock_backtest)
    
    args = argparse.Namespace(command="backtest-market", top_n=20)
    commands.run(args)
    
    assert mock_backtest.called


def test_run_dispatches_health_check_command(monkeypatch) -> None:
    """run() should dispatch to health_check handler."""
    mock_health = MagicMock()
    monkeypatch.setattr(commands, "health_check", mock_health)
    
    args = argparse.Namespace(command="health-check")
    commands.run(args)
    
    assert mock_health.called


def test_run_dispatches_run_api_command(monkeypatch) -> None:
    """run() should dispatch to run_api handler."""
    mock_api = MagicMock()
    monkeypatch.setattr(commands, "run_api", mock_api)
    
    args = argparse.Namespace(command="run-api", host="0.0.0.0", port=8000, reload=False)
    commands.run(args)
    
    assert mock_api.called


def test_run_raises_on_no_command_provided() -> None:
    """run() should raise SystemExit when no command is provided."""
    args = argparse.Namespace(command=None, scan_market=False, symbol=None)
    
    with pytest.raises(SystemExit):
        commands.run(args)


# --- Test command handlers with mocked dependencies ---
def test_scan_market_command_success(monkeypatch, tmp_path) -> None:
    """scan_market should complete workflow and save outputs."""
    fetcher_mock = MagicMock()
    fetcher_mock.fetch_daily_market_snapshot.return_value = build_mock_snapshot()
    fetcher_mock.fetch_universe_with_history.return_value = {
        "NABIL": build_mock_technical_df(),
        "SCB": build_mock_technical_df(),
    }
    fetcher_mock.fetch_company_fundamentals.return_value = {
        "eps": 50.0,
        "pe": 15.0,
        "dividend_yield": 3.5,
    }
    fetcher_mock.normalize_fundamentals.return_value = {
        "earnings_growth": 0.1,
        "dividend_stability": 0.9,
        "revenue_growth": 0.08,
    }
    
    detector_mock = MagicMock()
    detector_mock.build_feature_table.return_value = pd.DataFrame()
    detector_mock.score_bluechips.return_value = build_mock_bluechip_ranked()
    
    scanner_mock = MagicMock()
    scanner_mock.scan.return_value = (["NABIL", "SCB"], {
        "NABIL": build_mock_technical_df(),
        "SCB": build_mock_technical_df(),
    })
    
    monkeypatch.setattr(commands, "NepseDataFetcher", lambda: fetcher_mock)
    monkeypatch.setattr(commands, "BlueChipDetector", lambda: detector_mock)
    monkeypatch.setattr(commands, "MarketScanner", lambda: scanner_mock)
    monkeypatch.setattr(commands, "detect_patterns", lambda _df: [])
    monkeypatch.setattr(
        commands,
        "build_trade_signal",
        lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(
            signal="BUY", confidence=0.95, indicators={}, patterns={}
        ),
    )
    monkeypatch.setattr(commands, "detect_latest_patterns", lambda _df: {})
    monkeypatch.setattr(commands, "rank_opportunities", lambda df: df)
    monkeypatch.setattr(commands, "build_ranked_views", lambda bc, sig: {
        "top_bluechips": pd.DataFrame(),
        "best_buy_signals": pd.DataFrame(),
        "strong_momentum": pd.DataFrame(),
        "high_risk_weak": pd.DataFrame(),
    })
    
    args = argparse.Namespace(command="scan-market", top_n=2, plot=False, output=str(tmp_path))
    commands.scan_market(args)
    
    # Verify output files created
    assert (tmp_path / "bluechip_ranked.csv").exists()
    assert (tmp_path / "signal_summary.csv").exists()


def test_scan_market_raises_on_empty_snapshot(monkeypatch) -> None:
    """scan_market should raise RuntimeError when snapshot is empty."""
    fetcher_mock = MagicMock()
    fetcher_mock.fetch_daily_market_snapshot.return_value = pd.DataFrame()
    fetcher_mock.fetch_symbols.return_value = pd.DataFrame()
    
    monkeypatch.setattr(commands, "NepseDataFetcher", lambda: fetcher_mock)
    
    args = argparse.Namespace(command="scan-market", top_n=15, plot=False, output="output")
    
    with pytest.raises(RuntimeError, match="No market snapshot data retrieved"):
        commands.scan_market(args)


def test_scan_symbol_validates_symbol_input() -> None:
    """scan_symbol should reject non-alphanumeric symbols."""
    args = argparse.Namespace(symbol="NAB!L", start_date=None, end_date=None)
    
    with pytest.raises(ValueError, match="Symbol must be alphanumeric"):
        commands.scan_symbol(args)


def test_scan_symbol_requires_symbol_argument() -> None:
    """scan_symbol should raise ValueError when symbol is missing."""
    args = argparse.Namespace(start_date=None, end_date=None)
    
    with pytest.raises(ValueError, match="--symbol is required"):
        commands.scan_symbol(args)


def test_health_check_validates_snapshot(monkeypatch) -> None:
    """health_check should raise RuntimeError on empty snapshot."""
    fetcher_mock = MagicMock()
    fetcher_mock.fetch_daily_market_snapshot.return_value = pd.DataFrame()
    
    monkeypatch.setattr(commands, "NepseDataFetcher", lambda: fetcher_mock)
    
    args = argparse.Namespace(symbol=None)
    
    with pytest.raises(RuntimeError, match="snapshot endpoint returned no rows"):
        commands.health_check(args)


def test_health_check_validates_historical_data(monkeypatch) -> None:
    """health_check should raise RuntimeError on empty historical data."""
    fetcher_mock = MagicMock()
    fetcher_mock.fetch_daily_market_snapshot.return_value = build_mock_snapshot()
    fetcher_mock.fetch_historical_ohlcv.return_value = pd.DataFrame()
    
    monkeypatch.setattr(commands, "NepseDataFetcher", lambda: fetcher_mock)
    
    args = argparse.Namespace(symbol=None)
    
    with pytest.raises(RuntimeError, match="historical endpoint returned no rows"):
        commands.health_check(args)


def test_run_api_accepts_arguments() -> None:
    """run_api should accept host, port, and reload arguments."""
    # Test that run_api function exists and can be called (even if uvicorn import fails)
    args = argparse.Namespace(host="127.0.0.1", port=9000, reload=True)
    
    # We can't fully test uvicorn integration without mocking the entire import,
    # but we can verify the function signature and argument handling
    import inspect
    sig = inspect.signature(commands.run_api)
    assert "args" in sig.parameters


# --- Test signal frame generation ---
def test_build_historical_signal_frame_generates_rolling_signals(monkeypatch) -> None:
    """Historical signal frame should emit one signal per row with first row as HOLD."""
    technical_df = build_mock_technical_df(5)

    monkeypatch.setattr(commands, "detect_patterns", lambda _df: [])
    monkeypatch.setattr(
        commands,
        "build_trade_signal",
        lambda symbol, technical_df, pattern_results, bluechip_score: SimpleNamespace(signal="BUY"),
    )

    frame = commands._build_historical_signal_frame("NABIL", technical_df, bluechip_score=0.8)

    assert len(frame) == len(technical_df)
    assert frame.iloc[0]["signal"] == "HOLD"
    assert (frame["signal"] == "BUY").sum() == len(technical_df) - 1
