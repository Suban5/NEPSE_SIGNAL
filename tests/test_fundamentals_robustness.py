"""Tests for fundamentals fetching and normalization robustness."""

from __future__ import annotations

import sys
import types
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from nepse_api.data_fetcher import NepseApiConfig, NepseDataFetcher


def _build_config() -> NepseApiConfig:
    """Create test config with NEPSE base URL."""
    return NepseApiConfig(
        base_url="https://www.nepalstock.com.np",
        timeout_seconds=5,
        tls_verify=False,
        suppress_unofficial_client_output=True,
    )


def _setup_fake_client(monkeypatch: pytest.MonkeyPatch) -> NepseDataFetcher:
    """Setup a fetcher with fake nepse_client for testing."""

    class _FakeNepseClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout
            self.tls_verify: bool | None = None
            self.return_value: Any = {}

        def setTLSVerification(self, value: bool) -> None:
            self.tls_verify = value

        def getCompanyDetails(self, symbol: str) -> Any:
            """Mock getCompanyDetails method."""
            return self.return_value

    fake_module = types.SimpleNamespace(NepseClient=_FakeNepseClient)
    monkeypatch.setitem(sys.modules, "nepse_client", fake_module)

    return NepseDataFetcher(config=_build_config())


# --- Test normalize_fundamentals() ---
def test_normalize_fundamentals_empty_payload() -> None:
    """normalize_fundamentals should return defaults for empty payload."""
    result = NepseDataFetcher.normalize_fundamentals({})

    assert result == {
        "earnings_growth": 0.0,
        "dividend_stability": 0.0,
        "revenue_growth": 0.0,
    }


def test_normalize_fundamentals_none_payload() -> None:
    """normalize_fundamentals should return defaults for None payload."""
    result = NepseDataFetcher.normalize_fundamentals(cast(Any, None))

    assert result == {
        "earnings_growth": 0.0,
        "dividend_stability": 0.0,
        "revenue_growth": 0.0,
    }


def test_normalize_fundamentals_non_dict_payload() -> None:
    """normalize_fundamentals should return defaults for non-dict payload."""
    result = NepseDataFetcher.normalize_fundamentals(cast(Any, "invalid"))

    assert result == {
        "earnings_growth": 0.0,
        "dividend_stability": 0.0,
        "revenue_growth": 0.0,
    }


def test_normalize_fundamentals_with_valid_fields() -> None:
    """normalize_fundamentals should extract and return valid fields."""
    payload = {
        "earningsGrowth": 0.15,
        "revenueGrowth": 0.12,
        "dividendYield": 0.04,
    }
    result = NepseDataFetcher.normalize_fundamentals(payload)

    assert result["earnings_growth"] == 0.15
    assert result["revenue_growth"] == 0.12
    assert result["dividend_stability"] == 0.04


def test_normalize_fundamentals_with_alternative_field_names() -> None:
    """normalize_fundamentals should handle alternative field name variants."""
    payload = {
        "eps_growth": 0.18,  # Alternative name
        "sales_growth": 0.10,  # Alternative name
        "dividend_rate": 0.05,  # Alternative name
    }
    result = NepseDataFetcher.normalize_fundamentals(payload)

    assert result["earnings_growth"] == 0.18
    assert result["revenue_growth"] == 0.10
    assert result["dividend_stability"] == 0.05


def test_normalize_fundamentals_negative_values_clamped_to_zero() -> None:
    """normalize_fundamentals should clamp negative values to 0.0."""
    payload = {
        "earningsGrowth": -0.1,
        "revenueGrowth": -0.05,
        "dividendYield": -0.02,
    }
    result = NepseDataFetcher.normalize_fundamentals(payload)

    assert result["earnings_growth"] == 0.0
    assert result["revenue_growth"] == 0.0
    assert result["dividend_stability"] == 0.0


def test_normalize_fundamentals_out_of_range_values_preserved() -> None:
    """normalize_fundamentals should preserve values above 1.0 (percentages allowed)."""
    payload = {
        "earningsGrowth": 2.5,  # 250% growth in exceptional case
        "revenueGrowth": 1.8,  # 180% growth
        "dividendYield": 1.2,  # 120% yield (unusual but valid)
    }
    result = NepseDataFetcher.normalize_fundamentals(payload)

    assert result["earnings_growth"] == 2.5
    assert result["revenue_growth"] == 1.8
    assert result["dividend_stability"] == 1.2


