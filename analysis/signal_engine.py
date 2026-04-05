from __future__ import annotations

"""Trading signal generation from technicals and patterns."""

from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class SignalResult:
    """Output object for generated trading signal."""

    symbol: str
    signal: str
    confidence: float
    details: Dict[str, float]


def _crossed_above(series_a: pd.Series, series_b: pd.Series) -> bool:
    """Return True when series_a crosses above series_b on latest bar."""
    if len(series_a) < 2 or len(series_b) < 2:
        return False
    return bool(series_a.iloc[-2] <= series_b.iloc[-2] and series_a.iloc[-1] > series_b.iloc[-1])


def _crossed_below(series_a: pd.Series, series_b: pd.Series) -> bool:
    """Return True when series_a crosses below series_b on latest bar."""
    if len(series_a) < 2 or len(series_b) < 2:
        return False
    return bool(series_a.iloc[-2] >= series_b.iloc[-2] and series_a.iloc[-1] < series_b.iloc[-1])


def generate_signal(symbol: str, df: pd.DataFrame, patterns: Dict[str, bool], bluechip_score: float) -> SignalResult:
    """Generate BUY/SELL/HOLD signal for a stock.

    Args:
        symbol: Stock symbol.
        df: Technical DataFrame with indicator columns.
        patterns: Candlestick detection flags.
        bluechip_score: Blue-chip strength score in [0, 1].

    Returns:
        SignalResult with confidence and indicator snapshot.
    """
    required_columns = ["close", "sma50", "volume", "volume_sma20"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required signal columns: {missing}")
    if len(df) < 2:
        raise ValueError("At least 2 rows are required for crossover detection")

    latest = df.iloc[-1]
    rsi = float(latest.get("rsi14", 50.0))
    close_series = df["close"]
    sma50_series = df["sma50"]

    bullish_patterns = any(
        [
            patterns.get("bullish_engulfing", False),
            patterns.get("hammer", False),
            patterns.get("morning_star", False),
        ]
    )
    bearish_patterns = any(
        [
            patterns.get("bearish_engulfing", False),
            patterns.get("shooting_star", False),
            patterns.get("evening_star", False),
        ]
    )

    volume_up = bool(
        latest.get("volume", 0) > latest.get("volume_sma20", 0)
        and latest.get("volume", 0) > df.iloc[-2].get("volume", 0)
    )

    buy_conditions = {
        "rsi_low": rsi < 45,
        "price_cross_above_sma50": _crossed_above(close_series, sma50_series),
        "bullish_pattern": bullish_patterns,
        "volume_increasing": volume_up,
    }

    sell_conditions = {
        "rsi_high": rsi > 70,
        "price_cross_below_sma50": _crossed_below(close_series, sma50_series),
        "bearish_pattern": bearish_patterns,
    }

    buy_score = sum(buy_conditions.values()) / len(buy_conditions)
    sell_score = sum(sell_conditions.values()) / len(sell_conditions)

    if buy_score >= 0.5:
        signal = "BUY"
        confidence = min(1.0, 0.6 * buy_score + 0.4 * bluechip_score)
    elif sell_score >= 0.67:
        signal = "SELL"
        confidence = min(1.0, 0.7 * sell_score + 0.3 * (1 - bluechip_score))
    else:
        signal = "HOLD"
        confidence = min(1.0, 0.5 + abs(buy_score - sell_score) * 0.2)

    details = {
        "close": float(latest.get("close", 0.0)),
        "rsi14": rsi,
        "sma20": float(latest.get("sma20", 0.0)),
        "sma50": float(latest.get("sma50", 0.0)),
        "sma200": float(latest.get("sma200", 0.0)),
        "ema20": float(latest.get("ema20", 0.0)),
        "macd": float(latest.get("macd", 0.0)),
        "macd_signal": float(latest.get("macd_signal", 0.0)),
        "bb_upper": float(latest.get("bb_upper", 0.0)),
        "bb_lower": float(latest.get("bb_lower", 0.0)),
        "volume_trend": float(latest.get("volume_trend", 0.0)),
    }

    return SignalResult(
        symbol=symbol,
        signal=signal,
        confidence=round(confidence, 4),
        details=details,
    )
