# Roadmap

Metadata:
- Owner: suban
- Last Reviewed: 2026-04-09
- Source of Truth: api/app.py, api/service.py, cli/commands.py, workflows/*.py, bluechip/detector.py, docs/*.md
- Validation Method: Code + Tests

## Purpose

This document tracks feature-level progress and remaining product milestones. It is intentionally not an execution plan.

## Core Pillars

### Reliability

- deterministic scoring and ranking behavior
- robust error handling across fetch, scan, and API paths
- automated test coverage and CI enforcement

### Usability

- consistent API, CLI, and workflow outputs
- explainable signals and ranking decisions
- clear and validated documentation

### Scalability

- modular workflows with reusable services
- stable API contracts for consumers and integrations
- clear boundaries between orchestration and domain logic

## Completed

### data / nepse_api
- [x] Unified NEPSE data access with provider/coordinator/normalizer pattern.
- [x] Migrated CLI, workflows, and API to shared coordinator factory.
- [x] Added end-to-end parity tests for all data paths.
- [x] Locked in force-refresh and fallback semantics across all callers.

### workflows
- [x] Added structured workflow logging with execution IDs and benchmark correlation.
- [x] Added workflow failure classification for fetch, scan, score, rank, signal, and backtest stages.
- [x] Added shared validation helpers for workflow and CLI inputs.
- [x] Standardized workflow summary payloads for scan, backtest, and symbol analysis.
- [x] Completed D1 boundary cleanup by extracting shared fetch/validation orchestration helpers in `workflows/common.py` and preserving workflow outputs under regression tests.
- [x] Completed O1 structured stage logging for fetch/scan/score/rank with symbol scope and failure category metadata.
- [x] Completed O2 execution-ID traceability in API metrics snapshots and analytics structured logs.

### api
- [x] Exposed analytics execution IDs in API responses for end-to-end traceability.
- [x] Tightened analytics OpenAPI contracts with typed response models for response metadata.
- [x] Added typed row models for opportunities and signal summary analytics responses.
- [x] Exposed workflow category, stage, and workflow metadata in API error responses.
- [x] Standardized analytics response assembly in `api/service.py`.
- [x] Standardized analytics top-level response fields across scan routes (`top_n`, `sector_relative`, `execution_id`, `summary`, `rows`).
- [x] Added header-negotiated response versioning rules and additive `v2` analytics contract metadata.
- [x] Completed C2 contract documentation alignment with runtime routes/models and added doc-validation coverage.

### cli
- [x] Preserved CLI workflow commands with shared dependency wiring.
- [x] Kept user-facing validation behavior aligned with workflow validation.
- [x] Logged standardized workflow summary payloads for scan, backtest, and symbol analysis.
- [x] Logged backtest historical validation and portfolio metrics alongside standardized summaries.
- [x] Locked CLI summary logs to workflow `to_summary()` contracts for API/CLI/workflow field parity.

### analysis / ranking / backtesting
- [x] Added backtesting validation against historical NEPSE data and exposed summary results via API and CLI.
- [x] Enforced a single source of truth for blue-chip score access and ranking merge semantics across detector, workflows, and ranking modules.
- [x] Added ranking explainability fields (`trade_score_breakdown`, `ranking_rationale`) and comparison fields (`trade_score_rank`, `confidence_rank`, `bluechip_rank`, `relative_trade_score`) in ranked opportunity outputs.
- [x] Completed B1 backtest engine validation with deterministic fixtures and sparse-history edge-case coverage.

### reliability
- [x] Strengthened API, service, and CLI input validation for symbol, date, and pagination inputs.

### testing
- [x] Added regression coverage for API and workflow backtest-summary contract behavior.
- [x] Added workflow failure-path regressions for empty data, sparse history, malformed payloads, and upstream exception handling.

### testing
- [x] Expanded regression coverage for negative-path behavior in workflows and API routes.
  - [x] Added service-layer regression tests for retry policy, cache reuse, and analytics payload contract/caching behavior.
  - [x] Added API regression tests for timeout handling contract (`UPSTREAM_TIMEOUT`) and ranking failure classification metadata.
  - [x] Synchronized documentation with newly tested negative-path contracts in `api-contracts.md` and `workflows.md`.
  - [x] Added dedicated high-coverage suites for normalizers, signal adapter, cache adapter, candlestick adapter, persistence, and provider layers.
  - [x] Increased overall project test coverage baseline to roughly 93 percent.
  - [x] Completed service/workflow coverage objective with measured baseline validation for critical modules.
  - [x] Enabled CI coverage enforcement via `.github/workflows/ci.yml` with a 90 percent minimum gate.

### scalability / code duplication reduction (S1)
- [x] Reduced duplication between `api/service.py`, `cli/commands.py`, and `workflows/*.py`.
  - [x] Mapped and documented duplicate logic patterns across service analytics response, CLI workflow logging.
  - [x] Extracted `_analytics_rows_response()` shared helper consolidating 3 try/except blocks (bluechip-ranking, opportunities, signal-summary).
  - [x] Extracted `_log_workflow_summary()` shared helper consolidating CLI workflow summary logging (scan, backtest, symbol).
  - [x] Validated refactor with full test suite (396 tests passing, 2026-04-09).
  - [x] Frozen UI1 contract (endpoints and field shapes) in `docs/api-contracts.md` for stable dashboard consumption.

### ui / dashboard (UI1 & UI2)
- [x] **UI1 Complete (2026-04-09):** Defined minimal dashboard scope with 4 panels (signals, rankings, backtest summary, observability).
  - [x] UI1-T1: Defined dashboard screens and data needs with 3 primary + 1 optional panel.
  - [x] UI1-T2: Confirmed zero backend logic duplication across all scoring/ranking/backtesting modules.
  - [x] UI1-T3: Identified minimum API surface: 5 frozen endpoints with required fields documented.
  - [x] Reference templates: UI1_Dashboard_Scope.md, UI1_API_Contract_Mapping.md (preserved as backup).
  
- [x] **UI2 Complete (2026-04-09):** Mapped endpoints to views and added comprehensive smoke validation tests.
  - [x] UI2-T1: Endpoint-to-view mapping with field transformations (API field → UI display format) for all 4 panels.
  - [x] UI2-T2: Charting/reporting reuse evaluated; documented existing OHLC functions and recommended native UI charting for analytics.
  - [x] UI2-T3: Created 6 curl-based smoke tests (tests/ui2_smoke_tests.sh) validating all endpoints + error handling.
  - [x] Data freshness strategy: HTTP cache with manual refresh option.
  - [x] Production reference: UI2_Endpoint_View_Mapping.md with complete field definitions.
  
- Dashboard implementation ready with:
  - Frozen contract for 5 endpoints (no breaking changes until UI1 released).
  - Complete field mapping for 4 visualizable panels.
  - Smoke tests for pre-deployment validation: `bash tests/ui2_smoke_tests.sh http://localhost:8000`.
  - Zero backend logic duplication; display-only architecture.

## In Progress

### testing
- [ ] No active testing tasks currently.

## Remaining / Planned

### api
- [ ] Expand versioned API response coverage beyond analytics routes while preserving additive compatibility.
- [ ] Expand generated API docs checks in CI.

### analysis / ranking / backtesting
- [ ] Evolve scoring rationale wording and thresholds as model tuning changes over time.

### api / cli / workflows
- [ ] Maintain the standardized output contracts as new analytics routes and workflow summaries are introduced.

### product
- [ ] Provide a lightweight dashboard for exploration and reporting.
- [ ] Support richer visualization and historical comparison views.
- [ ] Improve release and versioning discipline for long-term maintainability.

## Strategy Notes

### Backend-First Path

- stabilize data, scoring, and contract behavior first
- complete quality gates and observability before UI work
- add UI only after core outputs are trusted
- treat contract stability and test coverage as release gates

### Recommended Default

- Prefer a backend-first path with a thin UI introduced once core outputs are stable.

## Non-Goals

- real-time trading execution
- high-frequency data ingestion
- complex frontend frameworks
- speculative features without code or test support

## Documentation Strategy

Documentation should stay aligned with code and tests through maintained reference files such as:

- FEATURE_STATUS.md
- API_CONTRACT.md
- SCORING_LOGIC.md
- api-contracts.md
- bluechip-scoring.md

Where possible, docs should be validated against runtime signatures and route behavior.
