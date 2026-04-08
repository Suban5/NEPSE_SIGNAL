# Troubleshooting

Metadata:
Owner: suban
Last Reviewed: 2026-04-06
Source of Truth: cli/commands.py, api/app.py, nepse_api/data_fetcher.py
Validation Method: Code + Tests

## Health Check Fails

Run:

```bash
python main.py health-check --symbol NABIL
```

Common causes:

- upstream API returned empty snapshot
- historical rows unavailable for requested symbol/date
- network or TLS verification issues

## API Timeout on Floor Sheet

Use higher timeout_seconds:

```text
GET /trading/floor-sheet?show_progress=false&timeout_seconds=120
```

## Upstream 401/403/5xx Behavior

The API maps upstream errors to structured error payloads and preserves status when available.

## TLS Issues

- keep NEPSE_TLS_VERIFY=true in secure environments
- use false only for controlled local debugging

## Increase Logging

```bash
export LOG_LEVEL=DEBUG
python main.py health-check --symbol NABIL
```

## Data Looks Stale

Force a fresh API pull and refresh local datasets:

```bash
python main.py scan-market --top-n 20 --output output --force-refresh
```

Cached datasets are stored under data/datasets/snapshots and data/datasets/historical.

## Unknown Sector Values

If many rows show `Unknown` sector:

- upstream sector mapping may be temporarily incomplete
- snapshot rows may have come from fallback sources

Mitigations:

- keep `NEPSE_ENRICH_SECTOR=true`
- provide a local override CSV and set `SECTOR_MASTER_PATH`

Example local CSV format:

```csv
symbol,sector
NABIL,Banking
SHIVM,Hydropower
```

## Turnover Is Zero in Top Volume

If `top-volume` shows `0.00` turnover for most symbols:

- upstream field names may vary (`turnover` vs `totalTradeValue`)
- stale cached snapshot may have older schema

Mitigations:

- run with `--force-refresh`
- ensure you are on the latest code that maps `totalTradeValue`

## Strong Momentum Output Is Empty

An empty `strong_momentum.csv` is valid when filters are strict.

Check:

- market trend is weak/broadly down
- your `--top-n` is too small

Mitigations:

- increase `--top-n` (example: 40)
- run again with `--force-refresh`

## Fundamentals Endpoint Is Flaky

When upstream fundamentals calls fail repeatedly, workflows now apply a short circuit-breaker and continue without fundamentals for affected symbols.

This prevents long retry storms while preserving scan completion.
