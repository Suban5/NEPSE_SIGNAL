# Workflow Reference

Metadata:
Owner: suban
Last Reviewed: 2026-04-08
Source of Truth: workflows/market_scan.py, workflows/market_backtest.py, workflows/symbol_analysis.py, workflows/common.py
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

## Symbol Analysis Workflow

Entry: run_symbol_analysis_workflow

Inputs:
- SymbolAnalysisDependencies
- symbol
- start_date
- end_date

Outputs:
- SymbolAnalysisContext including signal and backtest result

## Shared Utilities

workflows/common.py provides:
- market snapshot and universe fetch helpers
- fundamentals map builder
- concurrent signal-row computation
- ranking cache helper
- output persistence and benchmark writing

Fetch helper behavior:

- force_refresh=false: memory cache -> live API -> persisted latest snapshot -> security master fallback
- force_refresh=true: bypass memory/persisted read paths and force upstream refresh where available

Coordinator methods used by workflows:

- get_market_snapshot(force_refresh=...)
- get_universe_with_history(lookback_years=..., force_refresh=...)
- get_historical(symbol=..., start=..., end=..., force_refresh=...)

Snapshot data source semantics:

- live_market: row values come directly from current live market payload
- historical_fallback: live row unavailable; OHLCV hydrated from latest local historical row
- security_master_fallback: no live and no local historical row available; metadata-only fallback
