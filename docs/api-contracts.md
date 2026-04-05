# API Contracts

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: api/app.py, api/models.py, tests/test_api_app.py
Validation Method: Code + Tests

## Base

- App: FastAPI(title="NepseSignal API", version="1.0.0")
- Supported contract versions: v1, v2
- Contract discovery endpoint: GET /contracts

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
