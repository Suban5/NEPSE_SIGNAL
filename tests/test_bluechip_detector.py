"""Tests for blue-chip detector logic."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bluechip.detector import BlueChipDetector, BlueChipScoringConfig, BlueChipWeights


def _build_history(symbol: str, growth: float, volume_base: float) -> pd.DataFrame:
    rows = 300
    close = np.linspace(100, 100 * growth, rows)
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=rows, freq="D"),
            "symbol": symbol,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": np.full(rows, volume_base),
            "turnover": np.full(rows, volume_base * 100),
        }
    )


def test_bluechip_detector_scores_and_ranks() -> None:
    snapshot = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "Banking", "market_cap": 1_000_000_000},
            {"symbol": "BBB", "sector": "Hydro", "market_cap": 500_000_000},
        ]
    )
    historical = {
        "AAA": _build_history("AAA", growth=2.0, volume_base=5000),
        "BBB": _build_history("BBB", growth=1.1, volume_base=1200),
    }

    detector = BlueChipDetector()
    features = detector.build_feature_table(snapshot, historical)
    scored = detector.score_bluechips(features)

    assert not scored.empty
    assert scored.iloc[0]["symbol"] == "AAA"
    assert scored["bluechip_score"].between(0, 1).all()
    assert scored["rank"].tolist() == [1, 2]
    assert "fundamental_score" in scored.columns
    assert "score_breakdown" in scored.columns


def test_bluechip_detector_supports_sector_relative_scoring() -> None:
    snapshot = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "Banking", "market_cap": 1_000_000_000},
            {"symbol": "BBB", "sector": "Banking", "market_cap": 700_000_000},
            {"symbol": "CCC", "sector": "Hydro", "market_cap": 500_000_000},
        ]
    )
    historical = {
        "AAA": _build_history("AAA", growth=2.0, volume_base=5000),
        "BBB": _build_history("BBB", growth=1.8, volume_base=4500),
        "CCC": _build_history("CCC", growth=1.1, volume_base=1200),
    }

    detector = BlueChipDetector(config=BlueChipScoringConfig(sector_relative=True, sector_blend=0.25))
    scored = detector.score_bluechips(detector.build_feature_table(snapshot, historical))

    assert not scored.empty
    assert scored["sector_score"].between(0, 1).all()
    assert scored["bluechip_score"].between(0, 1).all()
    assert scored.iloc[0]["sector"] in {"Banking", "Hydro"}


def test_bluechip_detector_exposes_feature_importance_and_report() -> None:
    snapshot = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "Banking", "market_cap": 1_000_000_000},
            {"symbol": "BBB", "sector": "Hydro", "market_cap": 500_000_000},
        ]
    )
    historical = {
        "AAA": _build_history("AAA", growth=2.0, volume_base=5000),
        "BBB": _build_history("BBB", growth=1.1, volume_base=1200),
    }

    detector = BlueChipDetector()
    scored = detector.score_bluechips(detector.build_feature_table(snapshot, historical))
    report = detector.build_scoring_report(scored)

    assert report["feature_importance"]["fundamental"] == pytest.approx(0.10)
    assert len(report["symbol_breakdown"]) == 2


def test_bluechip_weights_validate_sum() -> None:
    with pytest.raises(ValueError, match="must sum to 1.0"):
        BlueChipWeights(market_cap=0.5, volume=0.2, stability=0.2, trend=0.2, fundamental=0.1)
