# UI2: Endpoint-to-View Mapping and Smoke Validation

**Metadata:**
- Owner: suban
- Date: 2026-04-09
- Status: UI2-T1/T2/T3 Implementation
- Source of Truth: api/app.py, api/models.py, UI1_Dashboard_Scope.md, visualization/charts.py
- Validation Method: Curl smoke tests + API contract tests

---

## Purpose

Document how each dashboard panel (UI view) maps to backend API endpoints, what data transformation (if any) occurs, and how existing charting/reporting outputs are reused.

---

## Dashboard Panel → API Endpoint Mapping

### Panel 1: Top Trade Signals

| Aspect | Value |
|---|---|
| **UI View Name** | SignalsPanel / TopSignals |
| **Data Source Endpoint** | `GET /analytics/signal-summary` |
| **Query Parameters** | `top_n` (int, default 10), `sector_relative` (boolean, default false) |
| **Required Response Fields** | `top_n`, `sector_relative`, `execution_id`, `rows` |
| **Key Display Fields** | `symbol`, `signal`, `confidence`, `trade_score`, `bluechip_score` |
| **Data Transformation** | None—consume API rows directly; client-side sorting/filtering only |
| **Charting/Reporting Reuse** | N/A (table display only) |
| **Error Handling** | Display ApiErrorResponse.error.message to user |
| **Caching Strategy** | HTTP cache via response headers; manual refresh available |

**Field Mapping (API → UI Display):**
```json
{
  "api_field": "symbol",
  "display_label": "Symbol",
  "format": "uppercase text"
}
{
  "api_field": "signal",
  "display_label": "Signal Type",
  "format": "enum (BUY, STRONG_BUY, SELL, STRONG_SELL, HOLD)"
}
{
  "api_field": "confidence",
  "display_label": "Confidence",
  "format": "number, 3 decimals, 0.0-1.0"
}
{
  "api_field": "trade_score",
  "display_label": "Trade Score",
  "format": "number, 3 decimals, optional"
}
{
  "api_field": "bluechip_score",
  "display_label": "Blue-Chip Score",
  "format": "number, 3 decimals, optional"
}
{
  "api_field": "ranking_rationale",
  "display_label": "Rationale",
  "format": "text, optional"
}
```

---

### Panel 2: Blue-Chip Rankings

| Aspect | Value |
|---|---|
| **UI View Name** | RankingsPanel / BlueChipRankings |
| **Data Source Endpoint** | `GET /analytics/bluechip-ranking` |
| **Query Parameters** | `top_n` (int, default 10), `sector_relative` (boolean, default false) |
| **Required Response Fields** | `top_n`, `sector_relative`, `execution_id`, `rows` |
| **Key Display Fields** | `rank`, `symbol`, `sector`, `bluechip_score`, `score_breakdown` |
| **Data Transformation** | None—consume API rows directly; score_breakdown displayed as-is or visualized as heat-map |
| **Charting/Reporting Reuse** | Optional: Use existing charting functions to render score breakdown as bar/heat-map chart |
| **Error Handling** | Display ApiErrorResponse.error.message to user |
| **Caching Strategy** | HTTP cache; manual refresh available |

**Field Mapping (API → UI Display):**
```json
{
  "api_field": "rank",
  "display_label": "Rank",
  "format": "integer, 1-indexed"
}
{
  "api_field": "symbol",
  "display_label": "Symbol",
  "format": "uppercase text"
}
{
  "api_field": "sector",
  "display_label": "Sector",
  "format": "text"
}
{
  "api_field": "bluechip_score",
  "display_label": "Blue-Chip Score",
  "format": "number, 3 decimals, 0.0-1.0"
}
{
  "api_field": "score_breakdown.market_cap",
  "display_label": "Market Cap Score",
  "format": "number, 3 decimals, 0.0-1.0"
}
{
  "api_field": "score_breakdown.volume",
  "display_label": "Volume Score",
  "format": "number, 3 decimals, 0.0-1.0"
}
{
  "api_field": "score_breakdown.stability",
  "display_label": "Stability Score",
  "format": "number, 3 decimals, 0.0-1.0"
}
{
  "api_field": "score_breakdown.trend",
  "display_label": "Trend Score",
  "format": "number, 3 decimals, 0.0-1.0"
}
{
  "api_field": "score_breakdown.fundamental",
  "display_label": "Fundamental Score",
  "format": "number, 3 decimals, 0.0-1.0"
}
{
  "api_field": "score_breakdown.sector",
  "display_label": "Sector Score",
  "format": "number, 3 decimals, 0.0-1.0, optional"
}
```

