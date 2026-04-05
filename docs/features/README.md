# Feature Documentation Index

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: docs/features/*.md, workflows/*.py, api/app.py
Validation Method: Code + Tests

## Feature Guides

- [01 Data Fetching](01-data-fetching.md)
- [02 Market Scanning](02-market-scanning.md)
- [03 Signal Generation](03-signal-generation.md)
- [04 Ranking and Blue-Chip](04-ranking.md)
- [05 Backtesting](05-backtesting.md)
- [06 Visualization](06-visualization.md)
- [07 HTTP API](07-api-server.md)

## End-to-End Flow

1. Fetch and normalize market data
2. Filter market universe
3. Compute blue-chip scores
4. Generate technical signals
5. Rank opportunities
6. Run backtests
7. Publish via API or output files

For orchestration-level details see [../workflows.md](../workflows.md).