def test_normalize_fundamentals_missing_fields_default_to_zero() -> None:
    """normalize_fundamentals should default missing fields to 0.0."""
    payload = {
        "earningsGrowth": 0.10,
        # revenueGrowth missing
        # dividendYield missing
    }
    result = NepseDataFetcher.normalize_fundamentals(payload)

    assert result["earnings_growth"] == 0.10
    assert result["revenue_growth"] == 0.0
    assert result["dividend_stability"] == 0.0


def test_normalize_fundamentals_mixed_valid_invalid_fields() -> None:
    """normalize_fundamentals should handle mix of valid and invalid values."""
    payload = {
        "earningsGrowth": 0.20,
        "revenueGrowth": -0.05,  # Negative - will be clamped to 0
        "dividendYield": 1.5,  # High value - preserved (percentages allowed)
    }
    result = NepseDataFetcher.normalize_fundamentals(payload)

    assert result["earnings_growth"] == 0.20
    assert result["revenue_growth"] == 0.0
    assert result["dividend_stability"] == 1.5  # High values preserved


def test_normalize_fundamentals_string_values_coerced() -> None:
    """normalize_fundamentals should coerce string numeric values."""
    payload = {
        "earningsGrowth": "0.15",  # String numeric
        "revenueGrowth": "0.12",  # String numeric
        "dividendYield": "0.04",  # String numeric
    }
    result = NepseDataFetcher.normalize_fundamentals(payload)

    assert result["earnings_growth"] == 0.15
    assert result["revenue_growth"] == 0.12
    assert result["dividend_stability"] == 0.04


def test_normalize_fundamentals_non_numeric_values_become_zero() -> None:
    """normalize_fundamentals should convert non-numeric values to 0.0."""
    payload = {
        "earningsGrowth": "invalid",
        "revenueGrowth": None,
        "dividendYield": [],
    }
    result = NepseDataFetcher.normalize_fundamentals(payload)

    assert result["earnings_growth"] == 0.0
    assert result["revenue_growth"] == 0.0
    assert result["dividend_stability"] == 0.0


# --- Test _validate_metric() ---
def test_validate_metric_returns_valid_value() -> None:
    """_validate_metric should return value when positive."""
    result = NepseDataFetcher._validate_metric(0.5, metric_name="test_metric")

    assert result == 0.5


def test_validate_metric_clamps_negative_to_zero() -> None:
    """_validate_metric should clamp negative values to 0.0."""
    result = NepseDataFetcher._validate_metric(-0.1, metric_name="test_metric")

    assert result == 0.0


def test_validate_metric_preserves_high_values() -> None:
    """_validate_metric should preserve values above 1.0 (percentages allowed)."""
    result = NepseDataFetcher._validate_metric(1.5, metric_name="test_metric")

    assert result == 1.5


def test_validate_metric_preserves_very_high_values() -> None:
    """_validate_metric should preserve very high values (exceptional growth)."""
    result = NepseDataFetcher._validate_metric(10.0, metric_name="test_metric")

    assert result == 10.0


# --- Test fetch_company_fundamentals() ---
def test_fetch_company_fundamentals_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_company_fundamentals should return payload when available."""
    fetcher = _setup_fake_client(monkeypatch)
    cast(Any, fetcher._unofficial_client).return_value = {
        "symbol": "NABIL",
        "earningsGrowth": 0.15,
        "revenueGrowth": 0.12,
        "dividendYield": 0.04,
    }

    result = fetcher.fetch_company_fundamentals("NABIL")

    assert result["symbol"] == "NABIL"
    assert result["earningsGrowth"] == 0.15


def test_fetch_company_fundamentals_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_company_fundamentals should return empty dict on empty response."""
    fetcher = _setup_fake_client(monkeypatch)
    cast(Any, fetcher._unofficial_client).return_value = {}

    result = fetcher.fetch_company_fundamentals("NABIL")

    assert result == {}


