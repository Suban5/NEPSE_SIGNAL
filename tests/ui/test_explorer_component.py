"""Unit tests for API Explorer helpers."""

from __future__ import annotations

import pytest

from ui.components.explorer import render_path_template


def test_render_path_template_success() -> None:
    rendered = render_path_template("/companies/{symbol}/history", {"symbol": "NABIL"})
    assert rendered == "/companies/NABIL/history"


def test_render_path_template_missing_value_raises() -> None:
    with pytest.raises(ValueError):
        render_path_template("/companies/{symbol}/history", {})
