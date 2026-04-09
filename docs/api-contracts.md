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

Data freshness behavior for API-backed analytics routes:

- default fetch path: memory cache -> local datasets -> upstream API
- no route-level force-refresh query parameter is currently defined in the API contract
- forced refresh can be triggered via CLI workflows using --force-refresh

## Core Endpoints

### Health
- GET /health -> HealthResponse

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

### Observability
- GET /metrics -> RequestMetricsResponse

### Contract Metadata
- GET /contracts -> ApiContractResponse

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

## Validation Reference

- Route behavior and schema: tests/test_api_app.py
- Service retry and error classification: tests/test_api_service.py
