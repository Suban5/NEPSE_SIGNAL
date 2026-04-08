"""Pydantic request/response models for API contracts."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorInfo(BaseModel):
    """Structured error payload for upstream failures."""

    code: str
    type: str
    method: str
    message: str
    error_id: str
    upstream_status: Optional[int] = None
    retriable: bool = False


class ApiContractResponse(BaseModel):
    """Negotiated API contract information."""

    default_version: str
    negotiated_version: str
    supported_versions: List[str]
    request_header: Optional[str] = None


class ApiErrorResponse(BaseModel):
    """Error response contract returned by FastAPI endpoints."""

    error: ApiErrorInfo


class HealthResponse(BaseModel):
    """Health endpoint response payload."""

    ok: bool
    marketStatus: Dict[str, Any]


class MarketStatusResponse(BaseModel):
    """Market status response model."""

    model_config = ConfigDict(extra="allow")

    isOpen: Optional[Any] = None


class GenericObjectResponse(BaseModel):
    """Generic object response model for pass-through payloads."""

    model_config = ConfigDict(extra="allow")


class CompanyHistoryQuery(BaseModel):
    """Company history date-range query model."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None


class TradingAverageQuery(BaseModel):
    """Trading average query model."""

    business_date: str = Field(..., min_length=1)
    n_days: int = Field(default=180, ge=1)


class NewsListQuery(BaseModel):
    """Pagination and formatting query model for news endpoints."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1)
    is_strip_tags: bool = True


class NewsListResponse(BaseModel):
    """Structured news list response."""

    model_config = ConfigDict(extra="allow")

    page: Optional[int] = None
    pageSize: Optional[int] = None
    stripTags: Optional[bool] = None
    items: Optional[List[Dict[str, Any]]] = None


class RequestMetricsResponse(BaseModel):
    """Runtime metrics snapshot for API observability."""

    request_count: int
    error_count: int
    avg_duration_ms: float
    status_counts: Dict[str, int]
    endpoint_counts: Dict[str, int]
    cache_stats: Dict[str, Dict[str, int]]


class ScoreBreakdown(BaseModel):
    """Detailed breakdown of blue-chip score components with computed ratios."""

    market_cap: float = Field(ge=0.0, le=1.0, description="Market capitalization normalized score")
    volume: float = Field(ge=0.0, le=1.0, description="Liquidity (volume + turnover) normalized score")
    stability: float = Field(ge=0.0, le=1.0, description="Inverse volatility: 1 - normalized volatility")
    trend: float = Field(ge=0.0, le=1.0, description="Trend (CAGR) normalized score")
    fundamental: float = Field(ge=0.0, le=1.0, description="Fundamental strength (earnings, dividend, revenue) normalized")
    sector: float = Field(ge=0.0, le=1.0, description="Sector relative ranking score when sector_relative is enabled")

    def explain(self) -> str:
        """Return human-readable explanation of score components."""
        components = [
            f"market_cap={self.market_cap:.3f}",
            f"volume={self.volume:.3f}",
            f"stability={self.stability:.3f}",
            f"trend={self.trend:.3f}",
            f"fundamental={self.fundamental:.3f}",
            f"sector={self.sector:.3f}",
        ]
        return ", ".join(components)


class BlueChipRankingItem(BaseModel):
    """Single stock entry in blue-chip ranking with score components and breakdown."""

    rank: int = Field(ge=1, description="Rank in blue-chip ranking (1-indexed)")
    symbol: str = Field(min_length=1, description="Stock symbol")
    sector: str = Field(description="Industry sector")
    bluechip_score: float = Field(ge=0.0, le=1.0, description="Final weighted blue-chip score")
    base_bluechip_score: float = Field(ge=0.0, le=1.0, description="Base score before sector adjustment")
    score_breakdown: ScoreBreakdown = Field(description="Component-level score breakdown for transparency")
    market_cap: float = Field(description="Market capitalization value")
    avg_volume: float = Field(description="Average trading volume")
    volatility: float = Field(description="Annualized volatility")
    cagr: float = Field(description="Compound annual growth rate")
    fundamental_strength: float = Field(description="Aggregated fundamental metrics")

    model_config = ConfigDict(populate_by_name=True)


class FeatureImportance(BaseModel):
    """Feature importance weights used in blue-chip scoring."""

    market_cap: float = Field(ge=0.0, le=1.0)
    volume: float = Field(ge=0.0, le=1.0)
    stability: float = Field(ge=0.0, le=1.0)
    trend: float = Field(ge=0.0, le=1.0)
    fundamental: float = Field(ge=0.0, le=1.0)


class BlueChipRankingResponse(BaseModel):
    """Structured blue-chip ranking response with explainability."""

    top_n: int
    sector_relative: bool
    generated_from: str = Field(description="Workflow or service that generated this ranking")
    feature_importance: FeatureImportance = Field(description="Weights applied to score components")
    ranking: List[BlueChipRankingItem] = Field(description="Ranked stocks with score breakdowns")
    sector_summary: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Aggregate statistics by sector (mean, max, count)"
    )


class AnalyticsRowsResponse(BaseModel):
    """Generic analytics rows response with workflow traceability."""

    top_n: int
    sector_relative: bool
    execution_id: str = Field(min_length=1, description="Workflow execution identifier")
    rows: List[Dict[str, Any]]


class AnalyticsBluechipRankingResponse(BaseModel):
    """Typed analytics response for blue-chip ranking endpoint."""

    top_n: int
    sector_relative: bool
    execution_id: str = Field(min_length=1, description="Workflow execution identifier")
    rows: List[Dict[str, Any]]
