# Workflow Reference

Metadata:
Owner: suban
Last Reviewed: 2026-04-09
Source of Truth: workflows/market_scan.py, workflows/market_backtest.py, workflows/symbol_analysis.py, workflows/common.py, workflows/errors.py
Validation Method: Code + Tests

## Workflow Modules

- workflows/market_scan.py
- workflows/market_backtest.py
- workflows/symbol_analysis.py
- workflows/common.py

## Market Scan Workflow

Entry: run_market_scan_workflow

Inputs:
- MarketScanDependencies
- output_dir
- top_n
- plot
- force_refresh (default false)

Outputs:
- MarketScanContext
- CSV artifacts and scan_benchmark.json

Standard summary contract:
- `MarketScanContext.to_summary()` returns the canonical workflow summary used by CLI logs, benchmark payloads, and API analytics responses
- `scan_benchmark.json` includes the same summary under a `summary` key

Observability:
- `MarketScanContext.execution_id` provides per-run correlation ID
- `scan_benchmark.json` includes the same `execution_id`
- structured events are logged with workflow, execution_id, and event fields

## Market Backtest Workflow

Entry: run_market_backtest_workflow

Inputs:
- MarketBacktestDependencies
- output_dir
- top_n
- lookback_days
- rebalance
- force_refresh (default false)

Outputs:
- MarketBacktestContext
- portfolio_backtest.json, portfolio_signal_set.csv, backtest_benchmark.json

Standard summary contract:
- `MarketBacktestContext.to_summary()` returns the canonical workflow summary used by CLI logs, benchmark payloads, and API analytics responses
- `backtest_benchmark.json` includes the same summary under a `summary` key
- market backtest summary includes portfolio metric fields (`portfolio_cagr`, `portfolio_max_drawdown`, `portfolio_sharpe_ratio`, `portfolio_total_return`) and historical sufficiency counters

Historical validation contract:
- workflow validates BUY symbols against required lookback window before backtest execution
- symbols with fewer than 2 valid close points in the requested window are excluded from the portfolio run
- `MarketBacktestContext.historical_validation` stores symbol-level row counts and sufficiency lists
- `backtest_benchmark.json` includes the same payload under `historical_validation`
- workflow raises `WorkflowDataError` at `stage=backtest` if no BUY symbols have sufficient history

Observability:
- `MarketBacktestContext.execution_id` provides per-run correlation ID
- `backtest_benchmark.json` includes the same `execution_id`
- structured events are logged with workflow, execution_id, and event fields

## Symbol Analysis Workflow

Entry: run_symbol_analysis_workflow

Inputs:
- SymbolAnalysisDependencies
- symbol
- start_date
- end_date

Outputs:
- SymbolAnalysisContext including signal and backtest result

Standard summary contract:
- `SymbolAnalysisContext.to_summary()` returns the canonical execution summary used by CLI output and downstream reporting

Observability:
- `SymbolAnalysisContext.execution_id` provides per-run correlation ID
- structured events are logged with workflow, execution_id, and event fields

## Shared Utilities

workflows/common.py provides:
- market snapshot and universe fetch helpers
- fundamentals map builder
- concurrent signal-row computation
- ranking cache helper
- output persistence and benchmark writing

### Fetch Helper Behavior

force_refresh=false: memory cache -> live API -> persisted latest snapshot -> security master fallback
force_refresh=true: bypass memory/persisted read paths and force upstream refresh where available

### Coordinator Methods Used by Workflows

- get_market_snapshot(force_refresh=...)
- get_universe_with_history(lookback_years=..., force_refresh=...)
- get_historical(symbol=..., start=..., end=..., force_refresh=...)

### Service Layer Caching

The NepseApiService layer caches responses using TTL (time-to-live) caches per endpoint to avoid repeated upstream calls:
- market_status: 30 seconds
- market_summary: 60 seconds
- company lists: 300 seconds
- analytics_scan: 120 seconds

When workflows call coordinator methods that delegate to the service layer, repeated calls within the cache TTL reuse cached payloads. This reduces API load and improves performance for repeated queries at the cost of potential staleness.

### Snapshot Data Source Semantics

- live_market: row values come directly from current live market payload
- historical_fallback: live row unavailable; OHLCV hydrated from latest local historical row
- security_master_fallback: no live and no local historical row available; metadata-only fallback

## Workflow Failure Classification

workflows/errors.py defines a failure classification system used by all workflows and exposed in both CLI logs and API error responses.

### Exception Hierarchy

- WorkflowError (base): workflow stage and category metadata
  - WorkflowValidationError: inputs or validated payloads invalid (HTTP 400)
    - stage: validate
    - category: validation
  - WorkflowDataError: required data missing or incompatible (HTTP 422)
    - stage: fetch, scan
    - category: data
  - WorkflowUpstreamError: upstream fetch or transformation failed (HTTP 502)
    - stage: fetch, fundamentals
    - category: upstream
    - retriable: true
  - WorkflowRankingError: scoring or ranking computation failed (HTTP 500)
    - stage: score, rank, signal, backtest, persist
    - category: ranking

### Classification Semantics

Each WorkflowError instance includes:
- workflow: workflow name (e.g., "market_scan", "market_backtest")
- stage: processing stage (e.g., "validate", "fetch", "fetch", "rank")
- category: failure type classification
- retriable: whether the failure indicates a transient error safe to retry
- status_code: HTTP status code for API error mapping
- message: descriptive error information

Example usage in API responses:
- Validation errors (invalid parameters) -> HTTP 400
- Data errors (missing required datasets) -> HTTP 422
- Upstream errors (API unavailable) -> HTTP 502, retriable=true
- Ranking errors (computation failure) -> HTTP 500

## Service Layer Retry Behavior

api/service.py implements retry logic for transient failures:

### Retryable Exceptions

The following are considered safe to retry:
- TimeoutError, ReadTimeout, ConnectTimeout
- NepseNetworkError
- Exceptions with status_code in {408, 429, 500, 502, 503, 504}

### Non-Retryable Exceptions

- RuntimeError with status_code=401, 403, 404 (auth/permission/notfound errors)
- Validation errors (ValueError, TypeError)
- All WorkflowValidationError and WorkflowDataError instances

### Retry Configuration

Retry behavior is controlled by settings:
- api_retry_attempts: max number of retry attempts (default from config)
- api_retry_backoff_seconds: base backoff duration (multiplied by attempt number)

## Validation Reference

Workflow and service layer contracts are validated by:
- Workflow orchestration tests: tests/test_workflows.py
  - validate workflow summary contracts and execution context
  - validate failure classification for fetch, scan, rank stages
  - validate parameter validation (top_n, lookback_days, rebalance)
- Service layer tests: tests/test_api_service.py
  - validate retry behavior for transient vs. permanent failures
  - validate call caching and response normalization
  - validate analytics payload shared caching
- API integration tests: tests/test_api_app.py
  - validate error mapping (classification metadata exposure)
  - validate timeout handling (504 UPSTREAM_TIMEOUT)
  - validate analytics response contracts with timeout wrapper
