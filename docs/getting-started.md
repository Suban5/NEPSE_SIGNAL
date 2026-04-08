# Getting Started

Metadata:
Owner: suban
Last Reviewed: 2026-04-06
Source of Truth: .env.example, config/settings.py, cli/commands.py
Validation Method: Code + Tests

## Prerequisites

- Python 3.11+
- Local virtual environment (.venv)
- pip

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Required/Supported Environment Variables

See complete reference: [configuration.md](configuration.md)

Minimum quick-start values:

```ini
NEPSE_API_BASE_URL=https://www.nepalstock.com.np
NEPSE_API_TIMEOUT=15
NEPSE_TLS_VERIFY=true
DATA_CACHE_PATH=./data
SECTOR_MASTER_PATH=./data/datasets/sector_master.csv
LOG_LEVEL=INFO
THIRD_PARTY_LOG_LEVEL=WARNING
SUPPRESS_UNOFFICIAL_CLIENT_OUTPUT=true
```

## Run Workflows

```bash
python main.py scan-market --top-n 20 --plot --output output
python main.py analyze NABIL --start-date 2024-01-01 --end-date 2026-03-31
python main.py backtest-market --top-n 20 --lookback-days 252 --rebalance monthly --output output
python main.py top-volume --limit 10 --force-refresh
python main.py health-check --symbol NABIL
```

To force fresh API data and refresh local datasets:

```bash
python main.py scan-market --top-n 20 --output output --force-refresh
python main.py backtest-market --top-n 20 --lookback-days 252 --output output --force-refresh
```

Fetched snapshot and historical data are persisted under data/datasets for reuse between runs.

## Run API

```bash
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

## Verify Installation

```bash
pytest -v
```
