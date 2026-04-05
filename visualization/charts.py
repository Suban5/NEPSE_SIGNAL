from __future__ import annotations

"""Chart rendering utilities for OHLC and indicators."""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd


logger = logging.getLogger(__name__)


def save_mplfinance_chart(df: pd.DataFrame, symbol: str, output_dir: str) -> Optional[Path]:
    """Render and save mplfinance candlestick chart.

    Args:
        df: DataFrame with OHLC data and optional indicators.
        symbol: Stock symbol.
        output_dir: Output directory path.

    Returns:
        Saved image path if mplfinance is available; otherwise None.
    """
    try:
        import mplfinance as mpf
    except ImportError:
        logger.warning("mplfinance is not installed. Skipping PNG chart for %s", symbol)
        return None

    chart_df = df.copy()
    chart_df = chart_df.set_index("date")
    chart_df.index = pd.to_datetime(chart_df.index)
    chart_df = chart_df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )

    addplots = []
    for col in ["sma20", "sma50", "sma200"]:
        if col in df.columns:
            addplots.append(mpf.make_addplot(df[col].values, panel=0))

    out_path = Path(output_dir) / f"{symbol}_candlestick.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mpf.plot(
        chart_df,
        type="candle",
        volume=True,
        style="charles",
        addplot=addplots if addplots else None,
        savefig=str(out_path),
        title=f"{symbol} Candlestick + SMA",
    )
    return out_path


def save_plotly_chart(df: pd.DataFrame, symbol: str, output_dir: str) -> Optional[Path]:
    """Render and save Plotly candlestick chart.

    Args:
        df: DataFrame with OHLC data and optional indicators.
        symbol: Stock symbol.
        output_dir: Output directory path.

    Returns:
        Saved HTML path if plotly is available; otherwise None.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        logger.warning("plotly is not installed. Skipping HTML chart for %s", symbol)
        return None

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df["date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="OHLC",
            )
        ]
    )
    for col in ["sma20", "sma50", "sma200", "ema20"]:
        if col in df.columns:
            fig.add_scatter(x=df["date"], y=df[col], mode="lines", name=col.upper())

    fig.update_layout(
        title=f"{symbol} Candlestick + Indicators",
        xaxis_title="Date",
        yaxis_title="Price",
        template="plotly_dark",
    )

    out_path = Path(output_dir) / f"{symbol}_candlestick.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path), include_plotlyjs="cdn")
    return out_path
