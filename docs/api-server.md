# API Server Guide

Metadata:
Owner: suban
Last Reviewed: 2026-04-06
Source of Truth: api/app.py, api/service.py, api/models.py
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
