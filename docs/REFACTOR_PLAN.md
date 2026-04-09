# Architecture Evolution Log

Metadata:
Owner: suban
Last Reviewed: 2026-04-08
Source of Truth: workflows/*.py, api/*.py, nepse_api/*.py, tests/test_coordinator_parity.py
Validation Method: Code + Tests

This document tracks major architectural decisions and their implementation status.

## Completed (2026-04-08)

### Coordinator Migration (Enterprise Data Access Pattern)

- Extracted upstream calls into `NepseClientProvider` with retry/jitter
- Separated normalization into `SnapshotNormalizer` and `HistoricalNormalizer`
- Centralized orchestration in `DataFetchCoordinator` with unified fallback order
- Wire all dependencies through `build_data_fetch_coordinator()` factory
- Deprecated `NepseDataFetcher` with `LegacyNepseDataFetcher` compatibility alias
- All CLI, workflows, and API paths now use coordinator factory
- Added 8 comprehensive end-to-end parity tests in `test_coordinator_parity.py`
- Validated identical behavior: live → persisted snapshot → security master fallback
- Added scoring explainability with score breakdown models, API response types, CLI formatting, and tests
- Added structured workflow observability with execution IDs in scan/backtest/symbol flows
- Added analytics API execution_id contract for response-level traceability
- Added typed analytics response models for improved OpenAPI contract clarity
- Added typed analytics row models for opportunities and signal summary endpoints

### Earlier Completed

- Workflow modularization into workflows/*
- API contract hardening with typed models and structured error payloads
- API telemetry and metrics endpoint
- Blue-chip scoring configuration improvements
- Caching and benchmark artifact generation in workflow execution paths

## Active Work

- None

## Completed (2026-04-09)

- Added workflow failure classification for fetch, scan, score, rank, signal, and backtest stages
- Exposed workflow category, stage, and workflow metadata in API error responses
- Added workflow and API regression tests for classified validation, data, and ranking failures
- Added shared validation helpers for workflow top_n, lookback_days, rebalance, and CLI limit inputs
- Added workflow and CLI regression tests for invalid parameter handling

## Active Follow-ups

- Tighten documentation governance automation
- Expand generated API docs checks in CI
- Periodically validate feature guides against runtime signatures

## Reference Implementation Details

For implementation truth, use:

- [workflows.md](workflows.md) - workflow orchestration patterns
- [api-contracts.md](api-contracts.md) - endpoint and type contracts
- [configuration.md](configuration.md) - runtime settings and defaults
- [bluechip-scoring.md](bluechip-scoring.md) - scoring logic and rationale
- [architecture.md](architecture.md) - system design and module responsibilities
- `nepse_api/coordinator.py` - data coordinator orchestration
- `nepse_api/factory.py` - dependency wiring
- `tests/test_coordinator_parity.py` - e2e data access validation