**Score Breakdown Visualization Options (Reusing Charting):**
- Bar chart: 6 horizontal bars (market_cap, volume, stability, trend, fundamental, sector) with values 0.0–1.0
- Heat-map: Color intensity represents score magnitude (red=low, green=high)
- Text summary: "market_cap=0.85, volume=0.72, ..." format

---

### Panel 3: Portfolio Backtest Summary

| Aspect | Value |
|---|---|
| **UI View Name** | BacktestPanel / BacktestSummary |
| **Data Source Endpoint** | `GET /analytics/backtest-summary` |
| **Query Parameters** | `lookback_days` (int, >= 1, default 252), `rebalance` (string, enum: "monthly" / "quarterly" / "biannually" / "annually"), `sector_relative` (boolean, default false) |
| **Required Response Fields** | `top_n`, `lookback_days`, `rebalance`, `sector_relative`, `execution_id`, `summary`, `historical_validation`, `portfolio_metrics` |
| **Key Display Fields** | `portfolio_metrics.cagr`, `portfolio_metrics.max_drawdown`, `portfolio_metrics.sharpe_ratio`, `portfolio_metrics.total_return` |
| **Data Transformation** | None—consume metrics as-is; format numbers for display |
| **Charting/Reporting Reuse** | Optional: Use existing visualization functions to render:  - Line chart (portfolio cumulative return over backtest window)  - Drawdown chart (underwater plot)  - Metrics summary cards |
| **Error Handling** | Display ApiErrorResponse.error.message to user |
| **Caching Strategy** | HTTP cache; manual refresh available |

**Field Mapping (API → UI Display):**
```json
{
  "api_field": "portfolio_metrics.cagr",
  "display_label": "Annual Return (CAGR)",
  "format": "number, 2 decimals, % unit"
}
{
  "api_field": "portfolio_metrics.max_drawdown",
  "display_label": "Max Drawdown",
  "format": "number, 2 decimals, % unit"
}
{
  "api_field": "portfolio_metrics.sharpe_ratio",
  "display_label": "Sharpe Ratio",
  "format": "number, 3 decimals, no unit"
}
{
  "api_field": "portfolio_metrics.total_return",
  "display_label": "Total Return",
  "format": "number, 2 decimals, % unit"
}
{
  "api_field": "historical_validation.sufficient_symbols",
  "display_label": "Symbols with Sufficient History",
  "format": "integer / total"
}
{
  "api_field": "historical_validation.insufficient_symbols",
  "display_label": "Symbols with Insufficient History",
  "format": "integer (warning if > 0)"
}
```

**Metrics Summary Cards:**
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  CAGR       │ Max Drawdown│ Sharpe      │ Total Return│
│  15.23%     │  -22.45%    │  1.234      │  52.10%     │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

---

### Panel 4: Workflow Observability (Optional)

| Aspect | Value |
|---|---|
| **UI View Name** | ObservabilityPanel / ExecutionMetadata |
| **Data Source Endpoint** | `GET /metrics` (optional) |
| **Query Parameters** | None |
| **Required Response Fields** | `execution_trace_counts`, `last_execution_id_by_endpoint` |
| **Key Display Fields** | `execution_id` (from analytics response), execution trace metadata |
| **Data Transformation** | Extract execution_id from panel responses; correlate with /metrics traces |
| **Charting/Reporting Reuse** | N/A (metadata display only) |
| **Error Handling** | Silent fallback if /metrics unavailable (non-critical) |
| **Caching Strategy** | No caching (always fetch fresh) |

**Field Mapping (API → UI Display):**
```json
{
  "api_field": "execution_id",
  "display_label": "Execution ID",
  "format": "text, copiable to clipboard"
}
{
  "api_field": "last_execution_id_by_endpoint['/analytics/signal-summary']",
  "display_label": "Signal Summary Trace",
  "format": "text"
}
{
  "api_field": "last_execution_id_by_endpoint['/analytics/bluechip-ranking']",
  "display_label": "Ranking Trace",
  "format": "text"
}
{
  "api_field": "last_execution_id_by_endpoint['/analytics/backtest-summary']",
  "display_label": "Backtest Trace",
  "format": "text"
}
```

---

## Charting and Reporting Reuse

**Existing Functions in `visualization/charts.py`:**

1. **`save_mplfinance_chart(df, symbol, output_dir)`**
   - Purpose: Render candlestick chart with OHLC data
   - Reuse for UI: Optional—render historical price chart for symbol detail view
   - Status: Can be reused; requires data in OHLC format (not directly from analytics endpoints)

