# API Contracts

Metadata:
Owner: suban
Last Reviewed: 2026-04-09
Source of Truth: api/app.py, api/models.py, tests/test_api_app.py
Validation Method: Code + Tests

## Base

- App: FastAPI(title="NepseSignal API", version="1.0.0")
- Supported contract versions: v1, v2
- Contract discovery endpoint: GET /contracts

Versioning strategy:

- Header-negotiated versioning via `X-API-Version`
- Unknown/unsupported versions safely fall back to `v1`
- v1 preserves existing response shapes
- v2 introduces additive metadata only (backward-compatible)
- Non-analytics typed endpoints (`/health`, `/metrics`) also include additive `contract` metadata for `v2` requests

Data freshness behavior for API-backed analytics routes:

- default fetch path: memory cache -> local datasets -> upstream API
- no route-level force-refresh query parameter is currently defined in the API contract
- forced refresh can be triggered via CLI workflows using --force-refresh

## Core Endpoints

### Health
- GET /health -> HealthResponse

Version-aware health metadata:

- For `v2` requests, `/health` includes additive `contract` with:
  - `version`
  - `compatibility_policy`
  - `request_header`

### Market
- GET /market/status
- GET /market/summary
- GET /market/index
- GET /market/sub-indices
- GET /market/live
- GET /market/price-volume
- GET /market/supply-demand
- GET /market/top-gainers
- GET /market/top-losers
- GET /market/top-trade-scrips
- GET /market/top-transaction-scrips
- GET /market/top-turnover-scrips

### Company and Security
- GET /companies
- GET /securities
- GET /companies/{symbol}
- GET /companies/{symbol}/history
- GET /companies/{symbol}/graph
- GET /companies/{company_id}/financials
- GET /companies/{company_id}/agm
- GET /companies/{company_id}/dividend
- GET /companies/{company_id}/market-depth

Validation notes:
- `/companies/{symbol}` and other symbol-based routes normalize to uppercase and reject non-alphanumeric symbols in the service layer.
- `/companies/{symbol}/history` rejects inverted date ranges where `start_date > end_date`.

### Trading
- GET /trading/floor-sheet
- GET /trading/floor-sheet/{symbol}
- GET /trading/average
- GET /trading/market-depth/{symbol}

Validation notes:
- `/trading/average` requires `business_date` to use `YYYY-MM-DD` format and `n_days >= 1`.
- `/news/company` and `/news/alerts` require `page >= 1` and `page_size >= 1`.

### News
- GET /news/company
- GET /news/alerts
- GET /news/press-releases
- GET /news/notices

### Other
- GET /other/holidays
- GET /other/debentures-bonds
- GET /other/price-volume-history

### Mappings
- GET /mappings/company-id
- GET /mappings/security-id
- GET /mappings/sector-scrips

### Analytics
- GET /analytics/bluechip-ranking
- GET /analytics/opportunities
- GET /analytics/signal-summary
- GET /analytics/backtest-summary

Analytics response contract (shared fields):
- top_n
- sector_relative
- execution_id (workflow correlation identifier)
- summary (optional workflow summary object shared with CLI/workflow artifacts)
- rows

Version-aware analytics metadata:

- For `v2` requests, analytics responses include `contract` with:
  - `version`
  - `compatibility_policy`
  - `request_header`

U1 field inventory (API, CLI, workflow alignment):

| Surface | Contract Scope | Required Fields |
|---|---|---|
| API analytics scan routes (`/analytics/bluechip-ranking`, `/analytics/opportunities`, `/analytics/signal-summary`) | top-level response | `top_n`, `sector_relative`, `execution_id`, `summary`, `rows` |
| Workflow summaries (`MarketScanContext.to_summary`, `MarketBacktestContext.to_summary`, `SymbolAnalysisContext.to_summary`) | summary payload | `workflow`, `execution_id` plus workflow-specific fields |
| CLI workflow logs (`scan-market`, `backtest-market`, `analyze`) | emitted summary object | Uses `context.to_summary()` unchanged to preserve key parity with workflow summary and API `summary` |

Typed response models:
- `/analytics/bluechip-ranking` -> `AnalyticsBluechipRankingResponse`
- `/analytics/opportunities` -> `AnalyticsOpportunitiesResponse`
- `/analytics/signal-summary` -> `AnalyticsSignalSummaryResponse`
- `/analytics/backtest-summary` -> `AnalyticsBacktestSummaryResponse`

Backtest analytics response contract:
- top_n
- lookback_days
- rebalance
- sector_relative
- execution_id
- summary (`WorkflowSummary`)
- historical_validation (`BacktestHistoricalValidation`)
- portfolio_metrics (`BacktestPortfolioMetrics`)

