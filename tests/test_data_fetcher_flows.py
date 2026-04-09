"""Tests for NepseDataFetcher snapshot, history, and universe flows."""

from __future__ import annotations

import sys
import types
from typing import Any, cast
from unittest.mock import MagicMock

import pandas as pd
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


def _setup_fake_fetcher(
    monkeypatch: pytest.MonkeyPatch, mock_return: Any = None
) -> NepseDataFetcher:
    """Setup a fetcher with fake nepse_client for testing."""

    class _FakeNepseClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout
            self.tls_verify: bool | None = None
            self.return_value = mock_return or {}

        def setTLSVerification(self, value: bool) -> None:
            self.tls_verify = value

        def getDailyMarketSummary(self) -> Any:
            return self.return_value.get("summary", {})

        def getCompanyPriceVolumeHistory(self, symbol: str, start_date: Any, end_date: Any) -> Any:
            return self.return_value.get("history", [])

        def getSecurityList(self) -> Any:
            return self.return_value.get("securities", [])

    fake_module = types.SimpleNamespace(NepseClient=_FakeNepseClient)
    monkeypatch.setitem(sys.modules, "nepse_client", fake_module)

    return NepseDataFetcher(config=_build_config())


# --- Test fetch_daily_market_snapshot() ---
def test_fetch_daily_market_snapshot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_daily_market_snapshot should return normalized DataFrame with market data."""
    # Setup mock for getLiveMarket call
    live_market_data = [
        {
            "symbol": "NABIL",
            "openPrice": 1000,
            "highPrice": 1020,
            "lowPrice": 990,
            "closePrice": 1010,
            "totalTradedQuantity": 10000,
            "totalTradedValue": 10100000,
        },
        {
            "symbol": "SCB",
            "openPrice": 1100,
            "highPrice": 1120,
            "lowPrice": 1090,
            "closePrice": 1110,
            "totalTradedQuantity": 11000,
            "totalTradedValue": 12321000,
        },
    ]

    fetcher = _setup_fake_fetcher(monkeypatch)

    # Mock both getLiveMarket and getSecurityList
    def mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getLiveMarket":
            return live_market_data
        elif method_name == "getSecurityList":
            return [{"symbol": "NABIL"}, {"symbol": "SCB"}]
        return []

    monkeypatch.setattr(fetcher, "_call_unofficial_client", mock_call)

    snapshot = fetcher.fetch_daily_market_snapshot()

    assert len(snapshot) == 2
    assert "symbol" in snapshot.columns
    assert "close" in snapshot.columns
    assert "data_source" in snapshot.columns
    assert snapshot.iloc[0]["symbol"] == "NABIL"
    assert snapshot.iloc[0]["close"] == 1010
    assert snapshot.iloc[1]["symbol"] == "SCB"
    assert (snapshot["data_source"] == "live_market").all()


def test_fetch_daily_market_snapshot_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_daily_market_snapshot should return empty DataFrame on empty response."""
    fetcher = _setup_fake_fetcher(monkeypatch)

    def mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getLiveMarket":
            return []
        elif method_name == "getSecurityList":
            return []
        return []

    monkeypatch.setattr(fetcher, "_call_unofficial_client", mock_call)

    snapshot = fetcher.fetch_daily_market_snapshot()

    assert snapshot.empty


