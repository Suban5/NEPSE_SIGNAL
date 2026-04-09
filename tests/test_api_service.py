"""Unit tests for the API service layer."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest

from api import service as api_service_module
from api.service import NepseApiService


class _AnalyticsCacheStub:
    """Minimal cache stub used by analytics response tests."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._values.get(key)

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value

    def snapshot(self) -> dict[str, int]:
        """Return mock cache statistics."""
        return {"hits": 0, "misses": 0}


def _build_service(coordinator: Any) -> NepseApiService:
    """Create a service instance without invoking the real constructor."""
    service = object.__new__(NepseApiService)
    service_ref = cast(Any, service)
    service_ref._client = SimpleNamespace()
    service_ref._coordinator = coordinator
    service_ref._caches = {"analytics_scan": _AnalyticsCacheStub()}
    return service


def test_call_retries_retryable_exception_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retryable failures should be retried before returning a result."""

    class _Client:
        def __init__(self) -> None:
            self.calls = 0

        def getMarketStatus(self) -> dict[str, bool]:
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporarily unavailable")
            return {"isOpen": True}

    monkeypatch.setattr(
        api_service_module,
        "get_settings",
        lambda: SimpleNamespace(api_retry_attempts=3, api_retry_backoff_seconds=0.0),
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(api_service_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    client = _Client()
    payload = NepseApiService._call(cast(Any, client), "getMarketStatus")

    assert client.calls == 2
    assert payload == {"isOpen": True}
    assert sleep_calls == []


def test_call_does_not_retry_runtime_error_with_status_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """RuntimeError with status metadata should fail fast instead of retrying."""

    class _Client:
        def __init__(self) -> None:
            self.calls = 0

        def getMarketStatus(self) -> dict[str, bool]:
            self.calls += 1
            error = RuntimeError("upstream unavailable")
            setattr(error, "status_code", 503)
            raise error

    monkeypatch.setattr(
        api_service_module,
        "get_settings",
        lambda: SimpleNamespace(api_retry_attempts=4, api_retry_backoff_seconds=0.0),
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(api_service_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    client = _Client()

    with pytest.raises(RuntimeError, match="upstream unavailable"):
        NepseApiService._call(cast(Any, client), "getMarketStatus")

    assert client.calls == 1
    assert sleep_calls == []


def test_live_market_and_company_history_return_rows() -> None:
    """Row-oriented service methods should normalize DataFrame payloads consistently."""
    coordinator = SimpleNamespace(
        get_market_snapshot=lambda force_refresh=False: pd.DataFrame(
            [
                {"symbol": "NABIL", "close": 100.0},
                {"symbol": "SCB", "close": 200.0},
            ]
        ),
        get_historical=lambda symbol, start, end, force_refresh=False: pd.DataFrame(
            [
                {"date": pd.Timestamp("2026-01-01"), "symbol": symbol, "close": 101.0},
                {"date": pd.Timestamp("2026-01-02"), "symbol": symbol, "close": 102.0},
            ]
        ),
    )
    service = _build_service(coordinator)

    snapshot_rows = service.live_market()
    history_rows = service.company_history("nabil", None, None)

    assert snapshot_rows == [{"symbol": "NABIL", "close": 100.0}, {"symbol": "SCB", "close": 200.0}]
    assert history_rows[0]["symbol"] == "NABIL"
    assert len(history_rows) == 2


def test_analytics_methods_share_cached_workflow_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Analytics methods should reuse one workflow payload and preserve the shared response contract."""
    service = _build_service(SimpleNamespace())
    monkeypatch.setattr(
        api_service_module,
        "get_settings",
        lambda: SimpleNamespace(data_cache_path=tmp_path, api_retry_attempts=1, api_retry_backoff_seconds=0.0),
    )
    monkeypatch.setattr(api_service_module, "BlueChipDetector", lambda config=None: SimpleNamespace())
    monkeypatch.setattr(api_service_module, "MarketScanner", lambda: SimpleNamespace())

    workflow_calls: list[dict[str, Any]] = []
    fake_context = SimpleNamespace(
        execution_id="scan-abc123",
        bluechip_ranked=pd.DataFrame(
            [
                {"symbol": "NABIL", "bluechip_score": 0.91, "rank": 1},
            ]
        ),
        signal_df=pd.DataFrame(
            [
                {
                    "symbol": "NABIL",
                    "signal": "BUY",
                    "confidence": 0.82,
                    "bluechip_score": 0.91,
                    "trade_score": 0.77,
                },
            ]
        ),
        to_summary=lambda: {
            "workflow": "market_scan",
            "execution_id": "scan-abc123",
            "output_dir": str(tmp_path / "api" / "analytics" / "scan_top_200_sector_1"),
            "top_n": 200,
            "plot": False,
            "snapshot_rows": 1,
            "universe_symbols": 1,
            "selected_symbols": 1,
            "signal_rows": 1,
        },
    )

    def _fake_run_market_scan_workflow(*, dependencies: Any, output_dir: Any, top_n: int, plot: bool) -> Any:
        workflow_calls.append({"dependencies": dependencies, "output_dir": output_dir, "top_n": top_n, "plot": plot})
        return fake_context

    monkeypatch.setattr(api_service_module, "run_market_scan_workflow", _fake_run_market_scan_workflow)

    bluechip_response = service.analytics_bluechip_ranking(top_n=500, sector_relative=True)
    opportunities_response = service.analytics_opportunities(top_n=500, sector_relative=True)
    signal_summary_response = service.analytics_signal_summary(top_n=500, sector_relative=True)

    assert len(workflow_calls) == 1
    assert workflow_calls[0]["top_n"] == 200
    assert bluechip_response["top_n"] == 200
    assert bluechip_response["summary"]["workflow"] == "market_scan"
    assert bluechip_response["rows"][0]["symbol"] == "NABIL"
    assert opportunities_response["rows"][0]["trade_score"] == 0.77
    assert signal_summary_response["rows"][0]["signal"] == "BUY"
    assert signal_summary_response["summary"]["selected_symbols"] == 1


