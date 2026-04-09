"""Tests for structured candlestick pattern adapter module."""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from types import SimpleNamespace

import pandas as pd
import pytest

from candlestick.patterns import PatternResult, detect_patterns


def test_pattern_result_is_frozen_dataclass() -> None:
    """PatternResult should be immutable."""
    result = PatternResult("hammer", 0.5, datetime(2024, 1, 1))
    with pytest.raises(AttributeError):
        result.pattern_name = "doji"  # type: ignore[misc]


def test_detect_patterns_returns_empty_when_no_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    """False-only detector output should map to empty results."""
    monkeypatch.setattr(
        "candlestick.patterns.detect_latest_patterns",
        lambda df: {
            "hammer": False,
            "doji": False,
        },
    )
    df = pd.DataFrame({"date": ["2024-01-01"], "close": [100]})

    assert detect_patterns(df) == []


def test_detect_patterns_maps_detected_patterns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detected flags should map to PatternResult rows in order."""
    monkeypatch.setattr(
        "candlestick.patterns.detect_latest_patterns",
        lambda df: {
            "hammer": True,
            "doji": False,
            "bullish_engulfing": True,
        },
    )
    df = pd.DataFrame({"date": ["2024-01-01"], "close": [100]})

    results = detect_patterns(df)

    assert [row.pattern_name for row in results] == ["hammer", "bullish_engulfing"]


def test_detect_patterns_uses_higher_strength_for_engulfing_and_star(monkeypatch: pytest.MonkeyPatch) -> None:
    """Engulfing/star patterns should receive strength 0.7; others 0.5."""
    monkeypatch.setattr(
        "candlestick.patterns.detect_latest_patterns",
        lambda df: {
            "bullish_engulfing": True,
            "evening_star": True,
            "doji": True,
        },
    )
    df = pd.DataFrame({"date": ["2024-01-01"], "close": [100]})

    strengths = {row.pattern_name: row.strength for row in detect_patterns(df)}

    assert strengths["bullish_engulfing"] == 0.7
    assert strengths["evening_star"] == 0.7
    assert strengths["doji"] == 0.5


def test_detect_patterns_uses_last_row_date_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timestamp should be parsed from last date row when DataFrame not empty."""
    monkeypatch.setattr(
        "candlestick.patterns.detect_latest_patterns",
        lambda df: {"hammer": True},
    )
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02T13:25:40"],
            "close": [100, 101],
        }
    )

    result = detect_patterns(df)[0]

    assert result.timestamp == datetime(2024, 1, 2, 13, 25, 40)


def test_detect_patterns_uses_current_utc_when_df_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty DataFrame should fallback to current UTC timestamp."""
    monkeypatch.setattr(
        "candlestick.patterns.detect_latest_patterns",
        lambda df: {"hammer": True},
    )

    fixed_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    import candlestick.patterns as module

    class _FrozenDatetime:
        @staticmethod
        def now(tz: tzinfo | None = None) -> datetime:
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(module, "datetime", _FrozenDatetime)

    result = detect_patterns(pd.DataFrame())[0]

    assert result.timestamp == fixed_now


def test_detect_patterns_calls_detector_with_input_df(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter should delegate source DataFrame to detector function."""
    captured = SimpleNamespace(df=None)

    def _fake_detect(df: pd.DataFrame) -> dict[str, bool]:
        captured.df = df
        return {"hammer": True}

    monkeypatch.setattr("candlestick.patterns.detect_latest_patterns", _fake_detect)

    frame = pd.DataFrame({"date": ["2024-01-01"], "close": [100]})
    detect_patterns(frame)

    assert captured.df is frame
