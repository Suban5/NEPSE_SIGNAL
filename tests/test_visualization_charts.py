"""Tests for chart rendering helpers with optional dependency mocking."""

from __future__ import annotations

import sys
import types
from pathlib import Path
import builtins

import pandas as pd

from visualization.charts import save_mplfinance_chart, save_plotly_chart


def _sample_chart_df() -> pd.DataFrame:
    """Build sample OHLCV frame with indicators."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=5, freq="D"),
            "open": [100, 101, 102, 103, 104],
            "high": [101, 102, 103, 104, 105],
            "low": [99, 100, 101, 102, 103],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [1000, 1100, 1200, 1300, 1400],
            "sma20": [100, 100, 101, 102, 103],
            "sma50": [99, 100, 100, 101, 102],
            "sma200": [95, 95, 96, 96, 97],
            "ema20": [100, 100.5, 101, 102, 103],
        }
    )


def test_save_mplfinance_chart_returns_none_when_dependency_missing(monkeypatch, tmp_path: Path) -> None:
    """When mplfinance is unavailable, helper should return None."""
    original_import = builtins.__import__

    def _mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mplfinance":
            raise ImportError("mocked missing mplfinance")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _mock_import)

    result = save_mplfinance_chart(_sample_chart_df(), symbol="NABIL", output_dir=str(tmp_path))

    assert result is None


def test_save_plotly_chart_returns_none_when_dependency_missing(monkeypatch, tmp_path: Path) -> None:
    """When plotly is unavailable, helper should return None."""
    original_import = builtins.__import__

    def _mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "plotly.graph_objects":
            raise ImportError("mocked missing plotly")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _mock_import)

    result = save_plotly_chart(_sample_chart_df(), symbol="NABIL", output_dir=str(tmp_path))

    assert result is None


def test_save_mplfinance_chart_saves_expected_path(monkeypatch, tmp_path: Path) -> None:
    """mplfinance path should be returned and plotting API invoked."""
    calls: dict[str, object] = {}
    addplot_count = 0

    def _make_addplot(values, panel=0):
        nonlocal addplot_count
        addplot_count += 1
        return {"values": values, "panel": panel}

    def _plot(*args, **kwargs):
        calls["savefig"] = kwargs.get("savefig")

    fake_mpf = types.SimpleNamespace(make_addplot=_make_addplot, plot=_plot)
    monkeypatch.setitem(sys.modules, "mplfinance", fake_mpf)

    result = save_mplfinance_chart(_sample_chart_df(), symbol="NABIL", output_dir=str(tmp_path))

    assert result == tmp_path / "NABIL_candlestick.png"
    assert calls.get("savefig") == str(tmp_path / "NABIL_candlestick.png")
    assert addplot_count >= 1


def test_save_plotly_chart_saves_expected_path(monkeypatch, tmp_path: Path) -> None:
    """plotly path should be returned and write_html should be called."""
    calls: dict[str, object] = {}
    scatter_count = 0

    class _FakeFigure:
        def __init__(self, data=None):
            calls["init_data"] = data

        def add_scatter(self, **kwargs):
            nonlocal scatter_count
            scatter_count += 1

        def update_layout(self, **kwargs):
            calls["layout"] = kwargs

        def write_html(self, path: str, include_plotlyjs: str):
            calls["path"] = path
            calls["include_plotlyjs"] = include_plotlyjs

    class _FakeCandlestick:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_go = types.SimpleNamespace(Figure=_FakeFigure, Candlestick=_FakeCandlestick)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", fake_go)

    result = save_plotly_chart(_sample_chart_df(), symbol="NABIL", output_dir=str(tmp_path))

    assert result == tmp_path / "NABIL_candlestick.html"
    assert calls.get("path") == str(tmp_path / "NABIL_candlestick.html")
    assert calls.get("include_plotlyjs") == "cdn"
    assert scatter_count >= 1
