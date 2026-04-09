"""Unit tests for UI error handling helpers."""

from __future__ import annotations

from ui.api_client import ApiClientError
from ui.utils.error_handling import classify_api_error


def test_classify_api_error_timeout_by_status_code() -> None:
    exc = ApiClientError(
        endpoint="/analytics/signal-summary",
        status_code=504,
        message="gateway timeout",
        request_id="req-timeout",
    )

    state = classify_api_error(exc)

    assert state.kind == "timeout"
    assert "request_id=req-timeout" in state.text


def test_classify_api_error_timeout_by_message() -> None:
    exc = ApiClientError(
        endpoint="/analytics/signal-summary",
        status_code=502,
        message="request timed out after 30 seconds",
        request_id="req-30",
    )

    state = classify_api_error(exc)

    assert state.kind == "timeout"


def test_classify_api_error_non_timeout() -> None:
    exc = ApiClientError(
        endpoint="/analytics/signal-summary",
        status_code=400,
        message="bad request",
        request_id="req-bad",
    )

    state = classify_api_error(exc)

    assert state.kind == "error"
    assert "status=400" in state.text
