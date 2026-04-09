"""Tests for trade signal generation and output contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from candlestick.patterns import PatternResult
from signals.signal_engine import TradeSignal, build_trade_signal


def _build_full_technical_df() -> pd.DataFrame:
    """Create a complete technical DataFrame with all required columns for generate_signal."""
    return pd.DataFrame({
        "date": [pd.Timestamp("2024-01-15")],
        "close": [1000.0],
        "sma20": [999.0],
        "sma50": [998.0],
        "sma200": [997.0],
        "ema20": [1001.0],
        "rsi14": [45.0],
        "macd": [0.5],
        "macd_signal": [0.48],
        "bb_upper": [1010.0],
        "bb_lower": [990.0],
        "volume": [5000],
        "volume_sma20": [4500],
        "volume_trend": [1.1],
    })


# ============================================================================
# Tests for TradeSignal dataclass
# ============================================================================


def test_trade_signal_is_frozen_dataclass() -> None:
    """TradeSignal should be a frozen (immutable) dataclass."""
    signal = TradeSignal(
        symbol="NABIL",
        signal="BUY",
        confidence=0.75,
        indicators={"rsi": 45.0, "macd": 0.5},
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
    )
    # Attempting to modify should raise error due to frozen=True
    with pytest.raises(AttributeError):
        signal.symbol = "SBI"  # type: ignore


def test_trade_signal_has_required_fields() -> None:
    """TradeSignal should have all required fields."""
    timestamp = datetime(2024, 1, 15, 10, 30, 0)
    signal = TradeSignal(
        symbol="NABIL",
        signal="BUY",
        confidence=0.75,
        indicators={"rsi": 45.0},
        timestamp=timestamp,
    )
    assert signal.symbol == "NABIL"
    assert signal.signal == "BUY"
    assert signal.confidence == 0.75
    assert signal.indicators == {"rsi": 45.0}
    assert signal.timestamp == timestamp


# ============================================================================
# Tests for build_trade_signal() function
# ============================================================================


def test_build_trade_signal_basic_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should return TradeSignal with all fields populated."""
    technical_df = _build_full_technical_df()
    pattern_results: list[PatternResult] = []
    
    import signals.signal_engine as sig_module
    monkeypatch.setattr(sig_module, "generate_signal", lambda *args, **kw: SimpleNamespace(
        signal="BUY",
        confidence=0.75,
        details={"rsi": 45.0},
    ))
    
    signal = build_trade_signal(
        symbol="NABIL",
        technical_df=technical_df,
        pattern_results=pattern_results,
        bluechip_score=0.7,
    )
    
    assert isinstance(signal, TradeSignal)
    assert signal.symbol == "NABIL"
    assert signal.signal in ["BUY", "SELL", "HOLD"]
    assert 0.0 <= signal.confidence <= 1.0
    assert isinstance(signal.indicators, dict)
    assert isinstance(signal.timestamp, datetime)


def test_build_trade_signal_uses_symbol_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should use provided symbol."""
    technical_df = _build_full_technical_df()
    
    import signals.signal_engine as sig_module
    monkeypatch.setattr(sig_module, "generate_signal", lambda *args, **kw: SimpleNamespace(
        signal="BUY", confidence=0.7, details={},
    ))
    
    signal1 = build_trade_signal("NABIL", technical_df, [], 0.7)
    signal2 = build_trade_signal("SBI", technical_df, [], 0.7)
    
    assert signal1.symbol == "NABIL"
    assert signal2.symbol == "SBI"


def test_build_trade_signal_detects_bullish_engulfing_pattern() -> None:
    """build_trade_signal should set pattern_map for bullish_engulfing."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    pattern = PatternResult(
        pattern_name="bullish_engulfing",
        strength=0.8,
        timestamp=datetime(2024, 1, 15),
    )
    
    # Mock generate_signal to verify pattern_map contents
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({
            "pattern_map": pattern_map.copy(),
            "bluechip_score": bluechip_score,
        })
        return SimpleNamespace(
            signal="BUY",
            confidence=0.8,
            details={"rsi": 45.0},
        )
    
    # Monkey-patch temporarily
    import signals.signal_engine as sig_module
    original_generate_signal = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [pattern], 0.7)
        
        assert len(signals_called) == 1
        assert signals_called[0]["pattern_map"]["bullish_engulfing"] is True
    finally:
        sig_module.generate_signal = original_generate_signal  # type: ignore


