# Feature 01: Data Fetching and Normalization

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: nepse_api/data_fetcher.py, tests/test_data_fetcher_flows.py
Validation Method: Code + Tests

## Purpose

NepseDataFetcher retrieves and normalizes symbol lists, market snapshots, historical OHLCV, and fundamentals.

## Verified Public API

- NepseDataFetcher(config: NepseApiConfig | None = None)
- fetch_symbols() -> pandas.DataFrame
- fetch_daily_market_snapshot() -> pandas.DataFrame
- fetch_historical_ohlcv(symbol, start_date=None, end_date=None) -> pandas.DataFrame
- fetch_company_fundamentals(symbol) -> dict
- normalize_fundamentals(payload: dict) -> dict[str, float]
- fetch_universe_with_history(lookback_years=5) -> dict[str, pandas.DataFrame]
- invalidate_cache(scope='all') -> None

## Example

```python
from nepse_api.data_fetcher import NepseDataFetcher

fetcher = NepseDataFetcher()
snapshot = fetcher.fetch_daily_market_snapshot()
history = fetcher.fetch_historical_ohlcv("NABIL")
fundamentals_raw = fetcher.fetch_company_fundamentals("NABIL")
fundamentals = fetcher.normalize_fundamentals(fundamentals_raw)
```

## Notes

- Snapshot and historical responses are cached using TTL cache.
- Historical fetch supports retry with deterministic jitter.
- If NEPSE_API_BASE_URL is not configured, fetcher initialization fails.
