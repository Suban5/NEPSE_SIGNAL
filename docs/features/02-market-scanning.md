# Feature 02: Market Scanning

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: market/market_scanner.py, market/universe_builder.py, workflows/market_scan.py, tests/test_workflows.py
Validation Method: Code + Tests

## Purpose

Market scanning filters symbols to a valid universe and runs analysis pipeline orchestration through workflow modules.

## Verified Scanner API

MarketScanner constructor has optional universe_builder only.

```python
from market.market_scanner import MarketScanner

scanner = MarketScanner()
symbols, filtered_history = scanner.scan(snapshot=snapshot_df, historical_universe=history_map)
```

## Recommended Orchestration API

Use workflow entrypoint for full scan and exports:

```python
from pathlib import Path
from workflows.market_scan import MarketScanDependencies, run_market_scan_workflow

context = run_market_scan_workflow(
    dependencies=MarketScanDependencies(...),
    output_dir=Path("output"),
    top_n=20,
    plot=False,
)
```

## Output Artifacts

- bluechip_ranked.csv
- signal_summary.csv
- best_buy_signals.csv
- top_buy_signals.csv
- strong_momentum.csv
- high_risk_weak.csv
- scan_benchmark.json