def test_build_trade_signal_detects_bearish_engulfing_pattern() -> None:
    """build_trade_signal should set pattern_map for bearish_engulfing."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    pattern = PatternResult(
        pattern_name="bearish_engulfing",
        strength=0.8,
        timestamp=datetime(2024, 1, 15),
    )
    
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({"pattern_map": pattern_map.copy()})
        return SimpleNamespace(
            signal="SELL",
            confidence=0.75,
            details={},
        )
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [pattern], 0.7)
        assert signals_called[0]["pattern_map"]["bearish_engulfing"] is True
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_detects_hammer_pattern() -> None:
    """build_trade_signal should set pattern_map for hammer."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    pattern = PatternResult(
        pattern_name="hammer",
        strength=0.7,
        timestamp=datetime(2024, 1, 15),
    )
    
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({"pattern_map": pattern_map.copy()})
        return SimpleNamespace(signal="BUY", confidence=0.7, details={})
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [pattern], 0.7)
        assert signals_called[0]["pattern_map"]["hammer"] is True
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_detects_shooting_star_pattern() -> None:
    """build_trade_signal should set pattern_map for shooting_star."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    pattern = PatternResult(
        pattern_name="shooting_star",
        strength=0.7,
        timestamp=datetime(2024, 1, 15),
    )
    
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({"pattern_map": pattern_map.copy()})
        return SimpleNamespace(signal="SELL", confidence=0.7, details={})
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [pattern], 0.7)
        assert signals_called[0]["pattern_map"]["shooting_star"] is True
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_detects_doji_pattern() -> None:
    """build_trade_signal should set pattern_map for doji."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    pattern = PatternResult(
        pattern_name="doji",
        strength=0.6,
        timestamp=datetime(2024, 1, 15),
    )
    
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({"pattern_map": pattern_map.copy()})
        return SimpleNamespace(signal="HOLD", confidence=0.5, details={})
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [pattern], 0.7)
        assert signals_called[0]["pattern_map"]["doji"] is True
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_detects_morning_star_pattern() -> None:
    """build_trade_signal should set pattern_map for morning_star."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    pattern = PatternResult(
        pattern_name="morning_star",
        strength=0.8,
        timestamp=datetime(2024, 1, 15),
    )
    
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({"pattern_map": pattern_map.copy()})
        return SimpleNamespace(signal="BUY", confidence=0.8, details={})
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [pattern], 0.7)
        assert signals_called[0]["pattern_map"]["morning_star"] is True
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_detects_evening_star_pattern() -> None:
    """build_trade_signal should set pattern_map for evening_star."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    pattern = PatternResult(
        pattern_name="evening_star",
        strength=0.8,
        timestamp=datetime(2024, 1, 15),
    )
    
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({"pattern_map": pattern_map.copy()})
        return SimpleNamespace(signal="SELL", confidence=0.8, details={})
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [pattern], 0.7)
        assert signals_called[0]["pattern_map"]["evening_star"] is True
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_ignores_unknown_pattern() -> None:
    """build_trade_signal should skip unknown pattern names."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    pattern = PatternResult(
        pattern_name="unknown_pattern",
        strength=0.5,
        timestamp=datetime(2024, 1, 15),
    )
    
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({"pattern_map": pattern_map.copy()})
        return SimpleNamespace(signal="HOLD", confidence=0.5, details={})
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [pattern], 0.7)
        # unknown_pattern should not be in pattern_map
        assert "unknown_pattern" not in signals_called[0]["pattern_map"]
        # All known patterns should be False
        assert all(v is False for v in signals_called[0]["pattern_map"].values())
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_multiple_patterns() -> None:
    """build_trade_signal should detect multiple patterns."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    patterns = [
        PatternResult("bullish_engulfing", 0.8, datetime(2024, 1, 15)),
        PatternResult("hammer", 0.7, datetime(2024, 1, 15)),
    ]
    
    signals_called: list[dict[str, Any]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        signals_called.append({"pattern_map": pattern_map.copy()})
        return SimpleNamespace(signal="BUY", confidence=0.8, details={})
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, patterns, 0.7)
        assert signals_called[0]["pattern_map"]["bullish_engulfing"] is True
        assert signals_called[0]["pattern_map"]["hammer"] is True
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_uses_last_date_for_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should extract timestamp from last row."""
    last_date = pd.Timestamp("2024-01-20 15:45:30")
    technical_df = pd.DataFrame({
        "date": [
            pd.Timestamp("2024-01-15"),
            pd.Timestamp("2024-01-18"),
            last_date,
        ],
        "close": [1000.0, 1005.0, 1010.0],
    })
    
    import signals.signal_engine as sig_module
    monkeypatch.setattr(sig_module, "generate_signal", lambda *args, **kw: SimpleNamespace(
        signal="BUY", confidence=0.7, details={},
    ))
    
    signal = build_trade_signal("NABIL", technical_df, [], 0.7)
    
    # Should extract from last row and convert to pydatetime
    assert signal.timestamp.year == 2024
    assert signal.timestamp.month == 1
    assert signal.timestamp.day == 20
    assert signal.timestamp.hour == 15
    assert signal.timestamp.minute == 45
    assert signal.timestamp.second == 30


def test_build_trade_signal_uses_utc_now_for_empty_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should use current UTC time for empty DataFrame."""
    technical_df = pd.DataFrame(columns=["date", "close"])
    
    import signals.signal_engine as sig_module
    
    before = datetime.now(UTC)
    
    monkeypatch.setattr(sig_module, "generate_signal", lambda *args, **kw: SimpleNamespace(
        signal="HOLD", confidence=0.5, details={},
    ))
    
    signal = build_trade_signal("NABIL", technical_df, [], 0.7)
    
    after = datetime.now(UTC)
    
    # Timestamp should be roughly current time
    assert before <= signal.timestamp <= after


