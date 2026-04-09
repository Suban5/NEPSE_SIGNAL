# Getting Started

Metadata:
Owner: suban
Last Reviewed: 2026-04-09
Source of Truth: .env.example, config/settings.py, cli/commands.py, api/app.py, ui/app.py, ui/api_client.py
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

## Run Streamlit Dashboard

Start the API first, then run:

```bash
streamlit run ui/app.py
```

Optional UI env vars:

```bash
export NEPSE_UI_API_BASE_URL=http://localhost:8000
export NEPSE_UI_DEFAULT_API_VERSION=v1
export NEPSE_UI_TIMEOUT_SECONDS=10
export NEPSE_UI_MAX_ATTEMPTS=3
export NEPSE_UI_BACKOFF_SECONDS=0.5
```

UI runtime behavior:

- read-only dashboard only
- API-driven data access only
- no scoring/ranking/signal/backtest computation in UI
- client-side sorting/filtering only

For detailed UI operations, see [streamlit-dashboard.md](streamlit-dashboard.md).

## Optional: Build UI Container

`Dockerfile.ui` is available for packaging.

```bash
docker build -f Dockerfile.ui -t nepsesignal-ui:test .
```

This step requires a running Docker daemon.

## Verify Installation

```bash
pytest -v
```