Notes:
- `AnalyticsBluechipRankingResponse` enforces typed top-level metadata (`top_n`, `sector_relative`, `execution_id`) while keeping `rows` schema flexible (`List[Dict[str, Any]]`) for backward compatibility.
- `AnalyticsOpportunitiesResponse`, `AnalyticsSignalSummaryResponse`, and the shared `AnalyticsRowsResponse` include an optional `summary` field that mirrors the workflow summary contract and keep typed row schemas with `extra=allow` to preserve compatibility with additive fields.
- `WorkflowSummary` captures the standardized execution summary shared across CLI logs, workflow benchmark payloads, and API analytics responses.
- For `market_backtest`, `WorkflowSummary` also includes portfolio metrics (`portfolio_cagr`, `portfolio_max_drawdown`, `portfolio_sharpe_ratio`, `portfolio_total_return`) and historical sufficiency counts (`historical_symbols_validated`, `historical_symbols_sufficient`, `historical_symbols_insufficient`).

U2 explainability contract:

- Minimum blue-chip score breakdown fields are exposed as `score_breakdown`: `market_cap`, `volume`, `stability`, `trend`, `fundamental`, `sector`.
- Opportunity and signal-summary rows may include ranking rationale fields:
  - `trade_score_breakdown` (weighted contribution map)
  - `ranking_rationale` (readable rationale string)
- Comparison-friendly fields used for ranking analysis:
  - `trade_score_rank`, `confidence_rank`, `bluechip_rank`, `relative_trade_score`

### Observability
- GET /metrics -> RequestMetricsResponse

Version-aware observability metadata:

- For `v2` requests, `/metrics` includes additive `contract` with:
  - `version`
  - `compatibility_policy`
  - `request_header`

O1 structured logging schema (workflow and analytics service events):

- `event`: event identifier (`stage_started`, `stage_completed`, `stage_failed`, `analytics_stage`)
- `stage`: pipeline stage (`fetch`, `scan`, `score`, `rank`, etc.)
- `category`: `success` or classified failure category (`validation`, `data`, `upstream`, `ranking`)
- `symbol_scope`: stage-specific symbol/row counts for context

O2 execution-ID traceability additions:

- `/metrics` includes execution trace fields for workflow-backed analytics routes:
  - `execution_trace_counts` (per-endpoint count of traced execution IDs)
  - `last_execution_id_by_endpoint` (latest execution ID seen for each traced endpoint)
- analytics service structured log events include `execution_id` on success paths for end-to-end correlation

### Contract Metadata
- GET /contracts -> ApiContractResponse

Contract metadata fields:
- default_version
- negotiated_version
- supported_versions
- versioning_strategy
- compatibility_policy
- request_header

## Error Contract

Error body model: ApiErrorResponse

### Standard Fields
- code: error classification code (UPSTREAM_ERROR, UPSTREAM_TIMEOUT)
- type: exception class name (RuntimeError, TimeoutError, etc.)
- method: API method name that failed (market_status, live_market, etc.)
- message: exception message or descriptive error text
- error_id: unique error identifier for correlation and logging
- upstream_status: HTTP status code from upstream service when available (401, 503, etc.)
- retriable: boolean indicating whether the error is safe to retry

### Workflow-Classified Error Fields

When a workflow orchestration layer raises a classified error (WorkflowValidationError, WorkflowRankingError, etc.), the error payload includes:
- category: workflow failure classification (validation, ranking, data, upstream)
- stage: workflow processing stage where the failure occurred (validate, fetch, rank, signal, backtest, persist)
- workflow: workflow name (market_scan, market_backtest, symbol_analysis, etc.)

Example (validation error):
```json
{
  "error": {
    "code": "UPSTREAM_ERROR",
    "type": "WorkflowValidationError",
    "method": "market_scan",
    "message": "invalid parameter",
    "error_id": "scan-abc123",
    "category": "validation",
    "stage": "validate",
    "workflow": "market_scan",
    "retriable": false
  }
}
```

### Timeout Contract

When a long-running operation times out (e.g., floor_sheet endpoint with timeout_seconds parameter), the error response uses:
- code: UPSTREAM_TIMEOUT
- type: TimeoutError
- status_code: 504 (GatewayTimeout)
- message: includes the timeout duration

Example:
```json
{
  "error": {
    "code": "UPSTREAM_TIMEOUT",
    "type": "TimeoutError",
    "method": "floor_sheet",
    "message": "Request timed out after 30 seconds"
  }
}
```

## UI1 Stable Contract - Frozen Endpoints for Dashboard Consumption