def test_build_trade_signal_converts_signal_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should convert signal_result to TradeSignal."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        return SimpleNamespace(
            signal="BUY",
            confidence=0.85,
            details={"rsi": 42.5, "macd": 0.3, "sma_ratio": 1.05},
        )
    
    import signals.signal_engine as sig_module
    monkeypatch.setattr(sig_module, "generate_signal", mock_generate_signal)
    
    signal = build_trade_signal("NABIL", technical_df, [], 0.7)
    
    assert signal.signal == "BUY"
    assert signal.confidence == 0.85
    assert signal.indicators == {"rsi": 42.5, "macd": 0.3, "sma_ratio": 1.05}


def test_build_trade_signal_passes_bluechip_score(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should pass bluechip_score to generate_signal."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    
    calls: list[tuple[str, pd.DataFrame, dict[str, bool], float]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        calls.append((symbol, df, pattern_map, bluechip_score))
        return SimpleNamespace(signal="BUY", confidence=0.7, details={})
    
    import signals.signal_engine as sig_module
    monkeypatch.setattr(sig_module, "generate_signal", mock_generate_signal)
    
    build_trade_signal("NABIL", technical_df, [], 0.82)
    
    assert len(calls) == 1
    assert calls[0][3] == 0.82  # bluechip_score parameter


def test_build_trade_signal_passes_technical_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should pass technical_df to generate_signal."""
    technical_df = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-15")],
        "close": [1000.0],
        "rsi": [45.0],
    })
    
    calls: list[tuple[str, pd.DataFrame, dict[str, bool], float]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        calls.append((symbol, df, pattern_map, bluechip_score))
        return SimpleNamespace(signal="BUY", confidence=0.7, details={})
    
    import signals.signal_engine as sig_module
    monkeypatch.setattr(sig_module, "generate_signal", mock_generate_signal)
    
    build_trade_signal("NABIL", technical_df, [], 0.7)
    
    assert len(calls) == 1
    assert (calls[0][1] == technical_df).all().all()
    assert "rsi" in calls[0][1].columns


def test_build_trade_signal_all_patterns_default_to_false() -> None:
    """build_trade_signal should initialize all patterns to False."""
    technical_df = pd.DataFrame({"date": [pd.Timestamp("2024-01-15")], "close": [1000.0]})
    
    calls: list[dict[str, bool]] = []
    
    def mock_generate_signal(
        symbol: str,
        df: pd.DataFrame,
        pattern_map: dict[str, bool],
        bluechip_score: float,
    ) -> Any:
        calls.append(pattern_map.copy())
        return SimpleNamespace(signal="HOLD", confidence=0.5, details={})
    
    import signals.signal_engine as sig_module
    original = sig_module.generate_signal
    sig_module.generate_signal = mock_generate_signal  # type: ignore
    
    try:
        build_trade_signal("NABIL", technical_df, [], 0.7)
        
        expected_patterns = {
            "bullish_engulfing",
            "bearish_engulfing",
            "hammer",
            "shooting_star",
            "doji",
            "morning_star",
            "evening_star",
        }
        actual_patterns = set(calls[0].keys())
        assert actual_patterns == expected_patterns
        assert all(v is False for v in calls[0].values())
    finally:
        sig_module.generate_signal = original  # type: ignore


def test_build_trade_signal_empty_pattern_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should handle empty pattern_results list."""
    technical_df = _build_full_technical_df()
    
    import signals.signal_engine as sig_module
    monkeypatch.setattr(sig_module, "generate_signal", lambda *args, **kw: SimpleNamespace(
        signal="BUY", confidence=0.7, details={},
    ))
    
    signal = build_trade_signal("NABIL", technical_df, [], 0.7)
    
    assert signal.signal in ["BUY", "SELL", "HOLD"]


def test_build_trade_signal_returns_trade_signal_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_trade_signal should always return TradeSignal instance."""
    technical_df = _build_full_technical_df()
    
    import signals.signal_engine as sig_module
    monkeypatch.setattr(sig_module, "generate_signal", lambda *args, **kw: SimpleNamespace(
        signal="BUY", confidence=0.7, details={},
    ))
    
    signal = build_trade_signal("NABIL", technical_df, [], 0.7)
    
    assert isinstance(signal, TradeSignal)
    assert type(signal).__name__ == "TradeSignal"