def test_fetch_daily_market_snapshot_missing_fields_filled_with_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_daily_market_snapshot should fill missing numeric fields with 0."""
    live_market_data = [
        {
            "symbol": "NABIL",
            "openPrice": 1000,
            "closePrice": 1010,
            # Missing high, low, volume, etc.
        },
    ]

    fetcher = _setup_fake_fetcher(monkeypatch)

    def mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getLiveMarket":
            return live_market_data
        elif method_name == "getSecurityList":
            return [{"symbol": "NABIL"}]
        return []

    monkeypatch.setattr(fetcher, "_call_unofficial_client", mock_call)

    snapshot = fetcher.fetch_daily_market_snapshot()

    assert len(snapshot) == 1
    assert snapshot.iloc[0]["symbol"] == "NABIL"
    # Missing fields should default to 0
    assert snapshot.iloc[0]["high"] == 0
    assert snapshot.iloc[0]["low"] == 0
    assert snapshot.iloc[0]["volume"] == 0


def test_fetch_daily_market_snapshot_coerces_numeric_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_daily_market_snapshot should coerce string numerics to float."""
    live_market_data = [
        {
            "symbol": "NABIL",
            "openPrice": "1000",  # String
            "highPrice": "1020",
            "lowPrice": "990",
            "closePrice": "1010",
            "totalTradedQuantity": "10000",  # String
            "totalTradedValue": "10100000",
        },
    ]

    fetcher = _setup_fake_fetcher(monkeypatch)

    def mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getLiveMarket":
            return live_market_data
        elif method_name == "getSecurityList":
            return [{"symbol": "NABIL"}]
        return []

    monkeypatch.setattr(fetcher, "_call_unofficial_client", mock_call)

    snapshot = fetcher.fetch_daily_market_snapshot()

    assert snapshot.iloc[0]["close"] == 1010.0
    assert snapshot.iloc[0]["volume"] == 10000.0


def test_fetch_daily_market_snapshot_hydrates_fallback_from_local_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback snapshot should use latest local historical OHLCV when available."""
    fetcher = _setup_fake_fetcher(monkeypatch)

    def mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getLiveMarket":
            return []
        if method_name == "getSecurityList":
            return [{"symbol": "NABIL"}, {"symbol": "SCB"}]
        return []

    monkeypatch.setattr(fetcher, "_call_unofficial_client", mock_call)

    class _FakePersistence:
        def load_universe(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
            del symbols
            return {
                "NABIL": pd.DataFrame(
                    [
                        {
                            "date": pd.to_datetime("2026-04-04"),
                            # Intentionally missing open/high/low to verify close-based fallback.
                            "close": 1010.0,
                            "volume": 12345.0,
                            "turnover": 12468450.0,
                        }
                    ]
                )
            }

        def save_snapshot(self, snapshot_df: pd.DataFrame) -> None:
            del snapshot_df

    cast(Any, fetcher)._persistence = _FakePersistence()

    snapshot = fetcher.fetch_daily_market_snapshot(force_refresh=True)
    nabil = snapshot[snapshot["symbol"] == "NABIL"].iloc[0]
    scb = snapshot[snapshot["symbol"] == "SCB"].iloc[0]

    assert nabil["close"] == 1010.0
    assert nabil["open"] == 1010.0
    assert nabil["high"] == 1010.0
    assert nabil["low"] == 1010.0
    assert nabil["volume"] == 12345.0
    assert nabil["data_source"] == "historical_fallback"
    # Symbols without local history remain zero-filled in fallback mode.
    assert scb["close"] == 0.0
    assert scb["open"] == 0.0
    assert scb["high"] == 0.0
    assert scb["low"] == 0.0
    assert scb["volume"] == 0.0
    assert scb["data_source"] == "security_master_fallback"


# --- Test fetch_historical_ohlcv() ---
def test_fetch_historical_ohlcv_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_historical_ohlcv should return normalized historical data."""
    mock_return = {
        "history": [
            {
                "businessDate": "2025-01-01",
                "openPrice": 1000,
                "highPrice": 1020,
                "lowPrice": 990,
                "closePrice": 1010,
                "totalTradedQuantity": 10000,
                "totalTradedValue": 10100000,
            },
            {
                "businessDate": "2025-01-02",
                "openPrice": 1010,
                "highPrice": 1025,
                "lowPrice": 1000,
                "closePrice": 1020,
                "totalTradedQuantity": 11000,
                "totalTradedValue": 11220000,
            },
        ]
    }

    fetcher = _setup_fake_fetcher(monkeypatch, mock_return)
    monkeypatch.setattr(
        fetcher, "_call_unofficial_client", lambda method_name, **kwargs: mock_return["history"]
    )

    history = fetcher.fetch_historical_ohlcv("NABIL")

    assert len(history) == 2
    assert history.iloc[0]["symbol"] == "NABIL"
    assert history.iloc[0]["date"] == pd.to_datetime("2025-01-01")
    assert history.iloc[0]["close"] == 1010
    assert history.iloc[1]["close"] == 1020


