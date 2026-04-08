# Improvement TODO

## 1. Code-Level Refactor Plan

### 1.1 nepse_api/data_fetcher.py

- Extract:
  - Raw upstream calls into NepseClientProvider.
  - Normalization helpers into SnapshotNormalizer and HistoricalNormalizer.
  - Fallback orchestration into DataFetchCoordinator.
- Rename:
  - NepseDataFetcher -> LegacyNepseDataFetcher during migration.
- Delete or consolidate:
  - Remove direct _call_unofficial_client usage from workflows once coordinator is adopted.
  - Remove duplicate fallback logic after coordinator is stable.

### 1.2 nepse_api/data_persistence.py

- Keep as repository layer.
- Add:
  - get_latest_snapshot_before(date_value)
  - load_historical_many(symbols)
- Consolidate:
  - Reuse load_latest_snapshot in fallback chain (currently underused).

### 1.3 workflows/common.py

- Extract:
  - fetch_market_snapshot and fetch_historical_universe should call coordinator only.
- Delete:
  - Local fallback branching in this file after migration.
- Keep:
  - Validation, ranking cache, logging summaries.

### 1.4 workflows/market_scan.py

- Change:
  - Dependencies.fetcher -> dependencies.coordinator.
- Keep:
  - Scanner, detector, ranking flow unchanged.

### 1.5 workflows/market_backtest.py

- Change:
  - Dependencies.fetcher -> dependencies.coordinator.
- Keep:
  - Backtest logic unchanged.

### 1.6 api/service.py

- Extract:
  - Direct NepseClient calls for live market and history should route through coordinator.
- Consolidate:
  - Remove duplication with workflow fetch logic.
- Keep:
  - API-specific TTL caches and HTTP-layer retries for non-market endpoints if desired.

## 2. Introduce Provider + Coordinator Pattern

### 2.1 nepse_api/providers.py

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional
import random
import time

import pandas as pd
from nepse_client import NepseClient


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    backoff_seconds: float = 0.25
    jitter_seconds: float = 0.10


