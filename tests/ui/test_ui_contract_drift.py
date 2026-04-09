"""Contract drift checks for UI-consumed endpoint definitions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api import app as api_app_module


client = TestClient(api_app_module.app)


def _param_schema(openapi: dict, path: str, name: str) -> dict:
    parameters = openapi["paths"][path]["get"].get("parameters", [])
    for item in parameters:
        if item.get("name") == name:
            return item.get("schema", {})
    raise AssertionError(f"parameter not found: {name} for {path}")


def test_ui_contract_drift_core_paths_exist() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi = response.json()

    required_paths = [
        "/health",
        "/metrics",
        "/contracts",
        "/analytics/signal-summary",
        "/analytics/bluechip-ranking",
        "/analytics/opportunities",
        "/analytics/backtest-summary",
    ]
    for path in required_paths:
        assert path in openapi["paths"]


def test_ui_contract_drift_analytics_constraints_match_ui_rules() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi = response.json()

    for analytics_path in [
        "/analytics/signal-summary",
        "/analytics/bluechip-ranking",
        "/analytics/opportunities",
        "/analytics/backtest-summary",
    ]:
        top_n_schema = _param_schema(openapi, analytics_path, "top_n")
        assert int(top_n_schema["minimum"]) == 1
        assert int(top_n_schema["maximum"]) == 200

    lookback_schema = _param_schema(openapi, "/analytics/backtest-summary", "lookback_days")
    assert int(lookback_schema["minimum"]) == 1
    assert int(lookback_schema["maximum"]) == 2000

    rebalance_schema = _param_schema(openapi, "/analytics/backtest-summary", "rebalance")
    assert rebalance_schema["pattern"] == "^(static|weekly|monthly)$"
