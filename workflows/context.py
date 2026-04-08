"""Typed workflow context objects and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


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
