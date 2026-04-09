# NEPSE Signal Analyzer

Metadata:
Owner: suban
Last Reviewed: 2026-04-09
Source of Truth: main.py, cli/commands.py, config/settings.py, workflows/*.py, api/app.py, nepse_api/*.py, ui/app.py, ui/api_client.py
Validation Method: Code + Tests + E2E Parity Tests

NepseSignal is a Python application for NEPSE market analysis with CLI workflows and a FastAPI service.

## What It Does

- Fetches and normalizes NEPSE market and historical data via unified coordinator
- Builds market universe filters with deterministic scoring
- Computes blue-chip scoring with configurable normalization
- Generates BUY/SELL/HOLD signals with confidence and explainability
- Ranks opportunities and exports CSV outputs
- Runs single-symbol and portfolio backtests with metrics
- Exposes HTTP API endpoints for market, company, trading, news, mappings, and analytics
- Provides a read-only Streamlit dashboard that consumes API responses only

Central architecture:

- `nepse_api/providers.py` — upstream and persisted data providers with retry/jitter
- `nepse_api/normalizers.py` — payload normalization to canonical forms
- `nepse_api/coordinator.py` — fetch orchestration with fallback (live → persisted → security master)
- `nepse_api/factory.py` — shared wiring for CLI, workflows, and API
- `tests/test_coordinator_parity.py` — validates identical behavior across CLI/workflow/API paths

## Documentation

- [Documentation Index](docs/README.md)
- [Getting Started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [CLI Reference](docs/cli.md)
- [API Contracts](docs/api-contracts.md)
- [Workflow Reference](docs/workflows.md)
- [Configuration Reference](docs/configuration.md)
- [Streamlit Dashboard Guide](docs/streamlit-dashboard.md)
- [Blue-Chip Scoring](docs/bluechip-scoring.md)
- [Candlestick Guide](docs/CandelStick.md)
- [Troubleshooting](docs/troubleshooting.md)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Quick Start

Run these commands in separate terminals after setup:

Terminal 1 (activate environment):

```bash
source .venv/bin/activate
```

Terminal 2 (start API):

```bash
source .venv/bin/activate
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

Terminal 3 (start Streamlit UI):

```bash
source .venv/bin/activate
streamlit run ui/app.py
```

## CLI Commands

```bash
python main.py scan-market --top-n 20 --plot --output output
python main.py scan-market --top-n 20 --plot --output output --force-refresh
python main.py analyze NABIL --start-date 2024-01-01 --end-date 2026-03-31
python main.py backtest-market --top-n 20 --lookback-days 252 --rebalance monthly --output output
python main.py backtest-market --top-n 20 --lookback-days 252 --rebalance monthly --output output --force-refresh
python main.py top-volume --limit 10 --force-refresh
python main.py health-check --symbol NABIL
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

`--force-refresh` bypasses local and in-memory caches and fetches fresh data from the API.

Workflow observability:

- `scan-market`, `backtest-market`, and `analyze` emit a workflow `execution_id` in CLI logs
- benchmark artifacts include the same `execution_id` and standardized `summary` payload for cross-run correlation
- analytics API responses include `execution_id` and `summary` for correlation with workflow logs/artifacts
- API and CLI inputs now validate symbol, date, pagination, and trading-average parameters consistently before workflow execution
- backtest workflow outputs include historical validation and portfolio metrics, documented in the workflow and API contract references

Snapshot fallback order:

1. live_market from upstream provider
2. latest persisted snapshot on disk
3. security master metadata fallback

## API Server

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Streamlit Dashboard

Start API first:

```bash
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

Then run the UI:

```bash
streamlit run ui/app.py
```

Optional UI environment variables:

```bash
export NEPSE_UI_API_BASE_URL=http://localhost:8000
export NEPSE_UI_DEFAULT_API_VERSION=v1
export NEPSE_UI_TIMEOUT_SECONDS=10
export NEPSE_UI_MAX_ATTEMPTS=3
export NEPSE_UI_BACKOFF_SECONDS=0.5
```

Container image configuration exists in `Dockerfile.ui`. Building the image requires a running Docker daemon.

## Output Artifacts

Common output files under output directory:

- bluechip_ranked.csv
- signal_summary.csv
- best_buy_signals.csv
- top_buy_signals.csv
- strong_momentum.csv
- high_risk_weak.csv
- scan_benchmark.json
- portfolio_backtest.json
- portfolio_signal_set.csv
- backtest_benchmark.json

Benchmark JSON files (`scan_benchmark.json`, `backtest_benchmark.json`) include `execution_id` and `summary` for traceability across logs and outputs.

Persistent fetched datasets under data/datasets:

- snapshots/market_snapshot_YYYY-MM-DD.csv
- snapshots/market_snapshot_latest.csv
- historical/<SYMBOL>_history.csv
- sector_master.csv (optional local symbol to sector override)

Snapshot files include a data source marker per row:

- live_market
- historical_fallback
- security_master_fallback

## Testing

```bash
pytest -v
```
