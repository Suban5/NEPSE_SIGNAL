# API Contracts

Metadata:
Owner: suban
Last Reviewed: 2026-04-08
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

### Trading
- GET /trading/floor-sheet
- GET /trading/floor-sheet/{symbol}
- GET /trading/average
- GET /trading/market-depth/{symbol}

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

Analytics response contract (shared fields):
- top_n
- sector_relative
- execution_id (workflow correlation identifier)
- rows

Typed response models:
- `/analytics/bluechip-ranking` -> `AnalyticsBluechipRankingResponse`
- `/analytics/opportunities` -> `AnalyticsOpportunitiesResponse`
- `/analytics/signal-summary` -> `AnalyticsSignalSummaryResponse`

Notes:
- `AnalyticsBluechipRankingResponse` enforces typed top-level metadata (`top_n`, `sector_relative`, `execution_id`) while keeping `rows` schema flexible (`List[Dict[str, Any]]`) for backward compatibility.
- `AnalyticsOpportunitiesResponse` and `AnalyticsSignalSummaryResponse` enforce typed row schemas with `extra=allow` to preserve compatibility with additive fields.

### Observability
- GET /metrics -> RequestMetricsResponse

### Contract Metadata
- GET /contracts -> ApiContractResponse

## Error Contract

Error body model: ApiErrorResponse

Fields:
- code
- type
- method
- message
- error_id
- upstream_status
- retriable

## Validation Reference

- Route behavior and schema: tests/test_api_app.py
