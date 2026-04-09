"""Unit tests for Streamlit UI API client."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
import requests

from ui.api_client import ApiClient, ApiClientConfig, ApiClientError


def _mock_response(
    *,
    status_code: int,
    payload: dict[str, Any] | None = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.text = text
    response.headers = headers or {}
    response.json = Mock(return_value=payload if payload is not None else {})
    return response


def test_get_json_success_returns_payload_and_headers() -> None:
    session = Mock(spec=requests.Session)
    session.request.return_value = _mock_response(
        status_code=200,
        payload={"ok": True},
        headers={
            "X-Request-Id": "req-123",
            "X-API-Contract-Version": "v1",
            "X-API-Supported-Versions": "v1,v2",
        },
    )

    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000"), session=session)
    result = client.health()

    assert result.payload == {"ok": True}
    assert result.request_id == "req-123"
    assert result.negotiated_version == "v1"
    assert result.supported_versions == "v1,v2"


def test_request_retries_after_transient_exception_then_succeeds() -> None:
    session = Mock(spec=requests.Session)
    session.request.side_effect = [
        requests.Timeout("timed out"),
        _mock_response(status_code=200, payload={"ok": True}),
    ]

    client = ApiClient(
        ApiClientConfig(base_url="http://localhost:8000", max_attempts=2, backoff_seconds=0),
        session=session,
    )

    result = client.health()

    assert result.payload["ok"] is True
    assert session.request.call_count == 2


def test_non_retryable_http_error_raises_api_client_error() -> None:
    session = Mock(spec=requests.Session)
    session.request.return_value = _mock_response(
        status_code=400,
        payload={"error": {"message": "bad request"}},
        text="bad request",
        headers={"X-Request-Id": "req-err"},
    )

    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000", max_attempts=3), session=session)

    with pytest.raises(ApiClientError) as exc_info:
        client.analytics_signal_summary(top_n=20, sector_relative=False)

    assert exc_info.value.status_code == 400
    assert exc_info.value.request_id == "req-err"
    assert session.request.call_count == 1


def test_invalid_top_n_is_rejected_before_request_dispatch() -> None:
    session = Mock(spec=requests.Session)
    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000"), session=session)

    with pytest.raises(ApiClientError) as exc_info:
        client.analytics_signal_summary(top_n=0, sector_relative=False)

    assert "top_n" in str(exc_info.value)
    assert session.request.call_count == 0


def test_invalid_rebalance_is_rejected_before_request_dispatch() -> None:
    session = Mock(spec=requests.Session)
    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000"), session=session)

    with pytest.raises(ApiClientError) as exc_info:
        client.analytics_backtest_summary(
            top_n=20,
            lookback_days=252,
            rebalance="daily",
            sector_relative=False,
        )

    assert "rebalance" in str(exc_info.value)
    assert session.request.call_count == 0


def test_non_boolean_sector_relative_is_rejected_before_request_dispatch() -> None:
    session = Mock(spec=requests.Session)
    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000"), session=session)

    with pytest.raises(ApiClientError) as exc_info:
        client.analytics_opportunities(top_n=20, sector_relative="false")  # type: ignore[arg-type]

    assert "sector_relative" in str(exc_info.value)
    assert session.request.call_count == 0


def test_contracts_request_uses_selected_api_version_header() -> None:
    session = Mock(spec=requests.Session)
    session.request.return_value = _mock_response(
        status_code=200,
        payload={"negotiated_version": "v2", "default_version": "v1"},
        headers={
            "X-Request-Id": "req-contract-v2",
            "X-API-Contract-Version": "v2",
            "X-API-Supported-Versions": "v1,v2",
        },
    )

    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000"), session=session)
    result = client.contracts(api_version="v2")

    assert result.negotiated_version == "v2"
    call_kwargs = session.request.call_args.kwargs
    assert call_kwargs["headers"]["X-API-Version"] == "v2"


def test_contracts_unknown_version_can_return_v1_fallback_metadata() -> None:
    session = Mock(spec=requests.Session)
    session.request.return_value = _mock_response(
        status_code=200,
        payload={"negotiated_version": "v1", "default_version": "v1"},
        headers={
            "X-Request-Id": "req-contract-fallback",
            "X-API-Contract-Version": "v1",
            "X-API-Supported-Versions": "v1,v2",
        },
    )

    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000"), session=session)
    result = client.contracts(api_version="v9")

    assert result.negotiated_version == "v1"
    assert result.payload["negotiated_version"] == "v1"


def test_fetch_endpoint_rejects_path_without_leading_slash() -> None:
    session = Mock(spec=requests.Session)
    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000"), session=session)

    with pytest.raises(ApiClientError):
        client.fetch_endpoint("market/status")

    assert session.request.call_count == 0


def test_fetch_endpoint_success_for_generic_path() -> None:
    session = Mock(spec=requests.Session)
    session.request.return_value = _mock_response(status_code=200, payload={"ok": True})
    client = ApiClient(ApiClientConfig(base_url="http://localhost:8000"), session=session)

    result = client.fetch_endpoint("/market/status", params={"x": 1}, api_version="v1")

    assert result.payload["ok"] is True
    call_kwargs = session.request.call_args.kwargs
    assert call_kwargs["url"] == "http://localhost:8000/market/status"
    assert call_kwargs["params"] == {"x": 1}
