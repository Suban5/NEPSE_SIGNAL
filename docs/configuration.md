# Configuration Reference

Metadata:
Owner: suban
Last Reviewed: 2026-04-06
Source of Truth: config/settings.py, .env.example
Validation Method: Code + Tests

All runtime settings are loaded from environment variables in config/settings.py via python-dotenv.

## API and Network

- NEPSE_API_BASE_URL (default: empty; required for fetcher)
- NEPSE_API_TIMEOUT (default: 15)
- NEPSE_TLS_VERIFY (default: true)
- API_RETRY_ATTEMPTS (default: 2)
- API_RETRY_BACKOFF_SECONDS (default: 0.25)

## Market Fetch

- MARKET_PARALLEL_WORKERS (default: 8)
- MARKET_FETCH_RETRY_ATTEMPTS (default: 3)
- MARKET_FETCH_RETRY_BACKOFF_SECONDS (default: 0.20)
- MARKET_FETCH_RETRY_JITTER_SECONDS (default: 0.08)

## Cache

- CACHE_MARKET_SNAPSHOT_TTL_SECONDS (default: 30)
- CACHE_HISTORICAL_TTL_SECONDS (default: 900)
- CACHE_RANKING_TTL_SECONDS (default: 90)
- CACHE_MAX_ENTRIES (default: 5000)
- DATA_CACHE_PATH (default: ./data)
- SECTOR_MASTER_PATH (default: ./data/datasets/sector_master.csv)

Cache behavior is hybrid:

- in-memory TTL cache for fast repeat reads inside a process
- persistent dataset cache on disk under data/datasets

Persistent dataset layout:

- data/datasets/snapshots/market_snapshot_YYYY-MM-DD.csv
- data/datasets/snapshots/market_snapshot_latest.csv
- data/datasets/historical/<SYMBOL>_history.csv
- data/datasets/sector_master.csv (optional symbol to sector override)

Sector enrichment behavior:

- Primary source: upstream sector mapping from getSectorScrips
- Optional override source: SECTOR_MASTER_PATH CSV with columns symbol,sector
- Local CSV values override upstream mapping for matching symbols

Use CLI flag --force-refresh on scan-market and backtest-market to bypass cache and fetch from API.

## Blue-Chip Scoring

- BLUECHIP_SECTOR_RELATIVE (default: false)
- BLUECHIP_NORMALIZATION_MODE (default: robust)
- BLUECHIP_SECTOR_BLEND (default: 0.15)
- BLUECHIP_LOWER_QUANTILE (default: 0.05)
- BLUECHIP_UPPER_QUANTILE (default: 0.95)

## Logging

- LOG_LEVEL (default: INFO)
- THIRD_PARTY_LOG_LEVEL (default: WARNING)
- SUPPRESS_UNOFFICIAL_CLIENT_OUTPUT (default: true)
