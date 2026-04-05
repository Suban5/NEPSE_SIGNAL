# Blue-Chip Scoring

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: bluechip/detector.py, config/settings.py, tests/test_bluechip_detector.py
Validation Method: Code + Tests

## Model Components

BlueChipDetector computes these normalized component scores:

- market_cap_score
- volume_score (0.7 avg_volume + 0.3 avg_turnover)
- stability_score (inverse normalized volatility)
- trend_score (normalized CAGR)
- fundamental_score (normalized fundamental_strength)

## Default Weights

BlueChipWeights defaults:

- market_cap: 0.30
- volume: 0.20
- stability: 0.20
- trend: 0.20
- fundamental: 0.10

Weights are validated to sum to 1.0.

## Normalization

BlueChipScoringConfig supports:

- normalization_mode: robust or minmax
- robust mode uses configured lower/upper quantile clipping

## Sector-Relative Blend

When sector_relative is enabled:

- base_bluechip_score is scaled inside each sector
- final score blends global and sector score using sector_blend

## Explainability

build_scoring_report provides:

- feature_importance
- symbol_breakdown
- sector_summary

## Validation

Key behavior tests:

- ranking order and bounds
- sector-relative score path
- scoring report output
- weight validation
