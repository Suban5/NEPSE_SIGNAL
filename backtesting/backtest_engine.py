"""Backtesting engine for evaluating signal strategy performance."""

from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    """Key performance metrics from backtesting."""

    cagr: float
    max_drawdown: float
    win_rate: float
    sharpe_ratio: float


@dataclass(frozen=True)
class PortfolioBacktestResult:
    """Portfolio-level backtest metrics for market-wide signals."""

    symbols_count: int
    cagr: float
    max_drawdown: float
    sharpe_ratio: float
    total_return: float


def run_backtest(df: pd.DataFrame, signal_column: str = "signal") -> BacktestResult:
    """Run long-only daily backtest using discrete BUY/SELL/HOLD signals.

    Strategy assumptions:
    - BUY means hold from next day until SELL.
    - SELL means move to cash.
    - HOLD preserves current position.
    """
    if df.empty or signal_column not in df.columns or "close" not in df.columns:
        return BacktestResult(cagr=0.0, max_drawdown=0.0, win_rate=0.0, sharpe_ratio=0.0)

    out = df.copy().sort_values("date").reset_index(drop=True)
    out["returns"] = out["close"].pct_change().fillna(0.0)

    position = 0
    positions = []
    for signal in out[signal_column].astype(str).str.upper():
        if signal == "BUY":
            position = 1
        elif signal == "SELL":
            position = 0
        positions.append(position)
    out["position"] = positions
    out["strategy_returns"] = out["position"].shift(1).fillna(0.0) * out["returns"]

    equity = (1 + out["strategy_returns"]).cumprod()
    total_periods = max(len(out) - 1, 1)
    years = total_periods / 252
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0

    rolling_max = equity.cummax()
    drawdown = (equity / rolling_max) - 1
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

    trade_returns = out.loc[out["position"].diff().fillna(0) != 0, "strategy_returns"]
    wins = (trade_returns > 0).sum()
    total_trades = max(len(trade_returns), 1)
    win_rate = float(wins / total_trades)

    mean_return = out["strategy_returns"].mean()
    std_return = out["strategy_returns"].std(ddof=0)
    sharpe_ratio = float((mean_return / std_return) * math.sqrt(252)) if std_return > 0 else 0.0

    return BacktestResult(
        cagr=round(cagr, 6),
        max_drawdown=round(max_drawdown, 6),
        win_rate=round(win_rate, 6),
        sharpe_ratio=round(sharpe_ratio, 6),
    )


def run_portfolio_backtest(
    historical_universe: dict[str, pd.DataFrame],
    selected_symbols: list[str],
    lookback_days: int = 252,
    rebalance: str = "static",
) -> PortfolioBacktestResult:
    """Backtest equal-weight portfolio from selected symbols.

    Args:
        historical_universe: Mapping from symbol to OHLCV DataFrame.
        selected_symbols: Symbols included in portfolio.
        lookback_days: Number of trailing trading days to evaluate.
        rebalance: Rebalance mode: static, weekly, monthly.

    Returns:
        PortfolioBacktestResult with return and risk metrics.
    """
    if not selected_symbols:
        return PortfolioBacktestResult(
            symbols_count=0,
            cagr=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            total_return=0.0,
        )

    returns_frames: list[pd.Series] = []
    for symbol in selected_symbols:
        history = historical_universe.get(symbol)
        if history is None or history.empty:
            continue
        frame = history[["date", "close"]].copy().sort_values("date")
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date", "close"]).tail(lookback_days)
        if len(frame) < 2:
            continue
        series = frame.set_index("date")["close"].pct_change().rename(symbol)
        returns_frames.append(series)

    if not returns_frames:
        return PortfolioBacktestResult(
            symbols_count=0,
            cagr=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            total_return=0.0,
        )

    returns_df = pd.concat(returns_frames, axis=1).sort_index().fillna(0.0)
    portfolio_returns = _build_portfolio_returns(returns_df, rebalance=rebalance)
    equity = (1 + portfolio_returns).cumprod()

    total_periods = max(len(portfolio_returns), 1)
    years = total_periods / 252
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0

    rolling_max = equity.cummax()
    drawdown = (equity / rolling_max) - 1
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

    mean_return = portfolio_returns.mean()
    std_return = portfolio_returns.std(ddof=0)
    sharpe_ratio = float((mean_return / std_return) * math.sqrt(252)) if std_return > 0 else 0.0
    total_return = float(equity.iloc[-1] - 1)

    return PortfolioBacktestResult(
        symbols_count=len(returns_df.columns),
        cagr=round(cagr, 6),
        max_drawdown=round(max_drawdown, 6),
        sharpe_ratio=round(sharpe_ratio, 6),
        total_return=round(total_return, 6),
    )


def _build_portfolio_returns(returns_df: pd.DataFrame, rebalance: str) -> pd.Series:
    """Build portfolio returns series based on rebalance mode.

    Args:
        returns_df: DataFrame of symbol returns indexed by date.
        rebalance: static, weekly, or monthly.

    Returns:
        Portfolio return series.
    """
    mode = rebalance.lower().strip()
    if mode == "static":
        return returns_df.mean(axis=1)

    if mode not in {"weekly", "monthly"}:
        raise ValueError("rebalance must be one of: static, weekly, monthly")

    index = pd.to_datetime(returns_df.index)
    if mode == "weekly":
        periods = index.to_period("W")
    else:
        periods = index.to_period("M")

    portfolio_returns = pd.Series(index=returns_df.index, dtype=float)
    for _, period_idx in returns_df.groupby(periods).groups.items():
        block = returns_df.loc[period_idx]
        if block.empty:
            continue
        weights = pd.Series(1.0 / block.shape[1], index=block.columns)
        block_returns = block.mul(weights, axis=1).sum(axis=1)
        portfolio_returns.loc[block.index] = block_returns.values

    return portfolio_returns.fillna(0.0)
