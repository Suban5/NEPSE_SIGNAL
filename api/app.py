"""FastAPI app exposing nepse_client-backed endpoints."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import date
import logging
import time
from typing import Any
from uuid import uuid4

from contextvars import ContextVar

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response

from typing_extensions import Annotated

from api.models import (
    AnalyticsBluechipRankingResponse,
    AnalyticsOpportunitiesResponse,
    AnalyticsSignalSummaryResponse,
    ApiErrorResponse,
    ApiContractResponse,
    CompanyHistoryQuery,
    GenericObjectResponse,
    HealthResponse,
    MarketStatusResponse,
    NewsListQuery,
    NewsListResponse,
    RequestMetricsResponse,
    TradingAverageQuery,
)
from api.service import NepseApiService
from api.telemetry import metrics_registry
from workflows.errors import WorkflowError


logger = logging.getLogger(__name__)
observability_logger = logging.getLogger("api.observability")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

app = FastAPI(title="NepseSignal API", version="1.0.0")
service = NepseApiService()
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {401: {"model": ApiErrorResponse}, 502: {"model": ApiErrorResponse}}
SUPPORTED_API_VERSIONS = ["v1", "v2"]


@app.middleware("http")
async def add_request_context(request: Request, call_next: Any) -> Response:
    """Attach request id, capture duration, and emit structured request logs."""
    request_id = request.headers.get("X-Request-Id") or str(uuid4())
    negotiated_version = request.headers.get("X-API-Version", "v1").strip().lower() or "v1"
    if negotiated_version not in SUPPORTED_API_VERSIONS:
        negotiated_version = "v1"
    token = request_id_var.set(request_id)
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-Id"] = request_id
        response.headers["X-API-Contract-Version"] = negotiated_version
        response.headers["X-API-Supported-Versions"] = ",".join(SUPPORTED_API_VERSIONS)
        return response
    finally:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        endpoint = request.url.path
        metrics_registry.record(endpoint, status_code, duration_ms)
        observability_logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "contract_version": negotiated_version,
                    "client_host": request.client.host if request.client else None,
                    "query": dict(request.query_params),
                },
                default=str,
            )
        )
        request_id_var.reset(token)


def _extract_status_code(exc: Exception) -> int:
    """Extract HTTP status code from upstream exception when available."""
    if isinstance(exc, WorkflowError):
        return int(exc.status_code)

    if isinstance(exc, HTTPException):
        return int(exc.status_code)

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and 400 <= status_code <= 599:
        return status_code
    return 502


def _extract_upstream_status(exc: Exception) -> int | None:
    """Extract upstream status metadata from an exception when available."""
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and 400 <= status_code <= 599:
        return status_code
    upstream_status = getattr(exc, "upstream_status", None)
    if isinstance(upstream_status, int) and 400 <= upstream_status <= 599:
        return upstream_status
    return None


def _is_retriable(exc: Exception, status_code: int) -> bool:
    """Determine whether a failure is safe to retry."""
    if status_code in {408, 429, 500, 502, 503, 504}:
        return True
    return exc.__class__.__name__ in {"TimeoutError", "ReadTimeout", "ConnectTimeout", "NepseNetworkError"}


def _build_error_detail(method: str, exc: Exception) -> dict[str, dict[str, Any]]:
    """Build stable API error contract payload."""
    status_code = _extract_status_code(exc)
    upstream_status = _extract_upstream_status(exc)
    error_id = getattr(exc, "error_id", None) or str(uuid4())
    category = getattr(exc, "category", None)
    stage = getattr(exc, "stage", None)
    workflow = getattr(exc, "workflow", None)
    return {
        "error": {
            "code": "UPSTREAM_ERROR",
            "type": exc.__class__.__name__,
            "method": method,
            "message": str(exc),
            "error_id": error_id,
            "category": category,
            "stage": stage,
            "workflow": workflow,
            "upstream_status": upstream_status,
            "retriable": bool(getattr(exc, "retriable", _is_retriable(exc, status_code))),
        }
    }


def _build_contract_response(request_header: str | None = None) -> dict[str, Any]:
    """Build API contract negotiation response payload."""
    negotiated_version = (request_header or "v1").strip().lower() if request_header else "v1"
    if negotiated_version not in SUPPORTED_API_VERSIONS:
        negotiated_version = "v1"
    return {
        "default_version": "v1",
        "negotiated_version": negotiated_version,
        "supported_versions": SUPPORTED_API_VERSIONS,
        "request_header": request_header,
    }


def _wrap_call(method: str, func: Any, *args: Any, **kwargs: Any) -> Any:
    """Execute service call with consistent HTTP error mapping."""
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        logger.exception("API method failed: %s", method)
        raise HTTPException(
            status_code=_extract_status_code(exc),
            detail=_build_error_detail(method, exc),
        ) from exc


def _wrap_call_with_timeout(
    method: str,
    timeout_seconds: int,
    func: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute service call with timeout and stable error mapping."""
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(func, *args, **kwargs)
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        logger.warning("API method timed out: %s (timeout=%ss)", method, timeout_seconds)
        raise HTTPException(
            status_code=504,
            detail={
                "error": {
                    "code": "UPSTREAM_TIMEOUT",
                    "type": "TimeoutError",
                    "method": method,
                    "message": f"Request timed out after {timeout_seconds} seconds",
                }
            },
        ) from exc
    except Exception as exc:
        logger.exception("API method failed: %s", method)
        raise HTTPException(
            status_code=_extract_status_code(exc),
            detail=_build_error_detail(method, exc),
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


@app.get("/health", response_model=HealthResponse, responses=ERROR_RESPONSES)
def health() -> Any:
    """Return API health status."""
    return _wrap_call("health", service.health)


@app.get("/market/status", response_model=MarketStatusResponse, responses=ERROR_RESPONSES)
def market_status() -> Any:
    """Return market open/closed status."""
    return _wrap_call("market_status", service.market_status)


@app.get("/market/summary", response_model=GenericObjectResponse, responses=ERROR_RESPONSES)
def market_summary() -> Any:
    """Return market summary payload."""
    return _wrap_call("market_summary", service.market_summary)


@app.get("/market/index", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_index() -> Any:
    """Return NEPSE index payload."""
    return _wrap_call("nepse_index", service.nepse_index)


@app.get("/market/sub-indices", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_sub_indices() -> Any:
    """Return NEPSE sub-indices payload."""
    return _wrap_call("nepse_sub_indices", service.nepse_sub_indices)


@app.get("/market/live", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_live() -> Any:
    """Return live market rows."""
    return _wrap_call("live_market", service.live_market)


@app.get("/market/price-volume", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_price_volume() -> Any:
    """Return market price-volume payload."""
    return _wrap_call("price_volume", service.price_volume)


@app.get("/market/supply-demand", response_model=GenericObjectResponse, responses=ERROR_RESPONSES)
def market_supply_demand() -> Any:
    """Return supply-demand payload."""
    return _wrap_call("supply_demand", service.supply_demand)


@app.get("/market/top-gainers", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_top_gainers() -> Any:
    """Return top gainers list."""
    return _wrap_call("top_gainers", service.top_gainers)


@app.get("/market/top-losers", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_top_losers() -> Any:
    """Return top losers list."""
    return _wrap_call("top_losers", service.top_losers)


@app.get("/market/top-trade-scrips", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_top_trade_scrips() -> Any:
    """Return top trade scrip list."""
    return _wrap_call("top_ten_trade_scrips", service.top_ten_trade_scrips)


@app.get("/market/top-transaction-scrips", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_top_transaction_scrips() -> Any:
    """Return top transaction scrip list."""
    return _wrap_call("top_ten_transaction_scrips", service.top_ten_transaction_scrips)


@app.get("/market/top-turnover-scrips", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def market_top_turnover_scrips() -> Any:
    """Return top turnover scrip list."""
    return _wrap_call("top_ten_turnover_scrips", service.top_ten_turnover_scrips)


@app.get("/companies", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def companies() -> Any:
    """Return company list."""
    return _wrap_call("companies", service.companies)


@app.get("/securities", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def securities() -> Any:
    """Return securities list."""
    return _wrap_call("securities", service.securities)


@app.get("/companies/{symbol}", response_model=GenericObjectResponse, responses=ERROR_RESPONSES)
def company_details(symbol: str) -> Any:
    """Return details for one company symbol."""
    return _wrap_call("company_details", service.company_details, symbol)


@app.get("/companies/{symbol}/history", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def company_history(
    symbol: str,
    query: Annotated[CompanyHistoryQuery, Depends()],
) -> Any:
    """Return historical rows for one company symbol."""
    return _wrap_call("company_history", service.company_history, symbol, query.start_date, query.end_date)


@app.get("/companies/{symbol}/graph", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def company_graph(symbol: str) -> Any:
    """Return daily scrip price graph payload for symbol."""
    return _wrap_call("daily_scrip_price_graph", service.daily_scrip_price_graph, symbol)


@app.get("/companies/{company_id}/financials", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def company_financials(company_id: str) -> Any:
    """Return company financial details payload."""
    return _wrap_call("company_financial_details", service.company_financial_details, company_id)


@app.get("/companies/{company_id}/agm", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def company_agm(company_id: str) -> Any:
    """Return company AGM payload."""
    return _wrap_call("company_agm", service.company_agm, company_id)


@app.get("/companies/{company_id}/dividend", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def company_dividend(company_id: str) -> Any:
    """Return company dividend payload."""
    return _wrap_call("company_dividend", service.company_dividend, company_id)


@app.get("/companies/{company_id}/market-depth", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def company_market_depth(company_id: str) -> Any:
    """Return company market depth payload."""
    return _wrap_call("company_market_depth", service.company_market_depth, company_id)


@app.get("/trading/floor-sheet", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def trading_floor_sheet(
    show_progress: bool = Query(default=False),
    timeout_seconds: int = Query(default=30, ge=1, le=300),
) -> Any:
    """Return floor sheet payload."""
    return _wrap_call_with_timeout(
        "floor_sheet",
        timeout_seconds,
        service.floor_sheet,
        show_progress,
    )


@app.get("/trading/floor-sheet/{symbol}", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def trading_floor_sheet_of(symbol: str, business_date: str = Query(...)) -> Any:
    """Return floor sheet payload for symbol/date."""
    return _wrap_call("floor_sheet_of", service.floor_sheet_of, symbol, business_date)


@app.get("/trading/average", response_model=dict[str, Any] | list[dict[str, Any]], responses=ERROR_RESPONSES)
def trading_average(query: Annotated[TradingAverageQuery, Depends()]) -> Any:
    """Return trading average payload."""
    return _wrap_call("trading_average", service.trading_average, query.business_date, query.n_days)


@app.get("/trading/market-depth/{symbol}", response_model=str, responses=ERROR_RESPONSES)
def trading_market_depth(symbol: str) -> Any:
    """Return market depth payload for symbol."""
    return _wrap_call("symbol_market_depth", service.symbol_market_depth, symbol)


@app.get("/news/company", response_model=NewsListResponse, responses=ERROR_RESPONSES)
def news_company(query: Annotated[NewsListQuery, Depends()]) -> Any:
    """Return company news list payload."""
    return _wrap_call("company_news_list", service.company_news_list, query.page, query.page_size, query.is_strip_tags)


@app.get("/news/alerts", response_model=NewsListResponse, responses=ERROR_RESPONSES)
def news_alerts(query: Annotated[NewsListQuery, Depends()]) -> Any:
    """Return news and alerts payload."""
    return _wrap_call("news_alert_list", service.news_alert_list, query.page, query.page_size, query.is_strip_tags)


@app.get("/news/press-releases", response_model=GenericObjectResponse, responses=ERROR_RESPONSES)
def news_press_releases() -> Any:
    """Return press release payload."""
    return _wrap_call("press_release", service.press_release)


@app.get("/news/notices", response_model=GenericObjectResponse, responses=ERROR_RESPONSES)
def news_notices(page: int = Query(default=0, ge=0)) -> Any:
    """Return NEPSE notices payload."""
    return _wrap_call("nepse_notice", service.nepse_notice, page)


@app.get("/other/holidays", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def other_holidays(year: int = Query(..., ge=1900)) -> Any:
    """Return holiday list payload for year."""
    return _wrap_call("holiday_list", service.holiday_list, year)


@app.get("/other/debentures-bonds", response_model=list[dict[str, Any]], responses=ERROR_RESPONSES)
def other_debentures_bonds(instrument_type: str = Query(default="debenture", pattern="^(debenture|bond)$")) -> Any:
    """Return debenture or bond list payload."""
    return _wrap_call("debenture_bond_list", service.debenture_bond_list, instrument_type)


@app.get("/other/price-volume-history", response_model=GenericObjectResponse, responses=ERROR_RESPONSES)
def other_price_volume_history(business_date: str = Query(...)) -> Any:
    """Return price-volume history payload for date."""
    return _wrap_call("price_volume_history", service.price_volume_history, business_date)


@app.get("/mappings/company-id", response_model=dict[str, int], responses=ERROR_RESPONSES)
def mappings_company_id(force_update: bool = Query(default=False)) -> Any:
    """Return company ID key map payload."""
    return _wrap_call("company_id_key_map", service.company_id_key_map, force_update)


@app.get("/mappings/security-id", response_model=dict[str, int], responses=ERROR_RESPONSES)
def mappings_security_id(force_update: bool = Query(default=False)) -> Any:
    """Return security ID key map payload."""
    return _wrap_call("security_id_key_map", service.security_id_key_map, force_update)


@app.get("/mappings/sector-scrips", response_model=dict[str, list[str]], responses=ERROR_RESPONSES)
def mappings_sector_scrips() -> Any:
    """Return sector-wise scrip mapping payload."""
    return _wrap_call("sector_scrips", service.sector_scrips)


@app.get("/analytics/bluechip-ranking", response_model=AnalyticsBluechipRankingResponse, responses=ERROR_RESPONSES)
def analytics_bluechip_ranking(
    top_n: int = Query(default=20, ge=1, le=200),
    sector_relative: bool = Query(default=False),
) -> Any:
    """Return workflow-backed blue-chip ranking."""
    return _wrap_call("analytics_bluechip_ranking", service.analytics_bluechip_ranking, top_n, sector_relative)


@app.get("/analytics/opportunities", response_model=AnalyticsOpportunitiesResponse, responses=ERROR_RESPONSES)
def analytics_opportunities(
    top_n: int = Query(default=20, ge=1, le=200),
    sector_relative: bool = Query(default=False),
) -> Any:
    """Return workflow-backed ranked opportunities."""
    return _wrap_call("analytics_opportunities", service.analytics_opportunities, top_n, sector_relative)


@app.get("/analytics/signal-summary", response_model=AnalyticsSignalSummaryResponse, responses=ERROR_RESPONSES)
def analytics_signal_summary(
    top_n: int = Query(default=20, ge=1, le=200),
    sector_relative: bool = Query(default=False),
) -> Any:
    """Return workflow-backed signal summary."""
    return _wrap_call("analytics_signal_summary", service.analytics_signal_summary, top_n, sector_relative)


@app.get("/metrics", response_model=RequestMetricsResponse, responses=ERROR_RESPONSES)
def metrics() -> Any:
    """Return API request metrics snapshot."""
    snapshot = metrics_registry.snapshot()
    snapshot["cache_stats"] = service.cache_stats()
    return snapshot


@app.get("/contracts", response_model=ApiContractResponse, responses=ERROR_RESPONSES)
def contracts(request: Request) -> Any:
    """Return negotiated API contract information."""
    return _build_contract_response(request.headers.get("X-API-Version"))
