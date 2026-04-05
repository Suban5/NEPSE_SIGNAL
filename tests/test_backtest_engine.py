"""Tests for the backtesting engine."""

from __future__ import annotations

import pandas as pd

from backtesting.backtest_engine import run_backtest, run_portfolio_backtest


def test_run_backtest_returns_metrics() -> None:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=6, freq="D"),
            "close": [100.0, 101.0, 102.0, 101.0, 103.0, 104.0],
            "signal": ["BUY", "HOLD", "HOLD", "SELL", "BUY", "HOLD"],
        }
    )
    result = run_backtest(df)
    assert isinstance(result.cagr, float)
    assert isinstance(result.max_drawdown, float)
    assert isinstance(result.win_rate, float)
    assert isinstance(result.sharpe_ratio, float)


def test_run_backtest_handles_empty_frame() -> None:
    result = run_backtest(pd.DataFrame())
    assert result.cagr == 0.0
    assert result.max_drawdown == 0.0
    assert result.win_rate == 0.0
    assert result.sharpe_ratio == 0.0


def test_run_portfolio_backtest_returns_metrics() -> None:
    historical_universe = {
        "AAA": pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=10, freq="D"),
                "close": [100, 101, 102, 101, 103, 104, 105, 106, 105, 107],
            }
        ),
        "BBB": pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=10, freq="D"),
                "close": [200, 199, 201, 202, 203, 201, 204, 205, 206, 207],
            }
        ),
    }
    result = run_portfolio_backtest(historical_universe, ["AAA", "BBB"], lookback_days=10)
    assert result.symbols_count == 2
    assert isinstance(result.cagr, float)
    assert isinstance(result.max_drawdown, float)
    assert isinstance(result.sharpe_ratio, float)
    assert isinstance(result.total_return, float)


def test_run_portfolio_backtest_supports_rebalance_modes() -> None:
    historical_universe = {
        "AAA": pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=40, freq="D"),
                "close": [100 + i for i in range(40)],
            }
        ),
        "BBB": pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=40, freq="D"),
                "close": [200 + (i * 0.5) for i in range(40)],
            }
        ),
    }
    weekly = run_portfolio_backtest(historical_universe, ["AAA", "BBB"], lookback_days=40, rebalance="weekly")
    monthly = run_portfolio_backtest(historical_universe, ["AAA", "BBB"], lookback_days=40, rebalance="monthly")
    assert weekly.symbols_count == 2
    assert monthly.symbols_count == 2
    assert isinstance(weekly.total_return, float)
    assert isinstance(monthly.total_return, float)


def test_run_portfolio_backtest_invalid_rebalance_raises() -> None:
    historical_universe = {
        "AAA": pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=10, freq="D"),
                "close": [100 + i for i in range(10)],
            }
        )
    }
    try:
        run_portfolio_backtest(historical_universe, ["AAA"], lookback_days=10, rebalance="daily")
    except ValueError as exc:
        assert "rebalance must be one of" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid rebalance")
