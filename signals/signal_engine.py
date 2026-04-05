"""Signal generation engine combining indicators and candlestick patterns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

import pandas as pd

from analysis.signal_engine import generate_signal
from candlestick.patterns import PatternResult


@dataclass(frozen=True)
class TradeSignal:
    """Trading signal output contract."""

    symbol: str
    signal: str
    confidence: float
    indicators: Dict[str, float]
    timestamp: datetime


def build_trade_signal(
    symbol: str,
    technical_df: pd.DataFrame,
    pattern_results: List[PatternResult],
    bluechip_score: float,
) -> TradeSignal:
    """Build final trading signal object."""
    pattern_map = {
        "bullish_engulfing": False,
        "bearish_engulfing": False,
        "hammer": False,
        "shooting_star": False,
        "doji": False,
        "morning_star": False,
        "evening_star": False,
    }
    for result in pattern_results:
        if result.pattern_name in pattern_map:
            pattern_map[result.pattern_name] = True

    signal_result = generate_signal(symbol, technical_df, pattern_map, bluechip_score)
    timestamp = (
        pd.to_datetime(technical_df.iloc[-1]["date"]).to_pydatetime()
        if not technical_df.empty
        else datetime.utcnow()
    )
    return TradeSignal(
        symbol=symbol,
        signal=signal_result.signal,
        confidence=signal_result.confidence,
        indicators=signal_result.details,
        timestamp=timestamp,
    )
