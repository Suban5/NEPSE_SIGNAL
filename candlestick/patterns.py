"""Candlestick pattern detection engine with structured output."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

import pandas as pd

from analysis.candlestick_patterns import detect_latest_patterns


@dataclass(frozen=True)
class PatternResult:
    """Structured candlestick pattern output."""

    pattern_name: str
    strength: float
    timestamp: datetime


def detect_patterns(df: pd.DataFrame) -> List[PatternResult]:
    """Detect latest candlestick patterns and map to structured results."""
    detected = detect_latest_patterns(df)
    timestamp = pd.to_datetime(df.iloc[-1]["date"]).to_pydatetime() if not df.empty else datetime.utcnow()
    results: List[PatternResult] = []
    for pattern_name, is_detected in detected.items():
        if is_detected:
            strength = 0.7 if "engulfing" in pattern_name or "star" in pattern_name else 0.5
            results.append(PatternResult(pattern_name=pattern_name, strength=strength, timestamp=timestamp))
    return results
