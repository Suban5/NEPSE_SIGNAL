"""Tests for upstream/persisted provider layer wrappers."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from nepse_api.providers import (
    NepseClientProvider,
    PersistedHistoryProvider,
    PersistedSnapshotProvider,
    RetryPolicy,
)


def test_retry_policy_defaults() -> None:
    policy = RetryPolicy()

    assert policy.attempts == 3
    assert policy.backoff_seconds == 0.25
    assert policy.jitter_seconds == 0.10


def test_get_live_market_raw_calls_client_method() -> None:
    client = SimpleNamespace(getLiveMarket=lambda: [{"symbol": "NABIL"}])
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=1), suppress_output=False)

    result = provider.get_live_market_raw()

    assert result == [{"symbol": "NABIL"}]


def test_get_security_list_raw_calls_client_method() -> None:
    client = SimpleNamespace(getSecurityList=lambda: [{"symbol": "NABIL"}])
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=1), suppress_output=False)

    result = provider.get_security_list_raw()

    assert result == [{"symbol": "NABIL"}]


def test_get_sector_scrips_raw_calls_client_method() -> None:
    client = SimpleNamespace(getSectorScrips=lambda: {"BANKING": ["NABIL"]})
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=1), suppress_output=False)

    result = provider.get_sector_scrips_raw()

    assert result == {"BANKING": ["NABIL"]}


def test_get_company_history_raw_uppercases_symbol_and_passes_dates() -> None:
    seen: dict[str, Any] = {}

    def _history(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return [{"date": "2024-01-01", "close": 1000}]

    client = SimpleNamespace(getCompanyPriceVolumeHistory=_history)
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=1), suppress_output=False)

    result = provider.get_company_history_raw("nabil", date(2024, 1, 1), date(2024, 1, 31))

    assert result == [{"date": "2024-01-01", "close": 1000}]
    assert seen["symbol"] == "NABIL"
    assert seen["start_date"] == date(2024, 1, 1)
    assert seen["end_date"] == date(2024, 1, 31)


def test_get_company_details_raw_uppercases_symbol() -> None:
    seen: dict[str, Any] = {}

    def _details(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return {"symbol": kwargs["symbol"]}

    client = SimpleNamespace(getCompanyDetails=_details)
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=1), suppress_output=False)

    result = provider.get_company_details_raw("nabil")

    assert result == {"symbol": "NABIL"}
    assert seen["symbol"] == "NABIL"


def test_call_with_retry_returns_on_first_success() -> None:
    client = SimpleNamespace(getLiveMarket=lambda: [1])
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=3), suppress_output=False)

    assert provider._call_with_retry("getLiveMarket") == [1]


def test_call_with_retry_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def _flaky() -> list[int]:
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("temporary")
        return [42]

    sleeps: list[float] = []

    import nepse_api.providers as module

    monkeypatch.setattr(module.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))

    client = SimpleNamespace(getLiveMarket=_flaky)
    provider = NepseClientProvider(
        client=client,
        retry=RetryPolicy(attempts=3, backoff_seconds=0.5, jitter_seconds=0.1),
        suppress_output=False,
    )

    result = provider._call_with_retry("getLiveMarket")

    assert result == [42]
    assert calls["count"] == 3
    assert sleeps == [0.5, 1.0]


def test_call_with_retry_raises_last_exception_after_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    err = ValueError("hard fail")

    def _always_fail() -> Any:
        raise err

    import nepse_api.providers as module

    monkeypatch.setattr(module.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)

    client = SimpleNamespace(getLiveMarket=_always_fail)
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=2), suppress_output=False)

    with pytest.raises(ValueError, match="hard fail"):
        provider._call_with_retry("getLiveMarket")


def test_call_with_retry_does_not_sleep_when_backoff_non_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def _flaky() -> Any:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("once")
        return "ok"

    sleeps: list[float] = []

    import nepse_api.providers as module

    monkeypatch.setattr(module.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))

    client = SimpleNamespace(getLiveMarket=_flaky)
    provider = NepseClientProvider(
        client=client,
        retry=RetryPolicy(attempts=2, backoff_seconds=0.0, jitter_seconds=0.0),
        suppress_output=False,
    )

    assert provider._call_with_retry("getLiveMarket") == "ok"
    assert sleeps == []


def test_call_with_retry_suppresses_stdout_and_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    def _chatty() -> dict[str, bool]:
        print("stdout noise")
        import sys

        print("stderr noise", file=sys.stderr)
        return {"ok": True}

    client = SimpleNamespace(getLiveMarket=_chatty)
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=1), suppress_output=True)

    result = provider._call_with_retry("getLiveMarket")

    captured = capsys.readouterr()
    assert result == {"ok": True}
    assert captured.out == ""
    assert captured.err == ""


def test_call_with_retry_allows_output_when_suppression_disabled(capsys: pytest.CaptureFixture[str]) -> None:
    def _chatty() -> str:
        print("hello")
        return "ok"

    client = SimpleNamespace(getLiveMarket=_chatty)
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=1), suppress_output=False)

    result = provider._call_with_retry("getLiveMarket")

    captured = capsys.readouterr()
    assert result == "ok"
    assert "hello" in captured.out


def test_call_with_retry_raises_attribute_error_when_method_missing() -> None:
    client = SimpleNamespace()
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=2), suppress_output=False)

    with pytest.raises(AttributeError):
        provider._call_with_retry("missingMethod")


def test_call_with_retry_raises_runtime_error_when_attempts_zero() -> None:
    client = SimpleNamespace(getLiveMarket=lambda: [1])
    provider = NepseClientProvider(client=client, retry=RetryPolicy(attempts=0), suppress_output=False)

    with pytest.raises(RuntimeError, match="Failed call: getLiveMarket"):
        provider._call_with_retry("getLiveMarket")


def test_persisted_snapshot_provider_load_latest() -> None:
    expected = pd.DataFrame([{"symbol": "NABIL"}])
    persistence = SimpleNamespace(load_latest_snapshot=lambda: expected)
    provider = PersistedSnapshotProvider(persistence)

    loaded = provider.load_latest()

    assert loaded is expected


def test_persisted_snapshot_provider_save() -> None:
    saved: dict[str, Any] = {}

    def _save(df: pd.DataFrame) -> None:
        saved["df"] = df

    persistence = SimpleNamespace(save_snapshot=_save)
    provider = PersistedSnapshotProvider(persistence)
    frame = pd.DataFrame([{"symbol": "NABIL"}])

    provider.save(frame)

    assert saved["df"] is frame


def test_persisted_history_provider_load_many() -> None:
    expected = {"NABIL": pd.DataFrame([{"close": 1000}])}
    persistence = SimpleNamespace(load_universe=lambda symbols: expected)
    provider = PersistedHistoryProvider(persistence)

    loaded = provider.load_many(["NABIL"])

    assert loaded == expected


def test_persisted_history_provider_save_one() -> None:
    called: dict[str, Any] = {}

    def _save(symbol: str, frame: pd.DataFrame) -> None:
        called["symbol"] = symbol
        called["frame"] = frame

    persistence = SimpleNamespace(save_historical=_save)
    provider = PersistedHistoryProvider(persistence)
    frame = pd.DataFrame([{"close": 1000}])

    provider.save_one("NABIL", frame)

    assert called["symbol"] == "NABIL"
    assert called["frame"] is frame