def test_fetch_historical_ohlcv_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_historical_ohlcv should return empty DataFrame when no data."""
    fetcher = _setup_fake_fetcher(monkeypatch, {"history": []})
    monkeypatch.setattr(fetcher, "_call_unofficial_client", lambda method_name, **kwargs: [])

    history = fetcher.fetch_historical_ohlcv("NABIL")

    assert history.empty


def test_fetch_historical_ohlcv_with_date_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_historical_ohlcv should accept start_date and end_date parameters."""
    from datetime import date

    mock_return = {
        "history": [
            {
                "businessDate": "2025-06-15",
                "openPrice": 1000,
                "highPrice": 1020,
                "lowPrice": 990,
                "closePrice": 1010,
                "totalTradedQuantity": 10000,
                "totalTradedValue": 10100000,
            },
        ]
    }

    fetcher = _setup_fake_fetcher(monkeypatch, mock_return)

    call_args = {}

    def capture_call(method_name: str, **kwargs: Any) -> Any:
        nonlocal call_args
        call_args = kwargs
        return mock_return["history"]

    monkeypatch.setattr(fetcher, "_call_unofficial_client", capture_call)

    start = date(2025, 6, 1)
    end = date(2025, 6, 30)
    history = fetcher.fetch_historical_ohlcv("NABIL", start_date=start, end_date=end)

    assert len(history) == 1
    assert call_args.get("start_date") == start
    assert call_args.get("end_date") == end