**Purpose:** This section documents the minimal, stable API surface committed for UI1 (dashboard) consumption. Endpoints and field shapes listed here are frozen until UI1 is released.

**Frozen Endpoints:**

1. **GET /analytics/signal-summary**
   - Purpose: Top trade signals for dashboard display
   - Required Query Params: `top_n` (default 10), `sector_relative` (default false)
   - Response Fields (guaranteed stable):
     - `top_n`: integer (top N signals requested)
     - `sector_relative`: boolean (relative ranking flag)
     - `execution_id`: string (workflow correlation ID)
     - `summary`: optional WorkflowSummary object
     - `rows`: list of signals with at minimum: symbol, trade_score, confidence, signal_type
   - Versioning: Safe for v1 and v2 (v2 adds contract metadata only)
   - Error Contract: ApiErrorResponse with code, type, message fields

2. **GET /analytics/bluechip-ranking**
   - Purpose: Blue-chip stock rankings for dashboard display
   - Required Query Params: `top_n` (default 10), `sector_relative` (default false)
   - Response Fields (guaranteed stable):
     - `top_n`: integer (top N rankings requested)
     - `sector_relative`: boolean (relative ranking flag)
     - `execution_id`: string (workflow correlation ID)
     - `summary`: optional WorkflowSummary object
     - `rows`: list of rankings with at minimum: symbol, bluechip_score, market_cap, stability
   - Versioning: Safe for v1 and v2 (v2 adds contract metadata only)
   - Error Contract: ApiErrorResponse with code, type, message fields

3. **GET /analytics/backtest-summary**
   - Purpose: Portfolio backtest metrics for dashboard display
   - Required Query Params: `lookback_days` (int, >= 1), `rebalance` (enum), `sector_relative` (default false)
   - Response Fields (guaranteed stable):
     - `top_n`: integer (portfolio size)
     - `lookback_days`: integer (backtest window)
     - `rebalance`: string (rebalance frequency)
     - `execution_id`: string (workflow correlation ID)
     - `summary`: optional WorkflowSummary object with portfolio metrics
     - `historical_validation`: object with symbol sufficiency counts
     - `portfolio_metrics`: object with cagr, max_drawdown, sharpe_ratio, total_return
   - Versioning: Safe for v1 and v2 (v2 adds contract metadata only)
   - Error Contract: ApiErrorResponse with code, type, message fields

4. **GET /health**
   - Purpose: Service health check before UI loads
   - Response Fields: status (e.g., "healthy")
   - Versioning: Stable across all versions

5. **GET /metrics**
   - Purpose: Workflow execution telemetry for UI observability (optional consumption)
   - Response Fields (guaranteed stable):
     - `execution_trace_counts`: dict of endpoint -> trace count
     - `last_execution_id_by_endpoint`: dict of endpoint -> latest execution_id
   - Versioning: Safe for v1 and v2

**Field Stability Guarantees:**

- Core response fields (top_n, execution_id, rows, summary) are **not removed or renamed** in v1 or v2
- `rows` arrays preserve minimum required fields (symbol, score/rank, secondary fields)
- `execution_id` and `summary` remain optional but present on success
- Error responses maintain ApiErrorResponse shape (code, type, message, error_id, retriable)

**Breaking Changes Policy for UI1:**

- Response field removal or rename: **Not permitted** until UI1 is released and upgraded
- Additive fields (new columns in rows, new summary fields): **Permitted** without notification
- Type changes (e.g., string -> number): **Not permitted** for existing fields
- Response pagination: **Not introduced** during UI1 development (row counts remain pageless)

**Data Freshness Behavior for UI1:**

- UI requests use default fetch path: memory cache -> local datasets -> upstream API
- No force-refresh query parameter is exposed in UI1 contract
- Backtest summary uses provided `lookback_days` and `rebalance` params; does not auto-adjust

**Versioning Expansion Status (S2 Complete):**

- S2 now extends additive `v2` contract metadata beyond analytics routes to non-analytics typed endpoints (`/health`, `/metrics`)
- Breaking changes still require a coordinated client upgrade or fallback response version
- Version negotiation remains header-driven via `X-API-Version`

## Validation Reference

- Route behavior and schema: tests/test_api_app.py
- Service retry and error classification: tests/test_api_service.py

## C2 Doc Alignment Review

Doc-to-code review status (2026-04-09):

- Checked endpoint inventory in this file against route decorators in `api/app.py`
- Checked response model references against `api/models.py`
- Checked versioning metadata contract fields against `/contracts` response behavior

Actionable mismatches:

- None currently identified

Ongoing validation:

- `tests/test_api_app.py` includes doc alignment assertions for key endpoint and model references in this file
