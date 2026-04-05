# Feature 04: Ranking and Blue-Chip Scoring

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: bluechip/detector.py, ranking/opportunity_ranker.py, ranking/stock_ranker.py, tests/test_bluechip_detector.py
Validation Method: Code + Tests

## Purpose

Produce blue-chip ranking and opportunity ranking views for market outputs.

## Blue-Chip Detector APIs

- build_feature_table(market_snapshot, historical_data, fundamentals=None)
- score_bluechips(features)
- get_feature_importance()
- build_scoring_report(scored)

## Opportunity Ranking API

- rank_opportunities(signal_df)

## Ranked View API

- build_ranked_views(bluechip_df, signal_df)

## Example

```python
from bluechip.detector import BlueChipDetector

scored = BlueChipDetector().score_bluechips(features_df)
```

## Output View Buckets

- top_bluechips
- best_buy_signals
- strong_momentum
- high_risk_weak
