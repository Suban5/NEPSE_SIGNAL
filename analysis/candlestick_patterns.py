from __future__ import annotations

"""Candlestick pattern detection utilities."""

from typing import Dict

import pandas as pd


def _body(candle: pd.Series) -> float:
    """Return candle body size."""
    return abs(float(candle["close"]) - float(candle["open"]))


def _range(candle: pd.Series) -> float:
    """Return candle high-low range."""
    return max(float(candle["high"]) - float(candle["low"]), 1e-9)


def _is_bullish(candle: pd.Series) -> bool:
    """Return True if candle is bullish."""
    return float(candle["close"]) > float(candle["open"])


def _is_bearish(candle: pd.Series) -> bool:
    """Return True if candle is bearish."""
    return float(candle["close"]) < float(candle["open"])


def detect_latest_patterns(df: pd.DataFrame) -> Dict[str, bool]:
    """Detect patterns using latest candles in OHLC data.

    Args:
        df: OHLC DataFrame.

    Returns:
        Mapping of supported pattern names to detection booleans.
    """
    patterns = {
        "bullish_engulfing": False,
        "bearish_engulfing": False,
        "hammer": False,
        "shooting_star": False,
        "doji": False,
        "morning_star": False,
        "evening_star": False,
    }
    if len(df) < 3:
        return patterns

    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

    patterns["bullish_engulfing"] = (
        _is_bearish(c2)
        and _is_bullish(c3)
        and float(c3["open"]) <= float(c2["close"])
        and float(c3["close"]) >= float(c2["open"])
    )

    patterns["bearish_engulfing"] = (
        _is_bullish(c2)
        and _is_bearish(c3)
        and float(c3["open"]) >= float(c2["close"])
        and float(c3["close"]) <= float(c2["open"])
    )

    c3_body = _body(c3)
    c3_range = _range(c3)
    upper_shadow = float(c3["high"]) - max(float(c3["open"]), float(c3["close"]))
    lower_shadow = min(float(c3["open"]), float(c3["close"])) - float(c3["low"])

    patterns["doji"] = c3_body / c3_range <= 0.1
    patterns["hammer"] = lower_shadow >= 2 * c3_body and upper_shadow <= c3_body
    patterns["shooting_star"] = upper_shadow >= 2 * c3_body and lower_shadow <= c3_body

    small_c2 = _body(c2) / _range(c2) <= 0.3
    patterns["morning_star"] = _is_bearish(c1) and small_c2 and _is_bullish(c3) and float(c3["close"]) > (
        float(c1["open"]) + float(c1["close"])
    ) / 2
    patterns["evening_star"] = _is_bullish(c1) and small_c2 and _is_bearish(c3) and float(c3["close"]) < (
        float(c1["open"]) + float(c1["close"])
    ) / 2

    return patterns
