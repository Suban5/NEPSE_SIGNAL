"""Integration-style tests for FastAPI route layer and error mapping."""

from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from api import app as api_app_module
from workflows.errors import WorkflowRankingError, WorkflowValidationError


client = TestClient(api_app_module.app)


def test_health_endpoint_returns_service_payload(monkeypatch) -> None:
    """Health endpoint should return service payload."""
    monkeypatch.setattr(api_app_module.service, "health", lambda: {"ok": True, "marketStatus": {"isOpen": True}})

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.headers["x-request-id"]


def test_market_status_endpoint_returns_rows(monkeypatch) -> None:
    """Market status endpoint should return mapped payload."""
    monkeypatch.setattr(api_app_module.service, "market_status", lambda: {"isOpen": False})

    response = client.get("/market/status")

    assert response.status_code == 200
    assert response.json() == {"isOpen": False}


def test_company_details_endpoint_uses_path_param(monkeypatch) -> None:
    """Company endpoint should pass symbol and return details."""

    def _company_details(symbol: str):
        return {"symbol": symbol, "lastTradedPrice": 100}

    monkeypatch.setattr(api_app_module.service, "company_details", _company_details)

    response = client.get("/companies/NABIL")

    assert response.status_code == 200
    assert response.json()["symbol"] == "NABIL"


def test_trading_average_endpoint_passes_query_params(monkeypatch) -> None:
    """Trading average endpoint should pass query params to service call."""

    def _trading_average(business_date: str, n_days: int):
        return {"businessDate": business_date, "nDays": n_days}

    monkeypatch.setattr(api_app_module.service, "trading_average", _trading_average)

    response = client.get("/trading/average", params={"business_date": "2026-01-15", "n_days": 30})

    assert response.status_code == 200
    payload = response.json()
    assert payload["businessDate"] == "2026-01-15"
    assert payload["nDays"] == 30


