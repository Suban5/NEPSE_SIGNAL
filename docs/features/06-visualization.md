# Feature 06: Visualization

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: visualization/charts.py, tests/test_visualization_charts.py
Validation Method: Code + Tests

## Purpose

Generate chart artifacts from technical OHLC data.

## Verified APIs

- save_mplfinance_chart(df, symbol, output_dir) -> pathlib.Path | None
- save_plotly_chart(df, symbol, output_dir) -> pathlib.Path | None

## Output Naming

- <symbol>_candlestick.png
- <symbol>_candlestick.html

## Example

```python
from visualization.charts import save_mplfinance_chart, save_plotly_chart

save_mplfinance_chart(technical_df, symbol="NABIL", output_dir="output/charts")
save_plotly_chart(technical_df, symbol="NABIL", output_dir="output/charts")
```

## Notes

- If mplfinance or plotly is unavailable, function returns None and logs a warning.