class NepseClientProvider:
    def __init__(self, client: NepseClient, retry: RetryPolicy) -> None:
        self.client = client
        self.retry = retry

    def get_live_market_raw(self) -> Any:
        return self._call_with_retry("getLiveMarket")

    def get_security_list_raw(self) -> Any:
        return self._call_with_retry("getSecurityList")

    def get_sector_scrips_raw(self) -> Any:
        return self._call_with_retry("getSectorScrips")

    def get_company_history_raw(self, symbol: str, start: date, end: date) -> Any:
        return self._call_with_retry(
            "getCompanyPriceVolumeHistory",
            symbol=symbol.upper(),
            start_date=start,
            end_date=end,
        )

    def get_company_details_raw(self, symbol: str) -> Any:
        return self._call_with_retry("getCompanyDetails", symbol=symbol.upper())

    def _call_with_retry(self, method_name: str, **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, self.retry.attempts + 1):
            try:
                method = getattr(self.client, method_name)
                return method(**kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt >= self.retry.attempts:
                    break
                sleep_for = (self.retry.backoff_seconds * attempt) + random.uniform(0, self.retry.jitter_seconds)
                if sleep_for > 0:
                    time.sleep(sleep_for)
        if last_exc:
            raise last_exc
        raise RuntimeError(f"Failed call: {method_name}")


class PersistedSnapshotProvider:
    def __init__(self, persistence: Any) -> None:
        self.persistence = persistence

    def load_latest(self) -> Optional[pd.DataFrame]:
        return self.persistence.load_latest_snapshot()

    def save(self, snapshot_df: pd.DataFrame) -> None:
        self.persistence.save_snapshot(snapshot_df)


class PersistedHistoryProvider:
    def __init__(self, persistence: Any) -> None:
        self.persistence = persistence

    def load_many(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        return self.persistence.load_universe(symbols)

    def save_one(self, symbol: str, history_df: pd.DataFrame) -> None:
        self.persistence.save_historical(symbol, history_df)
```

### 2.2 nepse_api/normalizers.py

```python
from __future__ import annotations
from typing import Any, Dict, List
import pandas as pd


class SnapshotNormalizer:
    @staticmethod
    def normalize_live_market(payload: Any) -> pd.DataFrame:
        rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
        out: List[Dict[str, Any]] = []
        for row in rows:
            symbol = row.get("symbol") or row.get("stockSymbol") or row.get("ticker")
            if not symbol:
                continue
            out.append(
                {
                    "symbol": str(symbol).upper(),
                    "open": row.get("openPrice") or row.get("open") or 0,
                    "high": row.get("highPrice") or row.get("high") or 0,
                    "low": row.get("lowPrice") or row.get("low") or 0,
                    "close": row.get("closePrice") or row.get("lastTradedPrice") or row.get("ltp") or 0,
                    "volume": row.get("totalTradedQuantity") or row.get("volume") or 0,
                    "turnover": row.get("totalTradedValue") or row.get("totalTradeValue") or row.get("turnover") or 0,
                    "sector": row.get("businessSectorName") or row.get("sectorName") or "Unknown",
                    "market_cap": row.get("marketCap") or 0,
                    "data_source": "live_market",
                }
            )
        df = pd.DataFrame(out)
        for col in ["open", "high", "low", "close", "volume", "turnover", "market_cap"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df


class HistoricalNormalizer:
    @staticmethod
    def normalize_history(payload: Any, symbol: str) -> pd.DataFrame:
        rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
        out = []
        for row in rows:
            out.append(
                {
                    "date": pd.to_datetime(row.get("businessDate") or row.get("date"), errors="coerce"),
                    "symbol": symbol.upper(),
                    "open": row.get("openPrice") or row.get("open") or 0,
                    "high": row.get("highPrice") or row.get("high") or 0,
                    "low": row.get("lowPrice") or row.get("low") or 0,
                    "close": row.get("closePrice") or row.get("close") or row.get("lastTradedPrice") or 0,
                    "volume": row.get("totalTradedQuantity") or row.get("volume") or 0,
                    "turnover": row.get("totalTradedValue") or row.get("totalTradeValue") or row.get("turnover") or 0,
                }
            )
        df = pd.DataFrame(out).dropna(subset=["date"])
        return df.sort_values("date").reset_index(drop=True)
```

### 2.3 nepse_api/coordinator.py

```python
from __future__ import annotations
from datetime import date, timedelta
from typing import Dict, List, Optional
import pandas as pd


class DataFetchCoordinator:
    def __init__(
        self,
        remote: Any,
        snapshot_repo: Any,
        history_repo: Any,
        snapshot_normalizer: Any,
        history_normalizer: Any,
        enable_cache: bool = True,
    ) -> None:
        self.remote = remote
        self.snapshot_repo = snapshot_repo
        self.history_repo = history_repo
        self.snapshot_normalizer = snapshot_normalizer
        self.history_normalizer = history_normalizer
        self.enable_cache = enable_cache
        self._snapshot_cache: Optional[pd.DataFrame] = None

    def get_market_snapshot(self, force_refresh: bool = False) -> pd.DataFrame:
        if not force_refresh and self._snapshot_cache is not None and not self._snapshot_cache.empty:
            return self._snapshot_cache.copy()

        live_df = self._fetch_live_snapshot()
        if not live_df.empty:
            self.snapshot_repo.save(live_df)
            self._snapshot_cache = live_df.copy()
            return live_df

        # Critical fix: persisted snapshot fallback BEFORE security master fallback
        persisted = self.snapshot_repo.load_latest()
        if persisted is not None and not persisted.empty:
            self._snapshot_cache = persisted.copy()
            return persisted

        security_master_df = self._build_security_master_fallback()
        self._snapshot_cache = security_master_df.copy()
        return security_master_df

    def get_historical(self, symbol: str, start: Optional[date], end: Optional[date], force_refresh: bool = False) -> pd.DataFrame:
        final_end = end or date.today()
        final_start = start or (final_end - timedelta(days=365 * 5))

        if not force_refresh:
            from_disk = self.history_repo.load_many([symbol.upper()]).get(symbol.upper())
            if from_disk is not None and not from_disk.empty:
                return from_disk

        raw = self.remote.get_company_history_raw(symbol=symbol, start=final_start, end=final_end)
        df = self.history_normalizer.normalize_history(raw, symbol=symbol)
        if not df.empty:
            self.history_repo.save_one(symbol.upper(), df)
        return df

    def get_universe_with_history(self, symbols: List[str], force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        result: Dict[str, pd.DataFrame] = {}
        if not force_refresh:
            result.update(self.history_repo.load_many(symbols))

        to_fetch = [s for s in symbols if s not in result]
        for symbol in to_fetch:
            hist = self.get_historical(symbol, start=None, end=None, force_refresh=True)
            if not hist.empty:
                result[symbol] = hist
        return result

    def _fetch_live_snapshot(self) -> pd.DataFrame:
        raw = self.remote.get_live_market_raw()
        return self.snapshot_normalizer.normalize_live_market(raw)

    def _build_security_master_fallback(self) -> pd.DataFrame:
        raw = self.remote.get_security_list_raw()
        rows = raw if isinstance(raw, list) else raw.get("data", []) if isinstance(raw, dict) else []
        out = []
        for row in rows:
            sym = row.get("symbol") or row.get("stockSymbol") or row.get("ticker")
            if not sym:
                continue
            out.append(
                {
                    "symbol": str(sym).upper(),
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.0,
                    "volume": 0.0,
                    "turnover": 0.0,
                    "market_cap": row.get("marketCap") or 0.0,
                    "sector": row.get("businessSectorName") or row.get("sectorName") or "Unknown",
                    "data_source": "security_master_fallback",
                }
            )
        return pd.DataFrame(out)
```

## 3. Unify API and CLI Data Access

Current duplication:

- API path in api/service.py calls NepseClient directly for live market and company history.
- CLI/workflow path in workflows/common.py calls nepse_api/data_fetcher.py, which has separate normalization/fallback logic.

Concrete unification:

- Create a factory in nepse_api/factory.py that builds one DataFetchCoordinator.
- Inject that coordinator into:
  - workflows/market_scan.py
  - workflows/market_backtest.py
  - api/service.py
- Move market snapshot and history methods in service to coordinator:
  - live_market delegates to coordinator.get_market_snapshot
  - company_history delegates to coordinator.get_historical

This removes dual behavior and ensures identical fallback and force_refresh semantics across CLI and API.

## 4. Fix Specific Gaps with Code-Level Solutions

### 4.1 Retry + jitter for live market fetch

- Implement inside NepseClientProvider.get_live_market_raw via _call_with_retry.
- Use RetryPolicy from settings:
  - MARKET_FETCH_RETRY_ATTEMPTS
  - MARKET_FETCH_RETRY_BACKOFF_SECONDS
  - MARKET_FETCH_RETRY_JITTER_SECONDS

### 4.2 Proper force_refresh behavior

- In DataFetchCoordinator:
  - force_refresh true must skip in-memory and persisted reads.
  - It should fetch upstream and overwrite persisted storage.

### 4.3 Snapshot fallback before security master fallback

- In coordinator.get_market_snapshot:
  - Try live
  - Then snapshot_repo.load_latest
  - Then security master fallback

### 4.4 Separation of normalization from fetching

- Move normalization functions out of nepse_api/data_fetcher.py into nepse_api/normalizers.py.
- Providers return raw payloads; normalizers return canonical DataFrames.

## 5. Before vs After Flow

### Current flow

- CLI:
  - main.py -> cli/commands.py -> workflows/market_scan.py
  - workflows/common.py.fetch_market_snapshot
  - nepse_api/data_fetcher.py.fetch_daily_market_snapshot
  - NepseClient.getLiveMarket
  - local fallback logic mixed in fetcher

- API:
  - api/app.py route
  - api/service.py.live_market
  - NepseClient.getLiveMarket direct

### Refactored flow

- CLI and API both:
  - caller -> DataFetchCoordinator.get_market_snapshot
  - NepseClientProvider.get_live_market_raw
  - SnapshotNormalizer.normalize_live_market
  - PersistedSnapshotProvider.save
  - fallback to PersistedSnapshotProvider.load_latest
  - fallback to security master

## 6. Minimal Incremental Migration Plan

1. Add new modules only:
- Add providers.py, normalizers.py, coordinator.py, factory.py.
- No existing call site changes yet.
- Test provider retry behavior in isolation.

2. Replace workflow snapshot path first:
- Update workflows/common.py fetch_market_snapshot to call coordinator.
- Keep legacy fetcher available behind a flag for rollback.
- Test scan workflow output parity.

3. Replace workflow historical path:
- Update fetch_historical_universe in workflows/common.py to coordinator.
- Test backtest workflow parity and timing.

4. Replace API live_market and company_history:
- Refactor api/service.py methods to coordinator.
- Keep other API endpoints unchanged.
- Test endpoint payload shape compatibility.

5. Remove duplicated fallback/normalization from legacy fetcher:
- Slim nepse_api/data_fetcher.py or deprecate it.
- Route all new calls through coordinator factory.

6. Cleanup and consolidate:
- Rename LegacyNepseDataFetcher back or remove it.
- Update docs and config references.
- Add regression tests for force_refresh and fallback order.

Each step is independently deployable and testable.

## 7. Example Refactored Function (before -> after)

### Before in api/service.py

```python
def live_market(self) -> List[Dict[str, Any]]:
    return self._coerce_rows(self._call(self._client, "getLiveMarket"))
```

### After

```python
# api/service.py
from nepse_api.factory import build_data_fetch_coordinator

class NepseApiService:
    def __init__(self) -> None:
        self._coordinator = build_data_fetch_coordinator()
        # keep existing caches for non-coordinator endpoints if needed

    def live_market(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        snapshot_df = self._coordinator.get_market_snapshot(force_refresh=force_refresh)
        if snapshot_df.empty:
            return []
        return snapshot_df.to_dict(orient="records")
```

### Before for company history

```python
def company_history(self, symbol: str, start_date: Optional[date], end_date: Optional[date]) -> List[Dict[str, Any]]:
    final_end = end_date or date.today()
    final_start = start_date or (final_end - timedelta(days=365))
    payload = self._call(
        self._client,
        "getCompanyPriceVolumeHistory",
        symbol=symbol.upper().strip(),
        start_date=final_start,
        end_date=final_end,
    )
    return self._coerce_rows(payload)
```

### After

```python
def company_history(self, symbol: str, start_date: Optional[date], end_date: Optional[date], force_refresh: bool = False) -> List[Dict[str, Any]]:
    df = self._coordinator.get_historical(
        symbol=symbol.upper().strip(),
        start=start_date,
        end=end_date,
        force_refresh=force_refresh,
    )
    if df.empty:
        return []
    return df.to_dict(orient="records")
```
