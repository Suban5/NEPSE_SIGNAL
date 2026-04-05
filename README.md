# NEPSE Signal Analyzer

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: main.py, cli/commands.py, config/settings.py, workflows/*.py, api/app.py
Validation Method: Code + Tests

NepseSignal is a Python application for NEPSE market analysis with CLI workflows and a FastAPI service.

## What It Does

- Fetches and normalizes NEPSE market and historical data
- Builds market universe filters
- Computes blue-chip scoring with configurable normalization
- Generates BUY/SELL/HOLD signals with confidence
- Ranks opportunities and exports CSV outputs
- Runs single-symbol and portfolio backtests
- Exposes HTTP API endpoints for market, company, trading, news, mappings, and analytics

## Documentation

- [Documentation Index](docs/README.md)
- [Getting Started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [CLI Reference](docs/cli.md)
- [API Contracts](docs/api-contracts.md)
- [Workflow Reference](docs/workflows.md)
- [Configuration Reference](docs/configuration.md)
- [Blue-Chip Scoring](docs/bluechip-scoring.md)
- [Troubleshooting](docs/troubleshooting.md)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## CLI Commands

```bash
python main.py scan-market --top-n 20 --plot --output output
python main.py analyze NABIL --start-date 2024-01-01 --end-date 2026-03-31
python main.py backtest-market --top-n 20 --lookback-days 252 --rebalance monthly --output output
python main.py health-check --symbol NABIL
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

## API Server

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

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

## Testing

```bash
pytest -v
```