def test_news_alerts_endpoint_returns_payload(monkeypatch) -> None:
    """News alerts endpoint should return list payload."""

    def _news_alerts(page: int, page_size: int, is_strip_tags: bool):
        return {"page": page, "pageSize": page_size, "stripTags": is_strip_tags, "items": []}

    monkeypatch.setattr(api_app_module.service, "news_alert_list", _news_alerts)

    response = client.get(
        "/news/alerts",
        params={"page": 1, "page_size": 25, "is_strip_tags": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["pageSize"] == 25


def test_wrap_call_maps_generic_exception_to_502(monkeypatch) -> None:
    """Unknown upstream exceptions should map to HTTP 502 with structured detail."""

    def _raise_error():
        raise RuntimeError("service unavailable")

    monkeypatch.setattr(api_app_module.service, "market_status", _raise_error)

    response = client.get("/market/status")

    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "UPSTREAM_ERROR"
    assert payload["detail"]["error"]["type"] == "RuntimeError"
    assert payload["detail"]["error"]["method"] == "market_status"
    assert payload["detail"]["error"]["error_id"]
    assert payload["detail"]["error"]["retriable"] is True


def test_wrap_call_preserves_upstream_status_code(monkeypatch) -> None:
    """Exceptions exposing status_code should preserve that code in HTTP response."""

    class UpstreamAuthError(Exception):
        """Custom upstream auth error with status code metadata."""

        status_code = 401

    def _raise_error():
        raise UpstreamAuthError("token expired")

    monkeypatch.setattr(api_app_module.service, "market_status", _raise_error)

    response = client.get("/market/status")

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["error"]["type"] == "UpstreamAuthError"
    assert payload["detail"]["error"]["message"] == "token expired"
    assert payload["detail"]["error"]["upstream_status"] == 401
    assert payload["detail"]["error"]["retriable"] is False


def test_wrap_call_exposes_workflow_classification(monkeypatch) -> None:
    """Workflow failures should surface category and stage metadata in the API payload."""

    def _raise_error():
        raise WorkflowValidationError("market_status", "validate", "invalid workflow input")

    monkeypatch.setattr(api_app_module.service, "market_status", _raise_error)

    response = client.get("/market/status")

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error"]["category"] == "validation"
    assert payload["detail"]["error"]["stage"] == "validate"
    assert payload["detail"]["error"]["workflow"] == "market_status"
    assert payload["detail"]["error"]["retriable"] is False


def test_wrap_call_exposes_ranking_workflow_classification(monkeypatch) -> None:
    """Ranking workflow failures should preserve category and status metadata."""

    def _raise_error():
        raise WorkflowRankingError("market_status", "rank", "ranking failed")

    monkeypatch.setattr(api_app_module.service, "market_status", _raise_error)

    response = client.get("/market/status")

    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"]["error"]["category"] == "ranking"
    assert payload["detail"]["error"]["stage"] == "rank"
    assert payload["detail"]["error"]["workflow"] == "market_status"
    assert payload["detail"]["error"]["retriable"] is False


def test_wrap_call_with_timeout_maps_timeout_to_http_504(monkeypatch) -> None:
    """Timeout wrapper should return a stable 504 contract when the worker future times out."""

    class _TimeoutFuture:
        def result(self, timeout: int):
            del timeout
            raise FutureTimeoutError()

    class _TimeoutExecutor:
        def submit(self, fn, *args, **kwargs):
            del fn, args, kwargs
            return _TimeoutFuture()

        def shutdown(self, wait: bool, cancel_futures: bool) -> None:
            del wait, cancel_futures

    monkeypatch.setattr(api_app_module, "ThreadPoolExecutor", lambda max_workers: _TimeoutExecutor())

    with pytest.raises(HTTPException) as exc_info:
        api_app_module._wrap_call_with_timeout("floor_sheet", 3, lambda: [])

    error = exc_info.value
    assert error.status_code == 504
    detail = cast(dict[str, Any], error.detail)
    assert detail["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert detail["error"]["method"] == "floor_sheet"
    assert detail["error"]["message"] == "Request timed out after 3 seconds"


def test_openapi_exposes_contract_models() -> None:
    """OpenAPI should expose request/response models for typed routes."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    assert "HealthResponse" in schemas
    assert "ApiErrorResponse" in schemas
    assert "NewsListResponse" in schemas
    assert "GenericObjectResponse" in schemas
    assert "RequestMetricsResponse" in schemas
    assert "ApiContractResponse" in schemas
    assert "AnalyticsOpportunitiesResponse" in schemas
    assert "AnalyticsSignalSummaryResponse" in schemas
    assert "AnalyticsBluechipRankingResponse" in schemas
    assert "WorkflowSummary" in schemas


def test_metrics_endpoint_returns_snapshot() -> None:
    """Metrics endpoint should expose runtime request counters."""
    response = client.get("/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert "request_count" in payload
    assert "status_counts" in payload
    assert "cache_stats" in payload


def test_contracts_endpoint_returns_versions() -> None:
    """Contracts endpoint should expose supported API versions."""
    response = client.get("/contracts", headers={"X-API-Version": "v2"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_version"] == "v1"
    assert payload["negotiated_version"] == "v2"
    assert payload["supported_versions"] == ["v1", "v2"]
    assert response.headers["x-api-contract-version"] == "v2"


def test_analytics_bluechip_ranking_endpoint_returns_rows(monkeypatch) -> None:
    """Analytics bluechip endpoint should return workflow-backed rows."""

    def _bluechip(top_n: int, sector_relative: bool):
        return {
            "top_n": top_n,
            "sector_relative": sector_relative,
            "execution_id": "scan-abc123",
            "summary": {
                "workflow": "market_scan",
                "execution_id": "scan-abc123",
                "output_dir": "output/api/analytics/scan_top_5_sector_1",
                "top_n": 5,
                "plot": False,
                "snapshot_rows": 12,
                "universe_symbols": 8,
                "selected_symbols": 5,
                "signal_rows": 5,
            },
            "rows": [{"symbol": "NABIL", "bluechip_score": 0.91}],
        }

    monkeypatch.setattr(api_app_module.service, "analytics_bluechip_ranking", _bluechip)

    response = client.get("/analytics/bluechip-ranking", params={"top_n": 5, "sector_relative": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["top_n"] == 5
    assert payload["sector_relative"] is True
    assert payload["execution_id"] == "scan-abc123"
    assert payload["summary"]["workflow"] == "market_scan"
    assert payload["summary"]["selected_symbols"] == 5
    assert payload["rows"][0]["symbol"] == "NABIL"


def test_analytics_opportunities_endpoint_returns_rows(monkeypatch) -> None:
    """Analytics opportunities endpoint should return ranked rows."""

    def _opportunities(top_n: int, sector_relative: bool):
        return {
            "top_n": top_n,
            "sector_relative": sector_relative,
            "execution_id": "scan-def456",
            "summary": {
                "workflow": "market_scan",
                "execution_id": "scan-def456",
                "output_dir": "output/api/analytics/scan_top_10_sector_0",
                "top_n": 10,
                "plot": False,
                "snapshot_rows": 12,
                "universe_symbols": 8,
                "selected_symbols": 5,
                "signal_rows": 5,
            },
            "rows": [{"symbol": "SCB", "trade_score": 0.77}],
        }

    monkeypatch.setattr(api_app_module.service, "analytics_opportunities", _opportunities)

    response = client.get("/analytics/opportunities", params={"top_n": 10, "sector_relative": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["top_n"] == 10
    assert payload["sector_relative"] is False
    assert payload["execution_id"] == "scan-def456"
    assert payload["summary"]["workflow"] == "market_scan"
    assert payload["rows"][0]["symbol"] == "SCB"


def test_analytics_signal_summary_endpoint_returns_rows(monkeypatch) -> None:
    """Analytics signal summary endpoint should return summarized rows."""

    def _summary(top_n: int, sector_relative: bool):
        return {
            "top_n": top_n,
            "sector_relative": sector_relative,
            "execution_id": "scan-ghi789",
            "summary": {
                "workflow": "market_scan",
                "execution_id": "scan-ghi789",
                "output_dir": "output/api/analytics/scan_top_8_sector_1",
                "top_n": 8,
                "plot": False,
                "snapshot_rows": 12,
                "universe_symbols": 8,
                "selected_symbols": 5,
                "signal_rows": 5,
            },
            "rows": [{"symbol": "NICA", "signal": "BUY", "confidence": 0.82}],
        }

    monkeypatch.setattr(api_app_module.service, "analytics_signal_summary", _summary)

    response = client.get("/analytics/signal-summary", params={"top_n": 8, "sector_relative": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["top_n"] == 8
    assert payload["sector_relative"] is True
    assert payload["execution_id"] == "scan-ghi789"
    assert payload["summary"]["workflow"] == "market_scan"
    assert payload["rows"][0]["signal"] == "BUY"
