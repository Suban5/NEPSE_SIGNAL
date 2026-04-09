"""Unit tests for metrics component helpers."""

from __future__ import annotations

from ui.components.metrics import build_execution_id_correlations


def test_build_execution_id_correlations_marks_match_and_mismatch() -> None:
    local_ids = {
        "/analytics/signal-summary": "exec-1",
        "/analytics/backtest-summary": "exec-2",
    }
    metrics_payload = {
        "last_execution_id_by_endpoint": {
            "/analytics/signal-summary": "exec-1",
            "/analytics/backtest-summary": "exec-9",
            "/analytics/bluechip-ranking": "exec-3",
        }
    }

    rows = build_execution_id_correlations(local_execution_ids=local_ids, metrics_payload=metrics_payload)
    row_map = {row["endpoint"]: row for row in rows}

    assert row_map["/analytics/signal-summary"]["match"] == "yes"
    assert row_map["/analytics/backtest-summary"]["match"] == "no"
    assert row_map["/analytics/bluechip-ranking"]["ui_execution_id"] == "n/a"


def test_build_execution_id_correlations_handles_missing_metrics_map() -> None:
    rows = build_execution_id_correlations(
        local_execution_ids={"/analytics/opportunities": "exec-7"},
        metrics_payload={},
    )

    assert len(rows) == 1
    assert rows[0]["endpoint"] == "/analytics/opportunities"
    assert rows[0]["metrics_execution_id"] == "n/a"
    assert rows[0]["match"] == "no"
