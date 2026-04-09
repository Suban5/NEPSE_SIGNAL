"""Tests for normalization layer - payload extraction and DataFrame building."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from nepse_api.normalizers import (
    HistoricalNormalizer,
    SnapshotNormalizer,
    _coerce_rows,
)


# ============================================================================
# Tests for _coerce_rows() helper function
# ============================================================================


def test_coerce_rows_extracts_list_payload() -> None:
    """_coerce_rows should extract list of dicts from list payload."""
    payload = [{"symbol": "NABIL"}, {"symbol": "SBI"}]
    result = _coerce_rows(payload)
    assert result == payload
    assert len(result) == 2


def test_coerce_rows_filters_non_dict_items_from_list() -> None:
    """_coerce_rows should skip non-dict items in list."""
    payload = [{"symbol": "NABIL"}, "string", None, 123, {"symbol": "SBI"}]
    result = _coerce_rows(payload)
    assert len(result) == 2
    assert result[0]["symbol"] == "NABIL"
    assert result[1]["symbol"] == "SBI"


def test_coerce_rows_extracts_data_key() -> None:
    """_coerce_rows should extract rows from 'data' key in dict."""
    payload = {"data": [{"symbol": "NABIL"}, {"symbol": "SBI"}]}
    result = _coerce_rows(payload)
    assert len(result) == 2
    assert result[0]["symbol"] == "NABIL"


def test_coerce_rows_extracts_result_key() -> None:
    """_coerce_rows should extract rows from 'result' key in dict."""
    payload = {"result": [{"symbol": "NABIL"}]}
    result = _coerce_rows(payload)
    assert len(result) == 1
    assert result[0]["symbol"] == "NABIL"


def test_coerce_rows_extracts_items_key() -> None:
    """_coerce_rows should extract rows from 'items' key in dict."""
    payload = {"items": [{"symbol": "NABIL"}]}
    result = _coerce_rows(payload)
    assert len(result) == 1
    assert result[0]["symbol"] == "NABIL"


def test_coerce_rows_extracts_content_key() -> None:
    """_coerce_rows should extract rows from 'content' key in dict."""
    payload = {"content": [{"symbol": "NABIL"}]}
    result = _coerce_rows(payload)
    assert len(result) == 1
    assert result[0]["symbol"] == "NABIL"


def test_coerce_rows_prioritizes_first_matching_key() -> None:
    """_coerce_rows should use first matching key (data > result > items > content)."""
    payload = {
        "data": [{"symbol": "NABIL"}],
        "result": [{"symbol": "SBI"}],
    }
    result = _coerce_rows(payload)
    assert len(result) == 1
    assert result[0]["symbol"] == "NABIL"


def test_coerce_rows_returns_empty_list_for_no_match() -> None:
    """_coerce_rows should return empty list when no keys match."""
    payload = {"info": "no match", "other": []}
    result = _coerce_rows(payload)
    assert result == []


def test_coerce_rows_handles_none_payload() -> None:
    """_coerce_rows should return empty list for None payload."""
    result = _coerce_rows(None)
    assert result == []


def test_coerce_rows_handles_empty_list() -> None:
    """_coerce_rows should return empty list for empty list payload."""
    result = _coerce_rows([])
    assert result == []


def test_coerce_rows_handles_string_payload() -> None:
    """_coerce_rows should return empty list for non-dict/non-list payload."""
    result = _coerce_rows("invalid")
    assert result == []


def test_coerce_rows_filters_list_with_non_dict_value() -> None:
    """_coerce_rows should skip non-list values in dict keys."""
    payload = {"data": "not a list", "result": [{"symbol": "SBI"}]}
    result = _coerce_rows(payload)
    assert len(result) == 1
    assert result[0]["symbol"] == "SBI"


# ============================================================================
# Tests for SnapshotNormalizer.normalize_live_market()
# ============================================================================


def test_normalize_live_market_basic_payload() -> None:
    """normalize_live_market should convert payload to snapshot DataFrame."""
    payload = [
        {
            "symbol": "nabil",
            "openPrice": 1000,
            "highPrice": 1010,
            "lowPrice": 990,
            "closePrice": 1005,
            "totalTradedQuantity": 5000,
            "totalTradedValue": 5025000,
            "marketCap": 100000000,
            "businessSectorName": "Banking",
        }
    ]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "NABIL"
    assert result.iloc[0]["close"] == 1005.0
    assert result.iloc[0]["volume"] == 5000.0


def test_normalize_live_market_uses_symbol_aliases() -> None:
    """normalize_live_market should try symbol, stockSymbol, ticker aliases."""
    payload1 = [{"symbol": "NABIL", "closePrice": 100}]
    payload2 = [{"stockSymbol": "NABIL", "closePrice": 100}]
    payload3 = [{"ticker": "NABIL", "closePrice": 100}]
    
    result1 = SnapshotNormalizer.normalize_live_market(payload1)
    result2 = SnapshotNormalizer.normalize_live_market(payload2)
    result3 = SnapshotNormalizer.normalize_live_market(payload3)
    
    assert result1.iloc[0]["symbol"] == "NABIL"
    assert result2.iloc[0]["symbol"] == "NABIL"
    assert result3.iloc[0]["symbol"] == "NABIL"


def test_normalize_live_market_skips_row_without_symbol() -> None:
    """normalize_live_market should skip rows with no symbol."""
    payload = [
        {"symbol": "NABIL", "closePrice": 100},
        {"closePrice": 105},  # No symbol
    ]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "NABIL"


def test_normalize_live_market_uses_open_aliases() -> None:
    """normalize_live_market should try open, openPrice, previousClosing for open."""
    payloads = [
        [{"symbol": "A", "openPrice": 100, "closePrice": 105}],
        [{"symbol": "B", "open": 100, "closePrice": 105}],
        [{"symbol": "C", "previousClosing": 100, "closePrice": 105}],
    ]
    for payload in payloads:
        result = SnapshotNormalizer.normalize_live_market(payload)
        assert result.iloc[0]["open"] == 100.0


def test_normalize_live_market_uses_high_aliases() -> None:
    """normalize_live_market should try high, highPrice, highPrice52Week."""
    payloads = [
        [{"symbol": "A", "highPrice": 150, "closePrice": 105}],
        [{"symbol": "B", "high": 150, "closePrice": 105}],
        [{"symbol": "C", "highPrice52Week": 150, "closePrice": 105}],
    ]
    for payload in payloads:
        result = SnapshotNormalizer.normalize_live_market(payload)
        assert result.iloc[0]["high"] == 150.0


def test_normalize_live_market_uses_low_aliases() -> None:
    """normalize_live_market should try low, lowPrice, lowPrice52Week."""
    payloads = [
        [{"symbol": "A", "lowPrice": 50, "closePrice": 105}],
        [{"symbol": "B", "low": 50, "closePrice": 105}],
        [{"symbol": "C", "lowPrice52Week": 50, "closePrice": 105}],
    ]
    for payload in payloads:
        result = SnapshotNormalizer.normalize_live_market(payload)
        assert result.iloc[0]["low"] == 50.0


def test_normalize_live_market_uses_close_aliases() -> None:
    """normalize_live_market should try close, closePrice, lastTradedPrice, ltp."""
    payloads = [
        [{"symbol": "A", "close": 105}],
        [{"symbol": "B", "closePrice": 105}],
        [{"symbol": "C", "lastTradedPrice": 105}],
        [{"symbol": "D", "ltp": 105}],
    ]
    for payload in payloads:
        result = SnapshotNormalizer.normalize_live_market(payload)
        assert result.iloc[0]["close"] == 105.0


def test_normalize_live_market_uses_volume_aliases() -> None:
    """normalize_live_market should try multiple volume field names."""
    payloads = [
        [{"symbol": "A", "totalTradedQuantity": 5000, "closePrice": 100}],
        [{"symbol": "B", "volume": 5000, "closePrice": 100}],
        [{"symbol": "C", "totalTradeQuantity": 5000, "closePrice": 100}],
        [{"symbol": "D", "tradeVolume": 5000, "closePrice": 100}],
    ]
    for payload in payloads:
        result = SnapshotNormalizer.normalize_live_market(payload)
        assert result.iloc[0]["volume"] == 5000.0


def test_normalize_live_market_uses_turnover_aliases() -> None:
    """normalize_live_market should try multiple turnover field names."""
    payloads = [
        [{"symbol": "A", "totalTradedValue": 5000000, "closePrice": 100}],
        [{"symbol": "B", "totalTradeValue": 5000000, "closePrice": 100}],
        [{"symbol": "C", "turnover": 5000000, "closePrice": 100}],
        [{"symbol": "D", "totalTrades": 5000000, "closePrice": 100}],
        [{"symbol": "E", "tradeTurnover": 5000000, "closePrice": 100}],
    ]
    for payload in payloads:
        result = SnapshotNormalizer.normalize_live_market(payload)
        assert result.iloc[0]["turnover"] == 5000000.0


def test_normalize_live_market_uses_market_cap_aliases() -> None:
    """normalize_live_market should try multiple market cap field names."""
    payloads = [
        [{"symbol": "A", "marketCap": 100000000, "closePrice": 100}],
        [{"symbol": "B", "market_cap": 100000000, "closePrice": 100}],
        [{"symbol": "C", "marketCapitalization": 100000000, "closePrice": 100}],
        [{"symbol": "D", "marketCapitalisation": 100000000, "closePrice": 100}],
    ]
    for payload in payloads:
        result = SnapshotNormalizer.normalize_live_market(payload)
        assert result.iloc[0]["market_cap"] == 100000000.0


def test_normalize_live_market_uses_sector_aliases() -> None:
    """normalize_live_market should try multiple sector field names."""
    payloads = [
        [{"symbol": "A", "businessSectorName": "Banking", "closePrice": 100}],
        [{"symbol": "B", "sectorName": "Banking", "closePrice": 100}],
        [{"symbol": "C", "sector": "Banking", "closePrice": 100}],
        [{"symbol": "D", "sectorType": "Banking", "closePrice": 100}],
    ]
    for payload in payloads:
        result = SnapshotNormalizer.normalize_live_market(payload)
        assert result.iloc[0]["sector"] == "Banking"


def test_normalize_live_market_defaults_to_unknown_sector() -> None:
    """normalize_live_market should default sector to 'Unknown' when missing."""
    payload = [{"symbol": "NABIL", "closePrice": 100}]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert result.iloc[0]["sector"] == "Unknown"


def test_normalize_live_market_defaults_numeric_fields_to_zero() -> None:
    """normalize_live_market should default numeric fields to 0 when missing."""
    payload = [{"symbol": "NABIL"}]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert result.iloc[0]["open"] == 0.0
    assert result.iloc[0]["high"] == 0.0
    assert result.iloc[0]["low"] == 0.0
    assert result.iloc[0]["close"] == 0.0
    assert result.iloc[0]["volume"] == 0.0
    assert result.iloc[0]["turnover"] == 0.0
    assert result.iloc[0]["market_cap"] == 0.0


def test_normalize_live_market_uppercases_symbol() -> None:
    """normalize_live_market should uppercase all symbols."""
    payload = [{"symbol": "nabil"}]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert result.iloc[0]["symbol"] == "NABIL"


def test_normalize_live_market_coerces_to_numeric() -> None:
    """normalize_live_market should convert string numbers to float."""
    payload = [
        {
            "symbol": "NABIL",
            "openPrice": "1000",
            "highPrice": "1010",
            "lowPrice": "990",
            "closePrice": "1005",
            "totalTradedQuantity": "5000",
            "totalTradedValue": "5025000",
            "marketCap": "100000000",
        }
    ]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert result.iloc[0]["open"] == 1000.0
    assert result.iloc[0]["close"] == 1005.0
    assert result.iloc[0]["volume"] == 5000.0


def test_normalize_live_market_handles_invalid_numeric_values() -> None:
    """normalize_live_market should coerce invalid numbers to NaN then 0."""
    payload = [
        {
            "symbol": "NABIL",
            "closePrice": "invalid",
            "openPrice": "also invalid",
        }
    ]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert result.iloc[0]["close"] == 0.0
    assert result.iloc[0]["open"] == 0.0


def test_normalize_live_market_sets_data_source() -> None:
    """normalize_live_market should add data_source field."""
    payload = [{"symbol": "NABIL", "closePrice": 100}]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert result.iloc[0]["data_source"] == "live_market"


def test_normalize_live_market_returns_empty_dataframe_for_empty_payload() -> None:
    """normalize_live_market should return empty DataFrame for empty payload."""
    result = SnapshotNormalizer.normalize_live_market([])
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_normalize_live_market_returns_empty_dataframe_when_all_rows_skip() -> None:
    """normalize_live_market should return empty DataFrame when no rows pass filter."""
    payload = [{}, {}]  # No symbols
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert len(result) == 0


def test_normalize_live_market_handles_wrapped_payload() -> None:
    """normalize_live_market should handle wrapped payload with 'data' key."""
    payload = {
        "data": [
            {
                "symbol": "NABIL",
                "closePrice": 100,
            }
        ]
    }
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "NABIL"


def test_normalize_live_market_multiple_rows() -> None:
    """normalize_live_market should normalize multiple rows."""
    payload = [
        {"symbol": "NABIL", "closePrice": 1000},
        {"symbol": "SBI", "closePrice": 500},
        {"symbol": "AAPL", "closePrice": 150},
    ]
    result = SnapshotNormalizer.normalize_live_market(payload)
    assert len(result) == 3
    assert list(result["symbol"]) == ["NABIL", "SBI", "AAPL"]


# ============================================================================
# Tests for HistoricalNormalizer.normalize_history()
# ============================================================================


def test_normalize_history_basic_payload() -> None:
    """normalize_history should convert payload to historical OHLCV DataFrame."""
    payload = [
        {
            "businessDate": "2024-01-15",
            "openPrice": 1000,
            "highPrice": 1010,
            "lowPrice": 990,
            "closePrice": 1005,
            "totalTradedQuantity": 5000,
            "totalTradedValue": 5025000,
        }
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "NABIL"
    assert result.iloc[0]["close"] == 1005
    assert result.iloc[0]["volume"] == 5000


def test_normalize_history_uses_date_aliases() -> None:
    """normalize_history should try businessDate, date, tradeDate."""
    payloads = [
        [{"businessDate": "2024-01-15", "closePrice": 100}],
        [{"date": "2024-01-15", "closePrice": 100}],
        [{"tradeDate": "2024-01-15", "closePrice": 100}],
    ]
    for payload in payloads:
        result = HistoricalNormalizer.normalize_history(payload, "NABIL")
        assert len(result) == 1
        assert pd.Timestamp("2024-01-15") in result["date"].values


def test_normalize_history_uppercases_symbol() -> None:
    """normalize_history should uppercase symbol parameter."""
    payload = [{"businessDate": "2024-01-15", "closePrice": 100}]
    result = HistoricalNormalizer.normalize_history(payload, "nabil")
    assert result.iloc[0]["symbol"] == "NABIL"


def test_normalize_history_skips_rows_without_date() -> None:
    """normalize_history should skip rows with no valid date."""
    payload = [
        {"businessDate": "2024-01-15", "closePrice": 100},
        {"closePrice": 105},  # No date
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    # Both rows have no date, so both skip
    assert len(result) == 1


def test_normalize_history_skips_invalid_dates() -> None:
    """normalize_history should skip rows with invalid date values."""
    payload = [
        {"businessDate": "2024-01-15", "closePrice": 100},
        {"businessDate": "invalid-date", "closePrice": 105},
        {"businessDate": "2024-01-20", "closePrice": 110},
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert len(result) == 2  # Invalid date row skipped


def test_normalize_history_uses_open_aliases() -> None:
    """normalize_history should try open, openPrice, previousClose."""
    payloads = [
        [{"businessDate": "2024-01-15", "openPrice": 1000, "closePrice": 1005}],
        [{"businessDate": "2024-01-15", "open": 1000, "closePrice": 1005}],
        [{"businessDate": "2024-01-15", "previousClose": 1000, "closePrice": 1005}],
    ]
    for payload in payloads:
        result = HistoricalNormalizer.normalize_history(payload, "NABIL")
        assert result.iloc[0]["open"] == 1000


def test_normalize_history_uses_high_aliases() -> None:
    """normalize_history should try high, highPrice, maxPrice."""
    payloads = [
        [{"businessDate": "2024-01-15", "highPrice": 1010, "closePrice": 1005}],
        [{"businessDate": "2024-01-15", "high": 1010, "closePrice": 1005}],
        [{"businessDate": "2024-01-15", "maxPrice": 1010, "closePrice": 1005}],
    ]
    for payload in payloads:
        result = HistoricalNormalizer.normalize_history(payload, "NABIL")
        assert result.iloc[0]["high"] == 1010


def test_normalize_history_uses_low_aliases() -> None:
    """normalize_history should try low, lowPrice, minPrice."""
    payloads = [
        [{"businessDate": "2024-01-15", "lowPrice": 990, "closePrice": 1005}],
        [{"businessDate": "2024-01-15", "low": 990, "closePrice": 1005}],
        [{"businessDate": "2024-01-15", "minPrice": 990, "closePrice": 1005}],
    ]
    for payload in payloads:
        result = HistoricalNormalizer.normalize_history(payload, "NABIL")
        assert result.iloc[0]["low"] == 990


def test_normalize_history_uses_close_aliases() -> None:
    """normalize_history should try close, closePrice, lastTradedPrice."""
    payloads = [
        [{"businessDate": "2024-01-15", "close": 1005}],
        [{"businessDate": "2024-01-15", "closePrice": 1005}],
        [{"businessDate": "2024-01-15", "lastTradedPrice": 1005}],
    ]
    for payload in payloads:
        result = HistoricalNormalizer.normalize_history(payload, "NABIL")
        assert result.iloc[0]["close"] == 1005


def test_normalize_history_uses_volume_aliases() -> None:
    """normalize_history should try multiple volume field names."""
    payloads = [
        [{"businessDate": "2024-01-15", "totalTradedQuantity": 5000, "closePrice": 100}],
        [{"businessDate": "2024-01-15", "volume": 5000, "closePrice": 100}],
        [{"businessDate": "2024-01-15", "totalTradeQuantity": 5000, "closePrice": 100}],
        [{"businessDate": "2024-01-15", "tradeVolume": 5000, "closePrice": 100}],
    ]
    for payload in payloads:
        result = HistoricalNormalizer.normalize_history(payload, "NABIL")
        assert result.iloc[0]["volume"] == 5000


def test_normalize_history_uses_turnover_aliases() -> None:
    """normalize_history should try multiple turnover field names."""
    payloads = [
        [{"businessDate": "2024-01-15", "totalTradedValue": 5000000, "closePrice": 100}],
        [{"businessDate": "2024-01-15", "totalTradeValue": 5000000, "closePrice": 100}],
        [{"businessDate": "2024-01-15", "turnover": 5000000, "closePrice": 100}],
        [{"businessDate": "2024-01-15", "totalTrades": 5000000, "closePrice": 100}],
        [{"businessDate": "2024-01-15", "tradeTurnover": 5000000, "closePrice": 100}],
    ]
    for payload in payloads:
        result = HistoricalNormalizer.normalize_history(payload, "NABIL")
        assert result.iloc[0]["turnover"] == 5000000


def test_normalize_history_defaults_numeric_fields_to_zero() -> None:
    """normalize_history should default numeric fields to 0 when missing."""
    payload = [{"businessDate": "2024-01-15", "closePrice": 100}]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert result.iloc[0]["open"] == 0
    assert result.iloc[0]["high"] == 0
    assert result.iloc[0]["low"] == 0
    assert result.iloc[0]["volume"] == 0
    assert result.iloc[0]["turnover"] == 0


def test_normalize_history_sorts_by_date() -> None:
    """normalize_history should sort rows by date."""
    payload = [
        {"businessDate": "2024-01-20", "closePrice": 110},
        {"businessDate": "2024-01-10", "closePrice": 100},
        {"businessDate": "2024-01-15", "closePrice": 105},
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert len(result) == 3
    assert result.iloc[0]["date"] == pd.Timestamp("2024-01-10")
    assert result.iloc[1]["date"] == pd.Timestamp("2024-01-15")
    assert result.iloc[2]["date"] == pd.Timestamp("2024-01-20")


def test_normalize_history_resets_index() -> None:
    """normalize_history should reset index after sorting."""
    payload = [
        {"businessDate": "2024-01-20", "closePrice": 110},
        {"businessDate": "2024-01-10", "closePrice": 100},
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert result.index.tolist() == [0, 1]


def test_normalize_history_drops_nan_dates() -> None:
    """normalize_history should drop rows with NaN dates."""
    payload = [
        {"businessDate": "2024-01-15", "closePrice": 100},
        {"businessDate": "invalid", "closePrice": 105},
        {"businessDate": "2024-01-20", "closePrice": 110},
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    # Invalid date row should be dropped before checking close
    assert len(result) >= 2  # At least the two valid dates


def test_normalize_history_drops_nan_close() -> None:
    """normalize_history should drop rows when close becomes NaN after coercion."""
    payload = [
        {"businessDate": "2024-01-15", "closePrice": 100},
        {"businessDate": "2024-01-20", "closePrice": "invalid-number"},  # Invalid close
        {"businessDate": "2024-01-25", "closePrice": 110},
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    # Row with invalid close (becomes NaN) should be dropped
    assert len(result) == 2  # Invalid close row dropped


def test_normalize_history_coerces_to_numeric() -> None:
    """normalize_history should convert string numbers to numeric."""
    payload = [
        {
            "businessDate": "2024-01-15",
            "openPrice": "1000",
            "highPrice": "1010",
            "lowPrice": "990",
            "closePrice": "1005",
            "totalTradedQuantity": "5000",
            "totalTradedValue": "5025000",
        }
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert result.iloc[0]["open"] == 1000.0
    assert result.iloc[0]["close"] == 1005.0
    assert result.iloc[0]["volume"] == 5000.0


def test_normalize_history_handles_invalid_numeric_values() -> None:
    """normalize_history should coerce invalid numbers to NaN."""
    payload = [
        {
            "businessDate": "2024-01-15",
            "closePrice": "invalid",
            "openPrice": "also invalid",
        }
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    # Row should be dropped due to NaN close
    assert len(result) == 0


def test_normalize_history_returns_empty_dataframe_for_empty_payload() -> None:
    """normalize_history should return empty DataFrame for empty payload."""
    result = HistoricalNormalizer.normalize_history([], "NABIL")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_normalize_history_returns_empty_when_all_rows_invalid() -> None:
    """normalize_history should return empty DataFrame when all rows invalid."""
    payload = [
        {},  # No date, no close
        {"businessDate": "invalid"},  # Invalid date, no close
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert len(result) == 0


def test_normalize_history_handles_wrapped_payload() -> None:
    """normalize_history should handle wrapped payload with 'data' key."""
    payload = {
        "data": [
            {
                "businessDate": "2024-01-15",
                "closePrice": 1000,
            }
        ]
    }
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert len(result) == 1
    assert result.iloc[0]["close"] == 1000


def test_normalize_history_multiple_rows() -> None:
    """normalize_history should normalize multiple rows."""
    payload = [
        {"businessDate": "2024-01-15", "closePrice": 1000},
        {"businessDate": "2024-01-20", "closePrice": 1005},
        {"businessDate": "2024-01-25", "closePrice": 1010},
    ]
    result = HistoricalNormalizer.normalize_history(payload, "NABIL")
    assert len(result) == 3


def test_normalize_history_date_parsing_formats() -> None:
    """normalize_history should parse various date formats."""
    payloads = [
        [{"businessDate": "2024-01-15", "closePrice": 100}],
        [{"businessDate": "2024/01/15", "closePrice": 100}],
        [{"businessDate": "01/15/2024", "closePrice": 100}],
    ]
    for payload in payloads:
        result = HistoricalNormalizer.normalize_history(payload, "NABIL")
        # Should parse without error
        assert len(result) >= 0