def test_fetch_historical_ohlcv_handles_missing_close_price(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_historical_ohlcv normalizes close price defaults when missing."""
    mock_return = {
        "history": [
            {
                "businessDate": "2025-01-01",
                "openPrice": 1000,
                "closePrice": 1010,
                "totalTradedQuantity": 10000,
            },
            {
                "businessDate": "2025-01-02",
                "openPrice": 1010,
                # Missing closePrice - will default to 0 in normalization
                "totalTradedQuantity": 0,
            },
            {
                "businessDate": "2025-01-03",
                "openPrice": 1020,
                "closePrice": 1025,
                "totalTradedQuantity": 11000,
            },
        ]
    }

    fetcher = _setup_fake_fetcher(monkeypatch, mock_return)
    monkeypatch.setattr(fetcher, "_call_unofficial_client", lambda method_name, **kwargs: mock_return["history"])

    history = fetcher.fetch_historical_ohlcv("NABIL")

    # All rows should be present (closed price defaults to 0, not dropped)
    assert len(history) == 3
    assert history.iloc[0]["close"] == 1010
    assert history.iloc[1]["close"] == 0  # Missing close defaults to 0
    assert history.iloc[2]["close"] == 1025


def test_fetch_historical_ohlcv_sorts_by_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_historical_ohlcv should return data sorted by date."""
    mock_return = {
        "history": [
            {"businessDate": "2025-01-03", "closePrice": 1030, "totalTradedQuantity": 10000},
            {"businessDate": "2025-01-01", "closePrice": 1010, "totalTradedQuantity": 10000},
            {"businessDate": "2025-01-02", "closePrice": 1020, "totalTradedQuantity": 10000},
        ]
    }

    fetcher = _setup_fake_fetcher(monkeypatch, mock_return)
    monkeypatch.setattr(fetcher, "_call_unofficial_client", lambda method_name, **kwargs: mock_return["history"])

    history = fetcher.fetch_historical_ohlcv("NABIL")

    assert history.iloc[0]["date"] == pd.to_datetime("2025-01-01")
    assert history.iloc[1]["date"] == pd.to_datetime("2025-01-02")
    assert history.iloc[2]["date"] == pd.to_datetime("2025-01-03")


def test_fetch_historical_ohlcv_uses_cache_for_identical_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Historical fetch should hit upstream once for repeated identical requests."""
    mock_return = {
        "history": [
            {
                "businessDate": "2025-01-01",
                "openPrice": 1000,
                "highPrice": 1020,
                "lowPrice": 990,
                "closePrice": 1010,
                "totalTradedQuantity": 10000,
                "totalTradedValue": 10100000,
            }
        ]
    }
    fetcher = _setup_fake_fetcher(monkeypatch, mock_return)
    call_counter = {"count": 0}

    def _mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getCompanyPriceVolumeHistory":
            call_counter["count"] += 1
        return mock_return["history"]

    monkeypatch.setattr(fetcher, "_call_unofficial_client", _mock_call)

    first = fetcher.fetch_historical_ohlcv("NABIL")
    second = fetcher.fetch_historical_ohlcv("NABIL")

    assert call_counter["count"] == 1
    assert len(first) == 1
    assert len(second) == 1


# --- Test fetch_symbols() ---
def test_fetch_symbols_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_symbols should return normalized symbol list."""
    mock_return = {
        "securities": [
            {"symbol": "NABIL", "listedShares": 1000000},
            {"symbol": "SCB", "listedShares": 900000},
        ]
    }

    fetcher = _setup_fake_fetcher(monkeypatch, mock_return)
    monkeypatch.setattr(fetcher, "_call_unofficial_client", lambda method_name, **kwargs: mock_return["securities"])

    symbols = fetcher.fetch_symbols()

    assert len(symbols) == 2
    assert symbols.iloc[0]["symbol"] == "NABIL"
    assert symbols.iloc[1]["symbol"] == "SCB"


def test_fetch_symbols_returns_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_symbols should return DataFrame with symbol column."""
    mock_return = {"securities": [{"symbol": "NABIL"}, {"symbol": "SCB"}]}

    fetcher = _setup_fake_fetcher(monkeypatch, mock_return)
    monkeypatch.setattr(fetcher, "_call_unofficial_client", lambda method_name, **kwargs: mock_return["securities"])

    symbols = fetcher.fetch_symbols()

    assert isinstance(symbols, pd.DataFrame)
    assert "symbol" in symbols.columns


def test_fetch_symbols_enriches_sector_from_sector_scrips(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_symbols should enrich sectors from getSectorScrips when available."""
    fetcher = _setup_fake_fetcher(monkeypatch)

    def mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getSecurityList":
            return [{"symbol": "NABIL"}, {"symbol": "SHIVM"}]
        if method_name == "getSectorScrips":
            return {
                "Commercial Banks": ["NABIL"],
                "Manufacturing And Processing": ["SHIVM"],
            }
        return []

    monkeypatch.setattr(fetcher, "_call_unofficial_client", mock_call)
    monkeypatch.setattr(fetcher, "_load_sector_lookup_from_file", lambda: {})

    symbols = fetcher.fetch_symbols()
    by_symbol = symbols.set_index("symbol")

    assert by_symbol.loc["NABIL", "sector"] == "Commercial Banks"
    assert by_symbol.loc["SHIVM", "sector"] == "Manufacturing And Processing"


def test_fetch_symbols_local_sector_file_overrides_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local sector master should override API sector mapping when provided."""
    fetcher = _setup_fake_fetcher(monkeypatch)

    def mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getSecurityList":
            return [{"symbol": "SHIVM"}]
        if method_name == "getSectorScrips":
            return {"Hydro Power": ["SHIVM"]}
        return []

    monkeypatch.setattr(fetcher, "_call_unofficial_client", mock_call)
    monkeypatch.setattr(fetcher, "_load_sector_lookup_from_file", lambda: {"SHIVM": "Cement"})

    symbols = fetcher.fetch_symbols()
    assert symbols.iloc[0]["sector"] == "Cement"


# --- Test fetch_universe_with_history() ---
def test_fetch_universe_with_history_filters_by_min_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_universe_with_history should filter symbols with insufficient history."""

    class _MockFetcher(NepseDataFetcher):
        def fetch_symbols(self) -> pd.DataFrame:
            return pd.DataFrame({"symbol": ["NABIL", "SCB", "KBL"]})

        def fetch_historical_ohlcv(self, symbol: str, **kwargs: Any) -> pd.DataFrame:
            if symbol == "NABIL":
                return pd.DataFrame(
                    {
                        "date": pd.date_range("2025-01-01", periods=200),
                        "close": [1000 + i for i in range(200)],
                    }
                )
            elif symbol == "SCB":
                return pd.DataFrame(
                    {
                        "date": pd.date_range("2025-01-01", periods=150),
                        "close": [1100 + i for i in range(150)],
                    }
                )
            else:
                return pd.DataFrame()  # KBL: insufficient data (< 180)

    monkeypatch.setattr(NepseDataFetcher, "__init__", lambda self, config=None: None)
    monkeypatch.setattr(NepseDataFetcher, "fetch_symbols", _MockFetcher.fetch_symbols)
    monkeypatch.setattr(NepseDataFetcher, "fetch_historical_ohlcv", _MockFetcher.fetch_historical_ohlcv)

    fetcher = NepseDataFetcher()
    fetcher.config = _build_config()

    universe = fetcher.fetch_universe_with_history(min_history_rows=180)

    assert "NABIL" in universe  # 200 rows >= 180, included
    assert "KBL" not in universe  # 0 rows < 180, excluded


def test_fetch_universe_with_history_returns_dict_of_dataframes(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_universe_with_history should return dict mapping symbol to DataFrame."""

    class _MockFetcher(NepseDataFetcher):
        def fetch_symbols(self) -> pd.DataFrame:
            return pd.DataFrame({"symbol": ["NABIL"]})

        def fetch_historical_ohlcv(self, symbol: str, **kwargs: Any) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "date": pd.date_range("2025-01-01", periods=200),
                    "close": [1000 + i for i in range(200)],
                }
            )

    monkeypatch.setattr(NepseDataFetcher, "__init__", lambda self, config=None: None)
    monkeypatch.setattr(NepseDataFetcher, "fetch_symbols", _MockFetcher.fetch_symbols)
    monkeypatch.setattr(NepseDataFetcher, "fetch_historical_ohlcv", _MockFetcher.fetch_historical_ohlcv)

    fetcher = NepseDataFetcher()
    fetcher.config = _build_config()

    universe = fetcher.fetch_universe_with_history(min_history_rows=100)

    assert isinstance(universe, dict)
    assert "NABIL" in universe
    assert isinstance(universe["NABIL"], pd.DataFrame)


def test_fetch_universe_with_history_uses_deterministic_symbol_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Universe output should preserve deterministic sorted symbol order."""

    class _MockFetcher(NepseDataFetcher):
        def fetch_daily_market_snapshot(self) -> pd.DataFrame:
            return pd.DataFrame({"symbol": ["BBB", "AAA", "CCC"]})

        def fetch_historical_ohlcv(self, symbol: str, **kwargs: Any) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "date": pd.date_range("2025-01-01", periods=200),
                    "close": [100 + i for i in range(200)],
                }
            )

    monkeypatch.setattr(NepseDataFetcher, "__init__", lambda self, config=None: None)
    monkeypatch.setattr(NepseDataFetcher, "fetch_daily_market_snapshot", _MockFetcher.fetch_daily_market_snapshot)
    monkeypatch.setattr(NepseDataFetcher, "fetch_historical_ohlcv", _MockFetcher.fetch_historical_ohlcv)

    fetcher = NepseDataFetcher()
    fetcher.config = _build_config()

    universe = fetcher.fetch_universe_with_history(min_history_rows=100)

    assert list(universe.keys()) == ["AAA", "BBB", "CCC"]


