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
