from __future__ import annotations

"""Normalization layer for upstream NEPSE payloads."""

from typing import Any, Dict, List

import pandas as pd


def _coerce_rows(payload: Any) -> List[Dict[str, Any]]:
    """Extract list rows from list-or-dict payload schemas."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "result", "items", "content"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


class SnapshotNormalizer:
    """Normalize live market payloads to canonical snapshot schema."""

    @staticmethod
    def normalize_live_market(payload: Any) -> pd.DataFrame:
        """Normalize upstream live market payload into snapshot DataFrame."""
        rows = _coerce_rows(payload)
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            symbol = row.get("symbol") or row.get("stockSymbol") or row.get("ticker")
            if not symbol:
                continue
            normalized.append(
                {
                    "symbol": str(symbol).upper(),
                    "open": row.get("openPrice") or row.get("open") or row.get("previousClosing") or 0,
                    "high": row.get("highPrice") or row.get("high") or row.get("highPrice52Week") or 0,
                    "low": row.get("lowPrice") or row.get("low") or row.get("lowPrice52Week") or 0,
                    "close": row.get("closePrice")
                    or row.get("lastTradedPrice")
                    or row.get("ltp")
                    or row.get("close")
                    or 0,
                    "volume": row.get("totalTradedQuantity")
                    or row.get("volume")
                    or row.get("totalTradeQuantity")
                    or row.get("tradeVolume")
                    or 0,
                    "turnover": row.get("totalTradedValue")
                    or row.get("totalTradeValue")
                    or row.get("turnover")
                    or row.get("totalTrades")
                    or row.get("tradeTurnover")
                    or 0,
                    "market_cap": row.get("marketCap")
                    or row.get("market_cap")
                    or row.get("marketCapitalization")
                    or row.get("marketCapitalisation")
                    or 0,
                    "sector": row.get("businessSectorName")
                    or row.get("sectorName")
                    or row.get("sector")
                    or row.get("sectorType")
                    or "Unknown",
                    "data_source": "live_market",
                }
            )

        snapshot_df = pd.DataFrame(normalized)
        if snapshot_df.empty:
            return snapshot_df

        for col in ["open", "high", "low", "close", "volume", "turnover", "market_cap"]:
            snapshot_df[col] = pd.to_numeric(snapshot_df[col], errors="coerce").fillna(0.0)

        return snapshot_df


class HistoricalNormalizer:
    """Normalize historical payloads to canonical OHLCV schema."""

    @staticmethod
    def normalize_history(payload: Any, symbol: str) -> pd.DataFrame:
        """Normalize upstream company history payload into OHLCV DataFrame."""
        rows = _coerce_rows(payload)
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            raw_date = row.get("businessDate") or row.get("date") or row.get("tradeDate")
            if raw_date is None:
                continue
            parsed_date = pd.to_datetime([raw_date], errors="coerce")[0]
            if pd.isna(parsed_date):
                continue
            normalized.append(
                {
                    "date": parsed_date,
                    "symbol": symbol.upper(),
                    "open": row.get("openPrice") or row.get("open") or row.get("previousClose") or 0,
                    "high": row.get("highPrice") or row.get("high") or row.get("maxPrice") or 0,
                    "low": row.get("lowPrice") or row.get("low") or row.get("minPrice") or 0,
                    "close": row.get("closePrice") or row.get("close") or row.get("lastTradedPrice") or 0,
                    "volume": row.get("totalTradedQuantity")
                    or row.get("volume")
                    or row.get("totalTradeQuantity")
                    or row.get("tradeVolume")
                    or 0,
                    "turnover": row.get("totalTradedValue")
                    or row.get("totalTradeValue")
                    or row.get("turnover")
                    or row.get("totalTrades")
                    or row.get("tradeTurnover")
                    or 0,
                }
            )

        history_df = pd.DataFrame(normalized)
        if history_df.empty:
            return history_df

        for col in ["open", "high", "low", "close", "volume", "turnover"]:
            history_df[col] = pd.to_numeric(history_df[col], errors="coerce")

        return history_df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