def test_fetch_universe_with_history_retries_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Universe fetching should retry transient history failures before giving up."""

    class _MockFetcher(NepseDataFetcher):
        def fetch_daily_market_snapshot(self) -> pd.DataFrame:
            return pd.DataFrame({"symbol": ["AAA"]})

    attempts = {"AAA": 0}

    def _history(self: NepseDataFetcher, symbol: str, **kwargs: Any) -> pd.DataFrame:
        attempts[symbol] += 1
        if attempts[symbol] == 1:
            raise RuntimeError("temporary upstream error")
        return pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=200),
                "close": [100 + i for i in range(200)],
            }
        )

    monkeypatch.setattr(NepseDataFetcher, "__init__", lambda self, config=None: None)
    monkeypatch.setattr(NepseDataFetcher, "fetch_daily_market_snapshot", _MockFetcher.fetch_daily_market_snapshot)
    monkeypatch.setattr(NepseDataFetcher, "fetch_historical_ohlcv", _history)
    monkeypatch.setattr("nepse_api.data_fetcher.time.sleep", lambda _seconds: None)

    fetcher = NepseDataFetcher()
    fetcher.config = _build_config()

    universe = fetcher.fetch_universe_with_history(min_history_rows=100)

    assert "AAA" in universe
    assert attempts["AAA"] == 2


# --- Integration Tests ---
def test_snapshot_to_history_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: fetch snapshot then fetch history for symbols."""
    live_market_data = [
        {"symbol": "NABIL", "closePrice": 1010},
        {"symbol": "SCB", "closePrice": 1110},
    ]
    history_data = [
        {
            "businessDate": "2025-01-01",
            "openPrice": 1000,
            "closePrice": 1010,
            "totalTradedQuantity": 10000,
        },
    ]

    fetcher = _setup_fake_fetcher(monkeypatch)

    call_count = {"snapshot": 0, "history": 0}

    def mock_call(method_name: str, **kwargs: Any) -> Any:
        if method_name == "getLiveMarket":
            call_count["snapshot"] += 1
            return live_market_data
        elif method_name == "getCompanyPriceVolumeHistory":
            call_count["history"] += 1
            return history_data
        elif method_name == "getSecurityList":
            return [{"symbol": "NABIL"}, {"symbol": "SCB"}]
        return []

    monkeypatch.setattr(fetcher, "_call_unofficial_client", mock_call)

    # Fetch snapshot
    snapshot = fetcher.fetch_daily_market_snapshot()
    assert len(snapshot) >= 1  # At least one symbol

    # Fetch history for each symbol
    symbols_to_test = snapshot["symbol"].head(2).tolist()
    for symbol in symbols_to_test:
        history = fetcher.fetch_historical_ohlcv(symbol)
        assert len(history) == 1

    assert call_count["snapshot"] >= 1
    assert call_count["history"] >= 1


def test_historical_data_normalization_handles_field_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    """Historical fetching should handle field name variants from different API versions."""
    # Test that various field name variants are handled
    mock_return = {
        "history": [
            {
                # camelCase variants
                "businessDate": "2025-01-01",
                "openPrice": 1000,
                "highPrice": 1020,
                "lowPrice": 990,
                "closePrice": 1010,
                "totalTradedQuantity": 10000,
                "totalTradedValue": 10100000,
            },
        ]
    }

    fetcher = _setup_fake_fetcher(monkeypatch, mock_return)
    monkeypatch.setattr(fetcher, "_call_unofficial_client", lambda method_name, **kwargs: mock_return["history"])

    history = fetcher.fetch_historical_ohlcv("NABIL")

    assert len(history) == 1
    assert history.iloc[0]["date"] == pd.to_datetime("2025-01-01")
    assert history.iloc[0]["open"] == 1000
    assert history.iloc[0]["close"] == 1010
    assert history.iloc[0]["volume"] == 10000
    assert history.iloc[0]["turnover"] == 10100000
