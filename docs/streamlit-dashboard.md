# Streamlit Dashboard Guide

Metadata:
- Owner: suban
- Last Reviewed: 2026-04-09
- Source of Truth: ui/app.py, ui/api_client.py, ui/components/*.py, ui/utils/error_handling.py, docs/Streamlit_UI_Development_Guidance_For_Copilot.md
- Validation Method: Code + Tests

## Purpose

This guide explains how to run and validate the read-only Streamlit dashboard for NepseSignal.

## Scope and Rules

The dashboard is strictly read-only:

- consumes backend APIs via HTTP
- displays API payloads
- allows client-side sort/filter only

The dashboard does not implement:

- scoring logic
- ranking logic
- signal generation
- backtest computation
- API-side data mutation

## Prerequisites

- Python 3.11+
- Local virtual environment (`.venv`)
- Dependencies installed from `requirements.txt`
- API server running locally or remotely

## Run Locally

1. Activate virtual environment:

```bash
source .venv/bin/activate
```

2. Start API server:

```bash
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

3. Start Streamlit dashboard:

```bash
streamlit run ui/app.py
```

## UI Environment Variables

Optional runtime config:

```bash
export NEPSE_UI_API_BASE_URL=http://localhost:8000
export NEPSE_UI_DEFAULT_API_VERSION=v1
export NEPSE_UI_TIMEOUT_SECONDS=10
export NEPSE_UI_MAX_ATTEMPTS=3
export NEPSE_UI_BACKOFF_SECONDS=0.5
```

## Feature Coverage

Implemented capabilities:

- API-backed panels: Signals, Rankings, Opportunities, Backtest, Metrics
- API Explorer for non-core endpoint groups
- contract/version diagnostics (`/contracts`, response headers)
- execution ID correlation (`execution_id` vs `/metrics` traces)
- standardized loading/empty/error/timeout states

## Validation Commands

Run UI-focused tests:

```bash
source .venv/bin/activate
pytest -q tests/ui
```

Compile UI modules:

```bash
source .venv/bin/activate
python -m py_compile ui/app.py ui/api_client.py ui/components/*.py ui/utils/*.py
```

## Container Packaging

UI container file:

- `Dockerfile.ui`

Build command:

```bash
docker build -f Dockerfile.ui -t nepsesignal-ui:test .
```

If Docker daemon is unavailable on the host, use local non-container execution (`streamlit run ui/app.py`) until daemon access is restored.

## Related Documents

- [Streamlit UI Development Guidance](Streamlit_UI_Development_Guidance_For_Copilot.md)
- [API Contracts](api-contracts.md)
- [API Server Guide](api-server.md)
- [Getting Started](getting-started.md)
