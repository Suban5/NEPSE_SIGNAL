# Feature 07: HTTP API

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: api/app.py, api/models.py, api/service.py, tests/test_api_app.py
Validation Method: Code + Tests

## Purpose

Expose NEPSE data and analytics through FastAPI routes with typed request/response contracts.

## Start

```bash
python main.py run-api --host 0.0.0.0 --port 8000 --reload
```

## Core Endpoint Families

- /health
- /market/*
- /companies* and /securities
- /trading/*
- /news/*
- /other/*
- /mappings/*
- /analytics/*
- /metrics
- /contracts

## Contract Details

- Request/response models in api/models.py
- Structured error payload returned for upstream failures
- Contract negotiation via X-API-Version request header and /contracts endpoint

See [../api-contracts.md](../api-contracts.md) for full contract listing.