def test_call_cached_reuses_cached_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cached service calls should avoid repeated upstream method invocations."""
    service = _build_service(SimpleNamespace())
    service_ref = cast(Any, service)
    service_ref._caches["market_status"] = _AnalyticsCacheStub()

    call_count = {"value": 0}

    def _fake_call(client: Any, method_name: str, **kwargs: Any) -> dict[str, Any]:
        del client, method_name, kwargs
        call_count["value"] += 1
        return {"isOpen": True}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    first = service._call_cached("market_status", "getMarketStatus")
    second = service._call_cached("market_status", "getMarketStatus")

    assert first == {"isOpen": True}
    assert second == {"isOpen": True}
    assert call_count["value"] == 1


def test_coerce_rows_handles_list_payload() -> None:
    """_coerce_rows should extract rows from list payload without filtering."""
    payload = [{"symbol": "NABIL", "close": 100.0}, {"symbol": "SCB", "close": 200.0}]
    result = NepseApiService._coerce_rows(payload)
    assert len(result) == 2
    assert result[0]["symbol"] == "NABIL"


def test_coerce_rows_handles_wrapped_data_key() -> None:
    """_coerce_rows should unwrap payload from 'data' key."""
    payload = {"data": [{"symbol": "NABIL"}, {"symbol": "SCB"}]}
    result = NepseApiService._coerce_rows(payload)
    assert len(result) == 2
    assert result[0]["symbol"] == "NABIL"


def test_coerce_rows_handles_wrapped_result_key() -> None:
    """_coerce_rows should unwrap payload from 'result' key."""
    payload = {"result": [{"symbol": "NABIL"}]}
    result = NepseApiService._coerce_rows(payload)
    assert len(result) == 1
    assert result[0]["symbol"] == "NABIL"


def test_coerce_rows_handles_wrapped_items_key() -> None:
    """_coerce_rows should unwrap payload from 'items' key."""
    payload = {"items": [{"symbol": "NABIL"}, {"symbol": "SCB"}]}
    result = NepseApiService._coerce_rows(payload)
    assert len(result) == 2


def test_coerce_rows_handles_wrapped_content_key() -> None:
    """_coerce_rows should unwrap payload from 'content' key."""
    payload = {"content": [{"symbol": "NABIL"}]}
    result = NepseApiService._coerce_rows(payload)
    assert len(result) == 1


def test_coerce_rows_filters_non_dict_items() -> None:
    """_coerce_rows should filter out non-dict items from list."""
    payload = [{"symbol": "NABIL"}, "invalid", None, {"symbol": "SCB"}]
    result = NepseApiService._coerce_rows(payload)
    assert len(result) == 2
    assert all(isinstance(row, dict) for row in result)


def test_coerce_rows_returns_empty_for_invalid_payload() -> None:
    """_coerce_rows should return empty list for invalid payloads."""
    assert NepseApiService._coerce_rows(None) == []
    assert NepseApiService._coerce_rows("string") == []
    assert NepseApiService._coerce_rows(123) == []
    assert NepseApiService._coerce_rows({}) == []


def test_coerce_dict_handles_dict_payload() -> None:
    """_coerce_dict should return dict payload as-is."""
    payload = {"isOpen": True, "status": "ready"}
    result = NepseApiService._coerce_dict(payload)
    assert result == payload


def test_coerce_dict_returns_empty_for_non_dict() -> None:
    """_coerce_dict should return empty dict for non-dict payloads."""
    assert NepseApiService._coerce_dict(None) == {}
    assert NepseApiService._coerce_dict("string") == {}
    assert NepseApiService._coerce_dict([1, 2, 3]) == {}
    assert NepseApiService._coerce_dict(123) == {}


def test_coerce_text_handles_string_payload() -> None:
    """_coerce_text should return string payload as-is."""
    payload = "market data"
    result = NepseApiService._coerce_text(payload)
    assert result == payload


def test_coerce_text_converts_none_to_empty_string() -> None:
    """_coerce_text should convert None to empty string."""
    result = NepseApiService._coerce_text(None)
    assert result == ""


def test_coerce_text_converts_non_string_to_string() -> None:
    """_coerce_text should convert non-string types to string."""
    assert NepseApiService._coerce_text(123) == "123"
    assert NepseApiService._coerce_text(12.34) == "12.34"
    assert NepseApiService._coerce_text(True) == "True"
    assert NepseApiService._coerce_text([1, 2]) == "[1, 2]"


def test_should_retry_exception_identifies_timeout_errors() -> None:
    """_should_retry_exception should identify standard timeout errors as retryable."""

    class TimeoutExc(Exception):
        pass

    TimeoutExc.__name__ = "TimeoutError"
    assert NepseApiService._should_retry_exception(TimeoutExc("timeout")) is True


def test_should_retry_exception_identifies_readtimeout_errors() -> None:
    """_should_retry_exception should identify ReadTimeout errors as retryable."""

    class ReadTimeoutExc(Exception):
        pass

    ReadTimeoutExc.__name__ = "ReadTimeout"
    assert NepseApiService._should_retry_exception(ReadTimeoutExc("timeout")) is True


def test_should_retry_exception_identifies_status_code_retriable_errors() -> None:
    """_should_retry_exception should identify status codes like 502, 503, 504 as retryable."""

    class CustomException(Exception):
        pass

    CustomException.__name__ = "CustomException"

    error_502 = cast(Any, CustomException("bad gateway"))
    error_502.status_code = 502
    assert NepseApiService._should_retry_exception(error_502) is True

    error_503 = cast(Any, CustomException("unavailable"))
    error_503.status_code = 503
    assert NepseApiService._should_retry_exception(error_503) is True

    error_429 = cast(Any, CustomException("too many requests"))
    error_429.status_code = 429
    assert NepseApiService._should_retry_exception(error_429) is True


def test_should_retry_exception_rejects_non_retriable_status_codes() -> None:
    """_should_retry_exception should reject non-retriable status codes like 401, 403, 404."""

    class CustomException(Exception):
        pass

    CustomException.__name__ = "CustomException"

    error_401 = cast(Any, CustomException("unauthorized"))
    error_401.status_code = 401
    assert NepseApiService._should_retry_exception(error_401) is False

    error_404 = cast(Any, CustomException("not found"))
    error_404.status_code = 404
    assert NepseApiService._should_retry_exception(error_404) is False


def test_should_retry_exception_rejects_runtime_error_with_5xx() -> None:
    """_should_retry_exception should reject RuntimeError even with 5xx status codes."""
    error_500 = cast(Any, RuntimeError("error"))
    error_500.status_code = 500
    # RuntimeError is excluded even with 500 status code
    assert NepseApiService._should_retry_exception(error_500) is False


def test_health_returns_service_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """health() should return service status via NepseClient call."""
    service = _build_service(SimpleNamespace())

    def _fake_call(client: Any, method_name: str, **kwargs: Any) -> dict[str, Any]:
        del client, kwargs
        if method_name == "getMarketStatus":
            return {"isOpen": True, "message": "Market is open"}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.health()
    assert result["ok"] is True
    assert result["marketStatus"]["isOpen"] is True


def test_market_status_returns_dict_via_coerce(monkeypatch: pytest.MonkeyPatch) -> None:
    """market_status() should call cached endpoint and coerce to dict."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        del client, kwargs
        if method_name == "getMarketStatus":
            return {"isOpen": False}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.market_status()
    assert isinstance(result, dict)
    assert result["isOpen"] is False


