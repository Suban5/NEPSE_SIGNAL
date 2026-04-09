# API Server Guide

Metadata:
Owner: suban
Last Reviewed: 2026-04-09
Source of Truth: api/app.py, api/service.py, api/models.py, tests/test_api_app.py
Validation Method: Code + Tests

## Start Server

```bash
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

or

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

## API Docs

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Runtime Headers

The API middleware sets:

- X-Request-Id
- X-API-Contract-Version
- X-API-Supported-Versions

Version negotiation behavior:

- Request header: `X-API-Version`
- Supported values: `v1`, `v2`
- Unknown values fall back to `v1`
- `v2` adds contract metadata for analytics responses while keeping existing fields intact

## Data Fetch and Cache Behavior

API requests use the same hybrid fetch path as application workflows:

- in-memory TTL cache
- local datasets in data/datasets
- upstream API fetch as fallback

Current API routes do not expose a force-refresh query parameter. For a forced refresh, run the CLI market workflows with --force-refresh before calling analytics endpoints.

## Endpoint Groups

- Health: /health
- Market: /market/*
- Companies and securities: /companies*, /securities
- Trading: /trading/*
- News: /news/*
- Other data: /other/*
- Mappings: /mappings/*
- Analytics: /analytics/*
- Observability: /metrics
- Contract negotiation: /contracts

For complete endpoint signatures see [api-contracts.md](api-contracts.md).

## Streamlit Dashboard Integration

The Streamlit UI consumes these API groups:

- core analytics panels: `/analytics/signal-summary`, `/analytics/bluechip-ranking`, `/analytics/opportunities`, `/analytics/backtest-summary`
- diagnostics and observability: `/health`, `/metrics`, `/contracts`
- explorer mode: non-core groups (`/market/*`, `/companies*`, `/trading/*`, `/news/*`, `/other/*`, `/mappings/*`)

Recommended local run order:

1. Start API server
2. Start Streamlit UI (`streamlit run ui/app.py`)

The UI sends `X-API-Version` and surfaces response headers for diagnostics:

- `X-Request-Id`
- `X-API-Contract-Version`
- `X-API-Supported-Versions`

## Analytics Traceability

Analytics endpoints include `execution_id` in responses:

- `/analytics/bluechip-ranking`
- `/analytics/opportunities`
- `/analytics/signal-summary`

These three analytics scan routes share the same top-level response fields:

- `top_n`
- `sector_relative`
- `execution_id`
- `summary`
- `rows`

For opportunity and signal-summary analytics rows, explainability fields may be present:

- `trade_score_breakdown`
- `ranking_rationale`
- `trade_score_rank`, `confidence_rank`, `bluechip_rank`, `relative_trade_score`

This `execution_id` maps analytics responses to workflow benchmark artifacts and structured observability logs.
