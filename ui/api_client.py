"""HTTP API client for the read-only Streamlit dashboard.

This module centralizes API calls, retry behavior, and response diagnostics.
It intentionally performs no business logic or payload transformations.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, Mapping, Optional

import requests


logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ApiClientConfig:
    """Configuration values for API client behavior."""

    base_url: str
    timeout_seconds: float = 10.0
    max_attempts: int = 3
    backoff_seconds: float = 0.5
    default_api_version: str = "v1"


@dataclass(frozen=True)
class ApiResponse:
    """Response payload plus diagnostic metadata from API headers."""

    payload: Dict[str, Any]
    status_code: int
    request_id: Optional[str]
    negotiated_version: Optional[str]
    supported_versions: Optional[str]


class ApiClientError(RuntimeError):
    """Raised when API calls fail after retry policy is exhausted."""

    def __init__(
        self,
        *,
        endpoint: str,
        status_code: Optional[int],
        message: str,
        request_id: Optional[str] = None,
        retriable: bool = False,
    ) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.status_code = status_code
        self.request_id = request_id
        self.retriable = retriable


class ApiClient:
    """Thin HTTP client wrapper for NepseSignal API endpoints."""

    def __init__(self, config: ApiClientConfig, session: Optional[requests.Session] = None) -> None:
        self._config = config
        self._session = session or requests.Session()

    def health(self, api_version: Optional[str] = None) -> ApiResponse:
        """Fetch health endpoint response."""
        return self._get_json("/health", api_version=api_version)

    def metrics(self, api_version: Optional[str] = None) -> ApiResponse:
        """Fetch metrics endpoint response."""
        return self._get_json("/metrics", api_version=api_version)

    def contracts(self, api_version: Optional[str] = None) -> ApiResponse:
        """Fetch contract negotiation endpoint response."""
        return self._get_json("/contracts", api_version=api_version)

    def fetch_endpoint(
        self,
        endpoint: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        api_version: Optional[str] = None,
    ) -> ApiResponse:
        """Fetch any read-only endpoint for API Explorer usage."""
        if not endpoint.startswith("/"):
            raise ApiClientError(
                endpoint="parameter.endpoint",
                status_code=None,
                message="endpoint must start with '/'",
            )
        return self._get_json(endpoint, params=params, api_version=api_version)

    def analytics_signal_summary(
        self,
        *,
        top_n: int,
        sector_relative: bool,
        api_version: Optional[str] = None,
    ) -> ApiResponse:
        """Fetch signal-summary analytics rows."""
        self._validate_top_n(top_n)
        self._validate_sector_relative(sector_relative)
        return self._get_json(
            "/analytics/signal-summary",
            params={"top_n": top_n, "sector_relative": sector_relative},
            api_version=api_version,
        )

    def analytics_bluechip_ranking(
        self,
        *,
        top_n: int,
        sector_relative: bool,
        api_version: Optional[str] = None,
    ) -> ApiResponse:
        """Fetch bluechip-ranking analytics rows."""
        self._validate_top_n(top_n)
        self._validate_sector_relative(sector_relative)
        return self._get_json(
            "/analytics/bluechip-ranking",
            params={"top_n": top_n, "sector_relative": sector_relative},
            api_version=api_version,
        )

    def analytics_opportunities(
        self,
        *,
        top_n: int,
        sector_relative: bool,
        api_version: Optional[str] = None,
    ) -> ApiResponse:
        """Fetch opportunities analytics rows."""
        self._validate_top_n(top_n)
        self._validate_sector_relative(sector_relative)
        return self._get_json(
            "/analytics/opportunities",
            params={"top_n": top_n, "sector_relative": sector_relative},
            api_version=api_version,
        )

    def analytics_backtest_summary(
        self,
        *,
        top_n: int,
        lookback_days: int,
        rebalance: str,
        sector_relative: bool,
        api_version: Optional[str] = None,
    ) -> ApiResponse:
        """Fetch backtest-summary analytics payload."""
        self._validate_top_n(top_n)
        self._validate_lookback_days(lookback_days)
        self._validate_rebalance(rebalance)
        self._validate_sector_relative(sector_relative)
        return self._get_json(
            "/analytics/backtest-summary",
            params={
                "top_n": top_n,
                "lookback_days": lookback_days,
                "rebalance": rebalance,
                "sector_relative": sector_relative,
            },
            api_version=api_version,
        )

    def _get_json(
        self,
        endpoint: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        api_version: Optional[str] = None,
    ) -> ApiResponse:
        """Issue a GET request with retry policy and parse JSON response."""
        url = f"{self._config.base_url.rstrip('/')}{endpoint}"
        headers = {"X-API-Version": api_version or self._config.default_api_version}

        attempts = max(1, self._config.max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                response = self._session.request(
                    method="GET",
                    url=url,
                    params=dict(params) if params else None,
                    headers=headers,
                    timeout=self._config.timeout_seconds,
                )
            except requests.RequestException as exc:
                retriable = attempt < attempts
                if not retriable:
                    raise ApiClientError(
                        endpoint=endpoint,
                        status_code=None,
                        message=f"request failed: {exc}",
                        request_id=None,
                        retriable=False,
                    ) from exc
                self._sleep_before_retry(attempt)
                continue

            if response.status_code >= 400:
                request_id = response.headers.get("X-Request-Id")
                retriable = response.status_code in RETRYABLE_STATUS_CODES and attempt < attempts
                if retriable:
                    self._sleep_before_retry(attempt)
                    continue
                raise ApiClientError(
                    endpoint=endpoint,
                    status_code=response.status_code,
                    message=response.text or f"request failed with status {response.status_code}",
                    request_id=request_id,
                    retriable=False,
                )

            payload = self._parse_json(response=response, endpoint=endpoint)
            return ApiResponse(
                payload=payload,
                status_code=response.status_code,
                request_id=response.headers.get("X-Request-Id"),
                negotiated_version=response.headers.get("X-API-Contract-Version"),
                supported_versions=response.headers.get("X-API-Supported-Versions"),
            )

        raise ApiClientError(
            endpoint=endpoint,
            status_code=None,
            message="request failed after retries",
            retriable=False,
        )

    @staticmethod
    def _validate_top_n(top_n: int) -> None:
        """Validate top_n contract: int between 1 and 200."""
        if not isinstance(top_n, int) or isinstance(top_n, bool):
            raise ApiClientError(endpoint="parameter.top_n", status_code=None, message="top_n must be an integer")
        if top_n < 1 or top_n > 200:
            raise ApiClientError(endpoint="parameter.top_n", status_code=None, message="top_n must be between 1 and 200")

    @staticmethod
    def _validate_lookback_days(lookback_days: int) -> None:
        """Validate lookback_days contract: int between 1 and 2000."""
        if not isinstance(lookback_days, int) or isinstance(lookback_days, bool):
            raise ApiClientError(
                endpoint="parameter.lookback_days",
                status_code=None,
                message="lookback_days must be an integer",
            )
        if lookback_days < 1 or lookback_days > 2000:
            raise ApiClientError(
                endpoint="parameter.lookback_days",
                status_code=None,
                message="lookback_days must be between 1 and 2000",
            )

    @staticmethod
    def _validate_rebalance(rebalance: str) -> None:
        """Validate rebalance contract: static, weekly, or monthly."""
        allowed = {"static", "weekly", "monthly"}
        if rebalance not in allowed:
            raise ApiClientError(
                endpoint="parameter.rebalance",
                status_code=None,
                message="rebalance must be one of: static, weekly, monthly",
            )

    @staticmethod
    def _validate_sector_relative(sector_relative: bool) -> None:
        """Validate sector_relative contract: boolean."""
        if not isinstance(sector_relative, bool):
            raise ApiClientError(
                endpoint="parameter.sector_relative",
                status_code=None,
                message="sector_relative must be a boolean",
            )

    @staticmethod
    def _parse_json(response: requests.Response, endpoint: str) -> Dict[str, Any]:
        """Parse JSON payload and return dict shape required by UI layer."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiClientError(
                endpoint=endpoint,
                status_code=response.status_code,
                message="response is not valid JSON",
                request_id=response.headers.get("X-Request-Id"),
                retriable=False,
            ) from exc

        if not isinstance(payload, dict):
            raise ApiClientError(
                endpoint=endpoint,
                status_code=response.status_code,
                message="response JSON must be an object",
                request_id=response.headers.get("X-Request-Id"),
                retriable=False,
            )
        return payload

    def _sleep_before_retry(self, attempt: int) -> None:
        """Apply linear backoff between retry attempts."""
        sleep_seconds = max(0.0, self._config.backoff_seconds) * attempt
        if sleep_seconds <= 0:
            return
        logger.debug("Retrying API request after %.3fs", sleep_seconds)
        time.sleep(sleep_seconds)
