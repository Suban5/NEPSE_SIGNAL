# API Integration Notes

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
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

## Contract Stability

- Structured error payload model is defined in api/models.py.
- Contract version negotiation is available through /contracts and middleware headers.

Use [api-contracts.md](api-contracts.md) for endpoint-level request/response contracts.
