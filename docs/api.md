# API Integration Notes

Metadata:
Owner: suban
Last Reviewed: 2026-04-06
Source of Truth: api/service.py, nepse_api/data_fetcher.py, api/app.py
Validation Method: Code + Tests

This document explains integration boundaries.

## Upstream Data Source

- NEPSE data is fetched through nepse_client.
- API routes do not call raw HTTP endpoints directly in route handlers.
- Service methods normalize payload shape before returning route responses.

## Retry and Timeout Behavior

- API service has retry rules for retryable upstream failures.
- Floor-sheet route supports explicit timeout_seconds query parameter.

## Cache and Persistence

- Fetcher uses hybrid caching: memory cache first, then persistent local datasets, then upstream API.
- Persistent datasets are stored under data/datasets/snapshots and data/datasets/historical.
- API routes currently do not expose force-refresh; use CLI workflows with --force-refresh when you need to refresh local datasets immediately.

## Contract Stability

- Structured error payload model is defined in api/models.py.
- Contract version negotiation is available through /contracts and middleware headers.

Use [api-contracts.md](api-contracts.md) for endpoint-level request/response contracts.
