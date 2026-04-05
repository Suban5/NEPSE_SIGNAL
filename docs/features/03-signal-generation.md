# Feature 03: Signal Generation

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: analysis/signal_engine.py, signals/signal_engine.py, tests/test_signal_engine.py
Validation Method: Code + Tests

## Purpose

Generate BUY/SELL/HOLD decisions and confidence using indicators, pattern detections, and blue-chip score.

## Verified APIs

- generate_signal(symbol, df, patterns, bluechip_score) -> SignalResult
- build_trade_signal(symbol, technical_df, pattern_results, bluechip_score) -> TradeSignal

## Required Columns for generate_signal

- close
- sma50
- volume
- volume_sma20

## Example

```python
from analysis.signal_engine import generate_signal

result = generate_signal(
    symbol="NABIL",
    df=technical_df,
    patterns={"hammer": True, "bullish_engulfing": False},
    bluechip_score=0.82,
)
```

## Decision Thresholds

- BUY when buy_score >= 0.5
- SELL when sell_score >= 0.67
- otherwise HOLD
