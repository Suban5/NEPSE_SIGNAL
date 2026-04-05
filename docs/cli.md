# CLI Reference

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: cli/commands.py, workflows/*.py
Validation Method: Code + Tests

Entry point: python main.py

## Commands

### scan-market

```bash
python main.py scan-market --top-n 15 --plot --sector-relative --output output
```

- --top-n: int (default 15)
- --plot: flag
- --sector-relative: flag
- --output: str (default output)

Outputs include ranking CSVs and scan_benchmark.json.

### analyze

```bash
python main.py analyze NABIL --start-date 2024-01-01 --end-date 2026-03-31 --sector-relative
```

- symbol: required positional
- --start-date: YYYY-MM-DD
- --end-date: YYYY-MM-DD
- --sector-relative: flag

### backtest-market

```bash
python main.py backtest-market --top-n 20 --lookback-days 252 --rebalance monthly --sector-relative --output output
```

- --top-n: int (default 20)
- --lookback-days: int (default 252)
- --rebalance: static|weekly|monthly (default static)
- --sector-relative: flag
- --output: str (default output)

Outputs include portfolio_backtest.json, portfolio_signal_set.csv, and backtest_benchmark.json.

### health-check

```bash
python main.py health-check --symbol NABIL
```

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
