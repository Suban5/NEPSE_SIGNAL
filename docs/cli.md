# CLI Reference

Metadata:
Owner: suban
Last Reviewed: 2026-04-08
Source of Truth: cli/commands.py, workflows/*.py
Validation Method: Code + Tests

Entry point: python main.py

## Commands

### scan-market

```bash
python main.py scan-market --top-n 15 --plot --sector-relative --output output --force-refresh
```

- --top-n: int (default 15)
- --plot: flag
- --sector-relative: flag
- --output: str (default output)
- --force-refresh: flag (default false; bypasses memory and disk cache)

Outputs include ranking CSVs and scan_benchmark.json.

CLI output now logs workflow completion with an `execution_id`. The same `execution_id` is persisted in `scan_benchmark.json` for trace correlation.

### analyze

```bash
python main.py analyze NABIL --start-date 2024-01-01 --end-date 2026-03-31 --sector-relative
```

- symbol: required positional
- --start-date: YYYY-MM-DD
- --end-date: YYYY-MM-DD
- --sector-relative: flag

CLI output logs workflow completion with an `execution_id` for symbol analysis traceability.

### backtest-market

```bash
python main.py backtest-market --top-n 20 --lookback-days 252 --rebalance monthly --sector-relative --output output --force-refresh
```

- --top-n: int (default 20)
- --lookback-days: int (default 252)
- --rebalance: static|weekly|monthly (default static)
- --sector-relative: flag
- --output: str (default output)
- --force-refresh: flag (default false; bypasses memory and disk cache)

Outputs include portfolio_backtest.json, portfolio_signal_set.csv, and backtest_benchmark.json.

CLI output now logs workflow completion with an `execution_id`. The same `execution_id` is persisted in `backtest_benchmark.json` for trace correlation.

## Data Refresh Behavior

- Default: prefers memory cache, then local datasets in data/datasets, then API.
- With --force-refresh: fetches fresh market snapshot and history from API and updates local datasets.

### health-check

```bash
python main.py health-check --symbol NABIL
```

### top-volume

```bash
python main.py top-volume --limit 10 --force-refresh
```

- --limit: int (default 10)
- --force-refresh: flag (default false; bypasses memory and disk cache)

Outputs top live-market symbols sorted by volume with symbol, close, volume, turnover, data_source, and sector.

### run-api

```bash
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

## Legacy Compatibility

Legacy flags remain supported:

```bash
python main.py --scan-market --top-n 20 --plot
python main.py --symbol NABIL --start-date 2024-01-01 --end-date 2026-03-31
```