def test_fetch_company_fundamentals_invalid_response_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_company_fundamentals should return empty dict on non-dict response."""
    fetcher = _setup_fake_client(monkeypatch)
    cast(Any, fetcher._unofficial_client).return_value = "invalid"

    result = fetcher.fetch_company_fundamentals("NABIL")

    assert result == {}


def test_fetch_company_fundamentals_none_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_company_fundamentals should return empty dict on None response."""
    fetcher = _setup_fake_client(monkeypatch)
    cast(Any, fetcher._unofficial_client).return_value = None

    result = fetcher.fetch_company_fundamentals("NABIL")

    assert result == {}


def test_fetch_company_fundamentals_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_company_fundamentals should return empty dict on exception."""
    fetcher = _setup_fake_client(monkeypatch)

    # Make getCompanyDetails raise an exception
    def raise_exception(symbol: str) -> None:
        raise RuntimeError("API error")

    cast(Any, fetcher._unofficial_client).getCompanyDetails = raise_exception

    result = fetcher.fetch_company_fundamentals("NABIL")

    assert result == {}


def test_fetch_company_fundamentals_missing_method(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_company_fundamentals should return empty dict if method missing."""

    class _FakeClientNoMethod:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout
            self.tls_verify: bool | None = None

        def setTLSVerification(self, value: bool) -> None:
            self.tls_verify = value

        # Intentionally no getCompanyDetails method

    fake_module = types.SimpleNamespace(NepseClient=_FakeClientNoMethod)
    monkeypatch.setitem(sys.modules, "nepse_client", fake_module)

    fetcher = NepseDataFetcher(config=_build_config())

    result = fetcher.fetch_company_fundamentals("NABIL")

    assert result == {}


# --- Integration Tests ---
def test_fundamentals_workflow_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end workflow: fetch fundamentals and normalize."""
    fetcher = _setup_fake_client(monkeypatch)
    cast(Any, fetcher._unofficial_client).return_value = {
        "symbol": "NABIL",
        "earningsGrowth": 0.25,  # 25% growth
        "revenueGrowth": 0.18,  # 18% growth
        "dividendYield": 0.035,  # 3.5% yield
    }

    # Fetch
    payload = fetcher.fetch_company_fundamentals("NABIL")
    assert payload["symbol"] == "NABIL"

    # Normalize
    normalized = NepseDataFetcher.normalize_fundamentals(payload)
    assert normalized["earnings_growth"] == 0.25
    assert normalized["revenue_growth"] == 0.18
    assert normalized["dividend_stability"] == 0.035


def test_fundamentals_workflow_with_problematic_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end with problematic data: negative values handled, high values preserved."""
    fetcher = _setup_fake_client(monkeypatch)
    cast(Any, fetcher._unofficial_client).return_value = {
        "symbol": "RISKY",
        "earningsGrowth": -0.5,  # Negative
        "revenueGrowth": 3.0,  # Unusually high but valid
        "dividendYield": "invalid",  # Non-numeric
    }

    payload = fetcher.fetch_company_fundamentals("RISKY")
    normalized = NepseDataFetcher.normalize_fundamentals(payload)

    # Negative clamped to 0, high values preserved, non-numeric becomes 0
    assert normalized["earnings_growth"] == 0.0  # Negative clamped to 0
    assert normalized["revenue_growth"] == 3.0  # High value preserved
    assert normalized["dividend_stability"] == 0.0  # Non-numeric becomes 0


def test_fundamentals_used_in_scorer_context() -> None:
    """Fundamentals normalization used in real scorer context."""
    # Simulate real-world payload with missing/incomplete fields
    payload = {
        "eps": 45.0,
        "pe": 14.5,
        "bookValue": 250.0,
        "roe": 0.18,  # 18% ROE
        "currentRatio": 1.5,
    }

    normalized = NepseDataFetcher.normalize_fundamentals(payload)

    # Should have safe defaults for missing earnings/revenue/dividend fields
    assert normalized["earnings_growth"] == 0.0
    assert normalized["revenue_growth"] == 0.0
    assert normalized["dividend_stability"] == 0.0
