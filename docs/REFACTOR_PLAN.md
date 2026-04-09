# Architecture Evolution Log

Metadata:
- Owner: suban
- Last Reviewed: 2026-04-09
- Source of Truth: workflows/*.py, api/*.py, nepse_api/*.py, tests/test_coordinator_parity.py
- Validation Method: Code + Tests

This document tracks technical refactoring status and architectural decisions.

## Completed

### data / nepse_api
- [x] Extracted upstream calls into `NepseClientProvider` with retry/jitter.
- [x] Separated normalization into `SnapshotNormalizer` and `HistoricalNormalizer`.
- [x] Centralized orchestration in `DataFetchCoordinator` with a unified fallback order.
- [x] Wired CLI, workflows, and API through `build_data_fetch_coordinator()`.
- [x] Kept `NepseDataFetcher` available as `LegacyNepseDataFetcher` compatibility alias.
- [x] Added parity tests covering live, persisted snapshot, and security master fallback behavior.

### workflows
- [x] Modularized scan, backtest, and symbol orchestration into `workflows/*.py`.
- [x] Added structured workflow logging with `execution_id` correlation.
- [x] Standardized workflow summary payloads with `Context.to_summary()` and benchmark `summary` fields.
- [x] Added workflow failure classification for fetch, scan, score, rank, signal, and backtest stages.
- [x] Added shared validation helpers for `top_n`, `lookback_days`, `rebalance`, and CLI `limit` inputs.
- [x] Added workflow regression tests for summary, failure classification, and invalid parameter handling.
- [x] Added historical-data sufficiency validation to market backtest with benchmark-visible validation metadata.

### api
- [x] Hardened API contracts with typed models and structured `ApiErrorResponse` payloads.
- [x] Added analytics `execution_id` and optional `summary` fields to analytics responses.
- [x] Exposed workflow category, stage, and workflow metadata in API error responses.
- [x] Added OpenAPI/schema tests for analytics and error contract models.
- [x] Consolidated analytics response assembly in `api/service.py` through a shared helper.
- [x] Added typed analytics backtest summary endpoint exposing workflow summary, historical validation, and portfolio metrics.
- [x] Hardened API/service validation for symbol, date, and pagination inputs with client-error mapping.

### cli
- [x] Kept CLI dispatch thin and aligned it with shared workflow dependencies.
- [x] Preserved user-facing validation behavior while using typed workflow validation internally.
- [x] Added CLI summary logging for scan, backtest, and symbol workflows.
- [x] Added CLI regression tests for invalid parameter handling.
- [x] Extended market backtest CLI logs with historical validation and portfolio metric payloads.
- [x] Added CLI validation for symbol date ranges before workflow execution.

### analysis / ranking / backtesting
- [x] Added scoring explainability with score breakdown models and response formatting.
- [x] Kept ranking and backtesting aligned with workflow-driven outputs and benchmark artifacts.
- [x] Centralized blue-chip score access and merge semantics in `bluechip/detector.py` for workflow and ranking consumers.

### testing
- [x] Expanded workflow and service-layer regression coverage for edge cases and negative paths.
  - [x] Added service-layer tests for retry behavior, cached call reuse, and analytics payload caching in `tests/test_api_service.py`.
  - [x] Added API negative-path tests for workflow ranking classification and timeout-to-504 mapping in `tests/test_api_app.py`.
  - [x] Updated `docs/api-contracts.md` and `docs/workflows.md` with explicit negative-path contract documentation.
  - [x] Added dedicated module suites for `nepse_api/normalizers.py`, `signals/signal_engine.py`, `api/cache.py`, and `candlestick/patterns.py`.
  - [x] Added comprehensive persistence/provider suites for `nepse_api/data_persistence.py` and `nepse_api/providers.py`.
  - [x] Raised overall project test coverage baseline to roughly 93 percent with targeted branch coverage improvements.
  - [x] Completed coverage expansion objective for service and workflow layers and validated baseline coverage across critical modules.
  - [x] Added CI coverage enforcement target in `.github/workflows/ci.yml` using `--cov-fail-under=90`.
  - [x] Added regression tests for API and service-layer backtest summary contract and workflow historical-validation metadata.
  - [x] Added workflow failure-path regressions covering missing history, sparse buy sets, malformed history rows, retriable upstream failures, and artifact stability after workflow exceptions.

## In Progress

### testing
  - [ ] No active testing tasks currently.

## Remaining / Planned

### api
- [ ] Introduce versioned API response handling and explicit backward-compatibility rules.

### workflows
- [ ] Continue tightening workflow orchestration boundaries so shared helpers live in one place.

### docs / ci
- [ ] Expand generated API docs checks in CI.
- [ ] Tighten documentation governance automation.
- [ ] Periodically validate feature guides against runtime signatures.

## Reference Implementation Details

For implementation truth, use:

- [workflows.md](workflows.md) - workflow orchestration patterns
- [api-contracts.md](api-contracts.md) - endpoint and type contracts
- [configuration.md](configuration.md) - runtime settings and defaults
- [bluechip-scoring.md](bluechip-scoring.md) - scoring logic and rationale
- [architecture.md](architecture.md) - system design and module responsibilities
- `nepse_api/coordinator.py` - data coordinator orchestration
- `nepse_api/factory.py` - dependency wiring
- `tests/test_coordinator_parity.py` - end-to-end data access validation
