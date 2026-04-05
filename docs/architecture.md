# Architecture

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: workflows/*.py, api/*.py, cli/commands.py, config/settings.py
Validation Method: Code + Tests

## Runtime Layers

1. Configuration and Logging
- config/settings.py

2. Data Access
- nepse_api/data_fetcher.py

3. Domain Processing
- market/*
- bluechip/*
- analysis/*
- candlestick/*
- signals/*
- ranking/*
- backtesting/*
- visualization/*

4. Workflow Orchestration
- workflows/market_scan.py
- workflows/market_backtest.py
- workflows/symbol_analysis.py
- workflows/common.py

5. Delivery Interfaces
- CLI: main.py, cli/commands.py
- API: api/app.py, api/service.py, api/models.py, api/telemetry.py, api_server.py

## Workflow Model

Workflows use dependency dataclasses to inject fetch/scoring/signal/ranking behavior and return typed context objects. This keeps CLI thin and reusable.

## API Model

- FastAPI routes in api/app.py
- Service wrapper in api/service.py
- Pydantic contracts in api/models.py
- Request middleware adds request id and API contract headers
- In-memory telemetry exposed via GET /metrics

## Caching and Reliability

- TTL cache in api/cache.py and workflow helpers
- Retry behavior configured via settings for API and market fetching paths
- Structured error responses and timeout handling in API wrapper
