"""Tests for score breakdown and explainability features."""

from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError

from api.models import BlueChipRankingItem, BlueChipRankingResponse, FeatureImportance, ScoreBreakdown
from api.service import NepseApiService
from cli.commands import _format_score_breakdown


class TestScoreBreakdown:
    """Tests for ScoreBreakdown model and validation."""

    def test_score_breakdown_valid(self) -> None:
        """Test creating valid ScoreBreakdown with typical values."""
        breakdown = ScoreBreakdown(
            market_cap=0.85,
            volume=0.72,
            stability=0.68,
            trend=0.91,
            fundamental=0.45,
            sector=0.70,
        )
        assert breakdown.market_cap == 0.85
        assert breakdown.volume == 0.72

    def test_score_breakdown_within_bounds(self) -> None:
        """Test that all scores must be between 0 and 1."""
        # Valid: all at boundaries
        breakdown = ScoreBreakdown(
            market_cap=0.0,
            volume=1.0,
            stability=0.5,
            trend=0.5,
            fundamental=0.5,
            sector=0.5,
        )
        assert breakdown.market_cap == 0.0
        assert breakdown.volume == 1.0

    def test_score_breakdown_invalid_market_cap_too_high(self) -> None:
        """Test validation rejects market_cap > 1.0."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(
                market_cap=1.1,
                volume=0.5,
                stability=0.5,
                trend=0.5,
                fundamental=0.5,
                sector=0.5,
            )

    def test_score_breakdown_invalid_volume_negative(self) -> None:
        """Test validation rejects volume < 0.0."""
        with pytest.raises(ValidationError):
            ScoreBreakdown(
                market_cap=0.5,
                volume=-0.1,
                stability=0.5,
                trend=0.5,
                fundamental=0.5,
                sector=0.5,
            )

    def test_score_breakdown_explain_method(self) -> None:
        """Test explain() method returns formatted component string."""
        breakdown = ScoreBreakdown(
            market_cap=0.85,
            volume=0.72,
            stability=0.68,
            trend=0.91,
            fundamental=0.45,
            sector=0.70,
        )
        explanation = breakdown.explain()
        assert "market_cap=0.850" in explanation
        assert "volume=0.720" in explanation
        assert "stability=0.680" in explanation
        assert "trend=0.910" in explanation
        assert "fundamental=0.450" in explanation
        assert "sector=0.700" in explanation


class TestBlueChipRankingItem:
    """Tests for BlueChipRankingItem model."""

    def test_ranking_item_valid(self) -> None:
        """Test creating valid BlueChipRankingItem."""
        breakdown = ScoreBreakdown(
            market_cap=0.85,
            volume=0.72,
            stability=0.68,
            trend=0.91,
            fundamental=0.45,
            sector=0.70,
        )
        item = BlueChipRankingItem(
            rank=1,
            symbol="SAMPLE",
            sector="Finance",
            bluechip_score=0.795,
            base_bluechip_score=0.790,
            score_breakdown=breakdown,
            market_cap=50000000.0,
            avg_volume=100000.0,
            volatility=0.25,
            cagr=0.15,
            fundamental_strength=0.45,
        )
        assert item.rank == 1
        assert item.symbol == "SAMPLE"
        assert item.bluechip_score == 0.795

    def test_ranking_item_rank_must_be_positive(self) -> None:
        """Test that rank must be >= 1."""
        breakdown = ScoreBreakdown(
            market_cap=0.5, volume=0.5, stability=0.5, trend=0.5, fundamental=0.5, sector=0.5
        )
        with pytest.raises(ValidationError):
            BlueChipRankingItem(
                rank=0,
                symbol="TEST",
                sector="Test",
                bluechip_score=0.5,
                base_bluechip_score=0.5,
                score_breakdown=breakdown,
                market_cap=1000000.0,
                avg_volume=10000.0,
                volatility=0.2,
                cagr=0.1,
                fundamental_strength=0.5,
            )


class TestBlueChipRankingResponse:
    """Tests for BlueChipRankingResponse model."""

    def test_ranking_response_empty(self) -> None:
        """Test BlueChipRankingResponse with empty ranking list."""
        response = BlueChipRankingResponse(
            top_n=20,
            sector_relative=False,
            generated_from="test",
            feature_importance=FeatureImportance(
                market_cap=0.30, volume=0.20, stability=0.20, trend=0.20, fundamental=0.10
            ),
            ranking=[],
        )
        assert response.top_n == 20
        assert response.sector_relative is False
        assert len(response.ranking) == 0

    def test_ranking_response_with_items(self) -> None:
        """Test BlueChipRankingResponse with populated ranking list."""
        breakdown = ScoreBreakdown(
            market_cap=0.85, volume=0.72, stability=0.68, trend=0.91, fundamental=0.45, sector=0.70
        )
        item = BlueChipRankingItem(
            rank=1,
            symbol="SAMPLE",
            sector="Finance",
            bluechip_score=0.795,
            base_bluechip_score=0.790,
            score_breakdown=breakdown,
            market_cap=50000000.0,
            avg_volume=100000.0,
            volatility=0.25,
            cagr=0.15,
            fundamental_strength=0.45,
        )
        response = BlueChipRankingResponse(
            top_n=20,
            sector_relative=False,
            generated_from="test",
            feature_importance=FeatureImportance(
                market_cap=0.30, volume=0.20, stability=0.20, trend=0.20, fundamental=0.10
            ),
            ranking=[item],
        )
        assert len(response.ranking) == 1
        assert response.ranking[0].symbol == "SAMPLE"


class TestBuildBluechipRankingResponse:
    """Tests for build_bluechip_ranking_response method."""

    @pytest.fixture
    def service(self) -> NepseApiService:
        """Provide a NepseApiService instance for tests."""
        # Since NepseApiService initializes real clients and coordinators,
        # we just create an instance normally; it will use configured settings
        return NepseApiService()

    def test_empty_dataframe(self, service: NepseApiService) -> None:
        """Test building response from empty bluechip dataframe."""
        empty_df = pd.DataFrame()
        response = service.build_bluechip_ranking_response(empty_df, sector_relative=False, top_n=20)

        assert response.top_n == 20
        assert response.sector_relative is False
        assert len(response.ranking) == 0

    def test_single_stock_dataframe(self, service: NepseApiService) -> None:
        """Test building response from single-stock dataframe."""
        df = pd.DataFrame(
            [
                {
                    "rank": 1,
                    "symbol": "TEST",
                    "sector": "Finance",
                    "bluechip_score": 0.795,
                    "base_bluechip_score": 0.790,
                    "score_breakdown": {
                        "market_cap": 0.85,
                        "volume": 0.72,
                        "stability": 0.68,
                        "trend": 0.91,
                        "fundamental": 0.45,
                        "sector": 0.70,
                    },
                    "market_cap": 50000000.0,
                    "avg_volume": 100000.0,
                    "volatility": 0.25,
                    "cagr": 0.15,
                    "fundamental_strength": 0.45,
                }
            ]
        )
        response = service.build_bluechip_ranking_response(df, sector_relative=False, top_n=20)

        assert len(response.ranking) == 1
        assert response.ranking[0].symbol == "TEST"
        assert response.ranking[0].bluechip_score == 0.795
        assert response.ranking[0].score_breakdown.market_cap == 0.85

    def test_multiple_stocks_with_sector_summary(self, service: NepseApiService) -> None:
        """Test building response with sector-relative scoring and sector summary."""
        df = pd.DataFrame(
            [
                {
                    "rank": 1,
                    "symbol": "STOCK1",
                    "sector": "Finance",
                    "bluechip_score": 0.80,
                    "base_bluechip_score": 0.79,
                    "score_breakdown": {
                        "market_cap": 0.85,
                        "volume": 0.72,
                        "stability": 0.68,
                        "trend": 0.91,
                        "fundamental": 0.45,
                        "sector": 0.75,
                    },
                    "market_cap": 50000000.0,
                    "avg_volume": 100000.0,
                    "volatility": 0.25,
                    "cagr": 0.15,
                    "fundamental_strength": 0.45,
                },
                {
                    "rank": 2,
                    "symbol": "STOCK2",
                    "sector": "Banking",
                    "bluechip_score": 0.75,
                    "base_bluechip_score": 0.74,
                    "score_breakdown": {
                        "market_cap": 0.75,
                        "volume": 0.68,
                        "stability": 0.65,
                        "trend": 0.81,
                        "fundamental": 0.50,
                        "sector": 0.72,
                    },
                    "market_cap": 40000000.0,
                    "avg_volume": 90000.0,
                    "volatility": 0.28,
                    "cagr": 0.12,
                    "fundamental_strength": 0.50,
                },
            ]
        )
        response = service.build_bluechip_ranking_response(df, sector_relative=True, top_n=20)

        assert len(response.ranking) == 2
        assert response.sector_relative is True
        assert response.ranking[0].symbol == "STOCK1"
        assert response.ranking[1].symbol == "STOCK2"

        # Verify sector_summary was computed
        assert response.sector_summary is not None
        assert len(response.sector_summary) == 2
        sectors = [s["sector"] for s in response.sector_summary]
        assert "Finance" in sectors
        assert "Banking" in sectors

    def test_fallback_to_component_scores(self, service: NepseApiService) -> None:
        """Test fallback to component scores when score_breakdown not provided."""
        df = pd.DataFrame(
            [
                {
                    "rank": 1,
                    "symbol": "TEST",
                    "sector": "Finance",
                    "bluechip_score": 0.795,
                    "base_bluechip_score": 0.790,
                    # No score_breakdown dict, but component scores are present
                    "market_cap_score": 0.85,
                    "volume_score": 0.72,
                    "stability_score": 0.68,
                    "trend_score": 0.91,
                    "fundamental_score": 0.45,
                    "sector_score": 0.70,
                    "market_cap": 50000000.0,
                    "avg_volume": 100000.0,
                    "volatility": 0.25,
                    "cagr": 0.15,
                    "fundamental_strength": 0.45,
                }
            ]
        )
        response = service.build_bluechip_ranking_response(df, sector_relative=False, top_n=20)

        assert len(response.ranking) == 1
        # Should build from component scores
        assert response.ranking[0].score_breakdown.market_cap == 0.85
        assert response.ranking[0].score_breakdown.volume == 0.72


class TestFormatScoreBreakdown:
    """Tests for CLI _format_score_breakdown helper."""

    def test_format_valid_breakdown(self) -> None:
        """Test formatting valid score breakdown dict."""
        breakdown = {"market_cap": 0.85, "volume": 0.72, "stability": 0.68, "trend": 0.91, "fundamental": 0.45, "sector": 0.70}
        result = _format_score_breakdown(breakdown)
        assert "mkt=0.85" in result
        assert "vol=0.72" in result
        assert "stab=0.68" in result
        assert "trend=0.91" in result
        assert "fund=0.45" in result
        assert "sec=0.70" in result

    def test_format_none_breakdown(self) -> None:
        """Test formatting None breakdown returns N/A."""
        result = _format_score_breakdown(None)
        assert result == "N/A"

    def test_format_empty_breakdown(self) -> None:
        """Test formatting empty breakdown returns N/A."""
        result = _format_score_breakdown({})
        assert result == "N/A"

    def test_format_partial_breakdown(self) -> None:
        """Test formatting breakdown with missing components uses defaults."""
        breakdown = {"market_cap": 0.85, "volume": 0.72}
        result = _format_score_breakdown(breakdown)
        assert "mkt=0.85" in result
        assert "vol=0.72" in result
        assert "stab=0.00" in result  # Missing components default to 0.0

    def test_format_invalid_breakdown(self) -> None:
        """Test formatting invalid breakdown gracefully returns N/A."""
        result = _format_score_breakdown("not a dict")
        assert result == "N/A"
