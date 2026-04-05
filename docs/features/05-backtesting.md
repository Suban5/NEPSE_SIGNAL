# Feature 05: Backtesting

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: backtesting/backtest_engine.py, workflows/market_backtest.py, tests/test_backtest_engine.py
Validation Method: Code + Tests

## Purpose

Evaluate signal-based strategy performance for single-series and market-portfolio scenarios.

## Verified APIs

- run_backtest(df, signal_column='signal') -> BacktestResult
- run_portfolio_backtest(historical_universe, selected_symbols, lookback_days=252, rebalance='static') -> PortfolioBacktestResult

## BacktestResult Fields

- cagr
- max_drawdown
- win_rate
- sharpe_ratio

## PortfolioBacktestResult Fields

- symbols_count
- cagr
- max_drawdown
- sharpe_ratio
- total_return

## Example

```python
from backtesting.backtest_engine import run_backtest

result = run_backtest(signal_frame, signal_column="signal")
```
