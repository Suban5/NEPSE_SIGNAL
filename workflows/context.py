"""Typed workflow context objects and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


VALID_REBALANCE_MODES = {"static", "weekly", "monthly"}


@dataclass(frozen=True)
class MarketScanContext:
    """Artifacts produced during the market scan workflow."""

    output_dir: Path
    top_n: int
    plot: bool
    snapshot: pd.DataFrame
    historical_universe: Dict[str, pd.DataFrame]
    symbols: List[str]
    filtered_history: Dict[str, pd.DataFrame]
    bluechip_ranked: pd.DataFrame
    signal_df: pd.DataFrame
    execution_id: str = ""

    def to_summary(self) -> Dict[str, Any]:
        """Return a standardized summary for CLI and benchmark output."""
        return {
            "workflow": "market_scan",
            "execution_id": self.execution_id,
            "output_dir": str(self.output_dir),
            "top_n": int(self.top_n),
            "plot": bool(self.plot),
            "snapshot_rows": int(len(self.snapshot)),
            "universe_symbols": int(len(self.symbols)),
            "selected_symbols": int(min(self.top_n, len(self.bluechip_ranked))),
            "signal_rows": int(len(self.signal_df)),
        }


@dataclass(frozen=True)
class MarketBacktestContext:
    """Artifacts produced during the portfolio backtest workflow."""

    output_dir: Path
    top_n: int
    lookback_days: int
    rebalance: str
    snapshot: pd.DataFrame
    historical_universe: Dict[str, pd.DataFrame]
    symbols: List[str]
    filtered_history: Dict[str, pd.DataFrame]
    bluechip_ranked: pd.DataFrame
    signal_df: pd.DataFrame
    selected_buy_symbols: List[str]
    execution_id: str = ""

    def to_summary(self) -> Dict[str, Any]:
        """Return a standardized summary for CLI and benchmark output."""
        return {
            "workflow": "market_backtest",
            "execution_id": self.execution_id,
            "output_dir": str(self.output_dir),
            "top_n": int(self.top_n),
            "lookback_days": int(self.lookback_days),
            "rebalance": self.rebalance,
            "snapshot_rows": int(len(self.snapshot)),
            "universe_symbols": int(len(self.symbols)),
            "selected_symbols": int(min(self.top_n, len(self.bluechip_ranked))),
            "buy_symbols": int(len(self.selected_buy_symbols)),
            "signal_rows": int(len(self.signal_df)),
        }


@dataclass(frozen=True)
class SymbolAnalysisContext:
    """Artifacts produced during a single-symbol analysis workflow."""

    symbol: str
    history: pd.DataFrame
    snapshot: pd.DataFrame
    feature_df: pd.DataFrame
    bluechip_score: float
    technical_df: pd.DataFrame
    signal: Any
    backtest: Any
    execution_id: str = ""

    def to_summary(self) -> Dict[str, Any]:
        """Return a standardized summary for CLI output."""
        return {
            "workflow": "symbol_analysis",
            "execution_id": self.execution_id,
            "symbol": self.symbol,
            "history_rows": int(len(self.history)),
            "bluechip_score": float(self.bluechip_score),
            "signal": getattr(self.signal, "signal", None),
            "confidence": getattr(self.signal, "confidence", None),
            "backtest_cagr": getattr(self.backtest, "cagr", None),
            "backtest_sharpe_ratio": getattr(self.backtest, "sharpe_ratio", None),
        }


def validate_snapshot(snapshot: pd.DataFrame) -> None:
    """Validate snapshot payload before downstream processing."""
    if snapshot.empty:
        raise RuntimeError("No market snapshot data retrieved.")
    if "symbol" not in snapshot.columns:
        raise ValueError("Snapshot data must include a 'symbol' column")


def validate_historical_universe(historical_universe: Dict[str, pd.DataFrame]) -> None:
    """Validate the historical universe mapping before downstream processing."""
    if not historical_universe:
        raise RuntimeError("No historical data found for the market universe.")

    required_columns = {"date", "close", "volume"}
    for symbol, history in historical_universe.items():
        if history.empty:
            continue
        missing = required_columns - set(history.columns)
        if missing:
            raise ValueError(f"Historical data for {symbol} is missing columns: {sorted(missing)}")


def validate_symbol(symbol: Optional[str]) -> str:
    """Validate a symbol input and normalize it."""
    if not symbol:
        raise ValueError("--symbol is required for single-stock analysis")
    normalized = str(symbol).upper().strip()
    if not normalized.isalnum():
        raise ValueError("Symbol must be alphanumeric")
    return normalized


def validate_positive_int(value: Any, field_name: str, minimum: int = 1) -> int:
    """Validate that a numeric input is an integer greater than or equal to a minimum."""
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc

    if normalized < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return normalized


def validate_rebalance_mode(rebalance: str) -> str:
    """Validate the portfolio rebalance mode."""
    normalized = str(rebalance).strip().lower()
    if normalized not in VALID_REBALANCE_MODES:
        raise ValueError(f"rebalance must be one of {sorted(VALID_REBALANCE_MODES)}")
    return normalized
