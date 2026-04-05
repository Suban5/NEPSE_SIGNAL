from __future__ import annotations

"""Technical indicator calculations."""

import numpy as np
import pandas as pd


REQUIRED_OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def _validate_ohlcv_frame(df: pd.DataFrame) -> None:
    """Validate required OHLCV columns.

    Args:
        df: Input market data frame.

    Raises:
        ValueError: If required columns are missing.
    """
    missing = [col for col in REQUIRED_OHLCV_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required OHLCV columns: {missing}")


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators to OHLCV DataFrame.

    Args:
        df: OHLCV data with date and price/volume columns.

    Returns:
        DataFrame with indicator columns.
    """
    _validate_ohlcv_frame(df)
    out = df.copy().sort_values("date").reset_index(drop=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date", "close"]).reset_index(drop=True)

    out["sma20"] = out["close"].rolling(20).mean()
    out["sma50"] = out["close"].rolling(50).mean()
    out["sma200"] = out["close"].rolling(200).mean()

    out["ema12"] = out["close"].ewm(span=12, adjust=False).mean()
    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema26"] = out["close"].ewm(span=26, adjust=False).mean()

    out["rsi14"] = _rsi(out["close"], period=14)

    out["macd"] = out["ema12"] - out["ema26"]
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]

    rolling_std = out["close"].rolling(20).std()
    out["bb_mid"] = out["sma20"]
    out["bb_upper"] = out["bb_mid"] + (2 * rolling_std)
    out["bb_lower"] = out["bb_mid"] - (2 * rolling_std)

    out["volume_sma20"] = out["volume"].rolling(20).mean()
    out["volume_trend"] = out["volume"] / out["volume_sma20"].replace(0, np.nan)

    return out