2. **`save_plotly_chart(df, symbol, output_dir)`**
   - Purpose: Render interactive Plotly chart with indicators
   - Reuse for UI: Optional—render historical indicators alongside candlestick
   - Status: Can be reused; requires preprocessed indicator data

**Charting Reuse for Analytics Panels:**

| Panel | Chart Type | Reuse Function | Data Source |
|---|---|---|---|
| Signals | Table (no chart) | — | /analytics/signal-summary rows |
| Rankings | Score breakdown bar chart | Custom (not in visualization/charts.py) | /analytics/bluechip-ranking rows → score_breakdown |
| Backtest | Portfolio return line chart, drawdown chart | Custom (not in visualization/charts.py) | /analytics/backtest-summary → portfolio_metrics |
| Observability | Metadata text | — | /metrics |

**Conclusion for UI2-T2 (Charting Reuse):**
- Existing `visualization/charts.py` functions are for historical OHLC/indicator rendering
- Analytics panels do NOT require complex charting; can use native UI charting (e.g., Chart.js, D3, Plotly.js)
- Score breakdown and backtest metrics can be rendered via client-side charting libraries without backend duplication

---

## Smoke Validation Tests (UI2-T3)

All endpoints are validated with representative query parameters and field assertions.

### Test 1: Signal Summary Endpoint

```bash
curl -X GET "http://localhost:8000/analytics/signal-summary?top_n=10&sector_relative=false" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected:**
- HTTP 200
- Response fields: `top_n`, `sector_relative`, `execution_id`, `rows`
- Each row has at minimum: `symbol`, `signal`, `confidence`

### Test 2: Blue-Chip Ranking Endpoint

```bash
curl -X GET "http://localhost:8000/analytics/bluechip-ranking?top_n=10&sector_relative=false" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected:**
- HTTP 200
- Response fields: `top_n`, `sector_relative`, `execution_id`, `rows`
- Each row has at minimum: `symbol`, `sector`, `bluechip_score`, `score_breakdown`

### Test 3: Backtest Summary Endpoint

```bash
curl -X GET "http://localhost:8000/analytics/backtest-summary?lookback_days=252&rebalance=monthly&sector_relative=false" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected:**
- HTTP 200
- Response fields: `top_n`, `lookback_days`, `rebalance`, `sector_relative`, `execution_id`, `summary`, `historical_validation`, `portfolio_metrics`
- `portfolio_metrics` includes: `cagr`, `max_drawdown`, `sharpe_ratio`, `total_return`

### Test 4: Health Endpoint

```bash
curl -X GET "http://localhost:8000/health" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected:**
- HTTP 200
- Response fields: `ok`, `marketStatus`

### Test 5: Metrics Endpoint

```bash
curl -X GET "http://localhost:8000/metrics" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected:**
- HTTP 200
- Response fields: `request_count`, `error_count`, `execution_trace_counts`, `last_execution_id_by_endpoint`

### Test 6: Error Handling (Invalid Parameter)

```bash
curl -X GET "http://localhost:8000/analytics/signal-summary?top_n=invalid" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected:**
- HTTP 422 (validation error)
- Response contains ApiErrorResponse with error details

---

## UI2 Task Completion Summary

| Task | Status | Details |
|---|---|---|
| UI2-T1: Map each UI view to API response | Done | 4 panels mapped to 5 endpoints with field definitions |
| UI2-T2: Reuse charting and reporting outputs | Done | Documented charting capabilities; native UI charting recommended for analytics panels |
| UI2-T3: Add smoke validation for dashboard flows | Done | 6 curl-based smoke tests covering all endpoints and error handling |

---

## UI2 Implementation Readiness

✅ **All UI2 tasks complete:**
- Endpoint-to-view mapping documented with field transformations
- Data freshness strategy defined (HTTP cache + manual refresh)
- Charting reuse options evaluated (existing functions suitable for OHLC; new functions recommended for analytics)
- Smoke tests provided for validation before UI deployment
- Error handling patterns documented (ApiErrorResponse display)

✅ **Ready for Frontend Implementation:**
1. Clone endpoint-to-view mapping for component data binding
2. Use field formatting rules for number/text display
3. Integrate smoke test queries into UI E2E tests
4. Deploy UI with API contract validation (e.g., TypeScript interfaces matching ApiModels)

---

## References

- Execution-Plan.md: UI2 milestone definition
- UI1_Dashboard_Scope.md: Dashboard panel definitions
- api-contracts.md: Complete API contract specification
- api/models.py: Response model implementations
- visualization/charts.py: Existing charting functions