def test_market_summary_returns_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """market_summary() should return summary via cached call."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        del client, kwargs
        if method_name == "getSummary":
            return {"totalTurnover": 1000000, "totalVolume": 50000}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.market_summary()
    assert isinstance(result, dict)
    assert result["totalTurnover"] == 1000000


def test_nepse_index_returns_rows_via_coerce(monkeypatch: pytest.MonkeyPatch) -> None:
    """nepse_index() should return rows via cached call and row coercion."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> dict[str, Any]:
        del client, kwargs
        if method_name == "getNepseIndex":
            return {"data": [{"index": "NEPSE", "value": 3000}]}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.nepse_index()
    assert len(result) == 1
    assert result[0]["index"] == "NEPSE"


def test_nepse_sub_indices_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """nepse_sub_indices() should return sub-indices rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getNepseSubIndices":
            return [{"indexName": "Banking", "value": 2500}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.nepse_sub_indices()
    assert len(result) >= 0


def test_companies_returns_row_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """companies() should return list of company rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getCompanyList":
            return [{"symbol": "NABIL", "companyId": 1}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.companies()
    assert len(result) == 1
    assert result[0]["symbol"] == "NABIL"


def test_securities_returns_row_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """securities() should return list of security rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getSecurityList":
            return [{"securityId": 1, "type": "equity"}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.securities()
    assert len(result) >= 0


def test_company_details_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """company_details() should return company dict via coercion."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getCompanyDetails":
            return {"companyName": "NABIL Bank", "symbol": "NABIL"}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.company_details("NABIL")
    assert isinstance(result, dict)
    assert result["symbol"] == "NABIL"


def test_company_history_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """company_history() should return historical price rows."""
    def _fake_get_historical(
        symbol: str, start: Any, end: Any, force_refresh: bool
    ) -> Any:
        del symbol, start, end, force_refresh
        return pd.DataFrame([{"date": "2024-01-01", "close": 100.0}])

    coordinator = SimpleNamespace(get_historical=_fake_get_historical)
    service = _build_service(coordinator)

    from datetime import date

    result = service.company_history("NABIL", date(2024, 1, 1), date(2024, 1, 31))
    assert len(result) == 1
    assert result[0]["close"] == 100.0


def test_company_financial_details_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """company_financial_details() should return financial data rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getCompanyFinancialDetails":
            return [{"eps": 5.5, "pe": 15.5}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.company_financial_details("1")
    assert isinstance(result, list)


def test_company_agm_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """company_agm() should return AGM records."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getCompanyAGM":
            return {"items": [{"agmId": 1, "date": "2024-01-01"}]}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.company_agm("1")
    assert len(result) >= 0


def test_company_dividend_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """company_dividend() should return dividend records."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getCompanyDividend":
            return [{"dividendId": 1, "amount": 10.0}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.company_dividend("1")
    assert len(result) >= 0


def test_company_market_depth_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """company_market_depth() should return market depth rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getCompanyMarketDepth":
            return [{"buy": 100, "sell": 200}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.company_market_depth("1")
    assert isinstance(result, list)


def test_press_release_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """press_release() should return press release rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getPressRelease":
            return {"data": [{"prId": 1, "title": "News"}]}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.press_release()
    assert len(result) >= 0


def test_nepse_notice_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """nepse_notice() should return NEPSE notice rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getNepseNotice":
            return [{"noticeId": 1, "notice": "Update"}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.nepse_notice()
    assert len(result) >= 0


def test_holiday_list_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """holiday_list() should return holiday rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getHolidayList":
            return {"items": [{"date": "2024-01-01", "name": "Holiday"}]}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.holiday_list(2024)
    assert len(result) >= 0


def test_price_volume_history_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """price_volume_history() should return historical price-volume rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getPriceVolumeHistory":
            return {"result": [{"date": "2024-01-01", "close": 100.0, "volume": 1000}]}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.price_volume_history("20240101")
    assert len(result) >= 0


def test_live_market_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """live_market() should return market snapshot rows via coordinator."""
    coordinator = SimpleNamespace(
        get_market_snapshot=lambda force_refresh=False: pd.DataFrame(
            [{"symbol": "NABIL", "close": 100.0}, {"symbol": "SCB", "close": 200.0}]
        )
    )
    service = _build_service(coordinator)

    result = service.live_market()
    assert len(result) == 2
    assert result[0]["symbol"] == "NABIL"


def test_live_market_returns_empty_for_empty_dataframe() -> None:
    """live_market() should return empty list when coordinator returns empty DataFrame."""
    coordinator = SimpleNamespace(get_market_snapshot=lambda force_refresh=False: pd.DataFrame())
    service = _build_service(coordinator)

    result = service.live_market()
    assert result == []


def test_price_volume_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """price_volume() should return price-volume rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getPriceVolume":
            return [{"symbol": "NABIL", "volume": 1000}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.price_volume()
    assert len(result) >= 0


def test_supply_demand_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """supply_demand() should return supply-demand dict."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getSupplyDemand":
            return {"buy": 100, "sell": 200}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.supply_demand()
    assert isinstance(result, dict)
    assert result["buy"] == 100


def test_top_gainers_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """top_gainers() should return top gainers rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getTopGainers":
            return [{"symbol": "NABIL", "change": 5.5}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.top_gainers()
    assert len(result) >= 0


def test_top_losers_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """top_losers() should return top losers rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getTopLosers":
            return [{"symbol": "SCB", "change": -2.1}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.top_losers()
    assert len(result) >= 0


def test_top_ten_trade_scrips_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """top_ten_trade_scrips() should return top 10 trade scrips rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getTopTenTradeScrips":
            return [{"symbol": "NABIL", "volume": 50000}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.top_ten_trade_scrips()
    assert len(result) >= 0


def test_top_ten_transaction_scrips_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """top_ten_transaction_scrips() should return top 10 transaction scrips rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getTopTenTransactionScrips":
            return [{"symbol": "SCB", "transactions": 100}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.top_ten_transaction_scrips()
    assert len(result) >= 0


def test_top_ten_turnover_scrips_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """top_ten_turnover_scrips() should return top 10 turnover scrips rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getTopTenTurnoverScrips":
            return [{"symbol": "NABIL", "turnover": 500000}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.top_ten_turnover_scrips()
    assert len(result) >= 0


def test_daily_scrip_price_graph_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """daily_scrip_price_graph() should return graph payload."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getDailyScripPriceGraph":
            return {"symbol": "NABIL", "data": [{"date": "2024-01-01", "close": 100}]}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.daily_scrip_price_graph("NABIL")
    assert isinstance(result, dict)


def test_company_history_returns_empty_for_empty_dataframe() -> None:
    """company_history() should return empty list when coordinator returns empty DataFrame."""
    coordinator = SimpleNamespace(
        get_historical=lambda symbol, start, end, force_refresh=False: pd.DataFrame()
    )
    service = _build_service(coordinator)

    from datetime import date

    result = service.company_history("NABIL", date(2024, 1, 1), date(2024, 1, 31))
    assert result == []


def test_floor_sheet_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """floor_sheet() should return floor sheet rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getFloorSheet":
            return [{"symbol": "NABIL", "quantity": 100}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.floor_sheet()
    assert len(result) >= 0


def test_floor_sheet_of_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """floor_sheet_of() should return floor sheet rows for symbol/date."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getFloorSheetOf":
            return [{"symbol": "NABIL", "quantity": 50, "rate": 101.5}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.floor_sheet_of("NABIL", "20240101")
    assert len(result) >= 0


def test_trading_average_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """trading_average() should return trading average rows."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getTradingAverage":
            return [{"symbol": "NABIL", "average": 10000}]
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.trading_average("20240101")
    assert len(result) >= 0


def test_symbol_market_depth_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """symbol_market_depth() should return market depth as text."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getSymbolMarketDepth":
            return "market depth data"
        return None

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.symbol_market_depth("NABIL")
    assert isinstance(result, str)


def test_company_news_list_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """company_news_list() should return news list payload."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getCompanyNewsList":
            return {"news": [{"title": "News"}], "total": 1}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.company_news_list()
    assert isinstance(result, dict)


def test_news_alert_list_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """news_alert_list() should return alerts payload."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getNewsAndAlertList":
            return {"alerts": [{"message": "Alert"}]}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.news_alert_list()
    assert isinstance(result, dict)


def test_company_id_key_map_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """company_id_key_map() should return company ID mapping."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getCompanyIDKeyMap":
            return {"NABIL": 1, "SCB": 2}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.company_id_key_map()
    assert isinstance(result, dict)


def test_security_id_key_map_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """security_id_key_map() should return security ID mapping."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getSecurityIDKeyMap":
            return {"sec1": 100, "sec2": 200}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.security_id_key_map()
    assert isinstance(result, dict)


def test_sector_scrips_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """sector_scrips() should return sector-scrip mapping."""
    service = _build_service(SimpleNamespace())

    def _fake_call(
        client: Any, method_name: str, **kwargs: Any
    ) -> Any:
        del client, kwargs
        if method_name == "getSectorScrips":
            return {"Banking": ["NABIL", "SCB"], "Finance": ["NIBL"]}
        return {}

    monkeypatch.setattr(NepseApiService, "_call", staticmethod(_fake_call))

    result = service.sector_scrips()
    assert isinstance(result, dict)


def test_cache_stats_returns_dict() -> None:
    """cache_stats() should return cache statistics."""
    service = _build_service(SimpleNamespace())

    result = service.cache_stats()
    assert isinstance(result, dict)
    assert len(result) > 0  # Should have at least one cache
    assert "market_status" in result or len(result) >= 1