"""UI smoke checks for core API endpoints used by Streamlit dashboard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api import app as api_app_module


client = TestClient(api_app_module.app)


def test_ui_smoke_health_and_contracts(monkeypatch) -> None:
    """Health and contracts endpoints should return expected minimal fields."""
    monkeypatch.setattr(api_app_module.service, "health", lambda: {"ok": True, "marketStatus": {"isOpen": True}})

    health_response = client.get("/health")
    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert "ok" in health_payload
    assert "marketStatus" in health_payload

    contracts_response = client.get("/contracts", headers={"X-API-Version": "v2"})
    assert contracts_response.status_code == 200
    contracts_payload = contracts_response.json()
    assert "default_version" in contracts_payload
    assert "negotiated_version" in contracts_payload
    assert "supported_versions" in contracts_payload


def test_ui_smoke_analytics_endpoints(monkeypatch) -> None:
    """Analytics endpoints should expose expected UI-consumed top-level fields."""

    base_rows_payload = {
        "top_n": 20,
        "sector_relative": False,
        "execution_id": "exec-rows-1",
        "summary": {"workflow": "market_scan", "execution_id": "exec-rows-1"},
        "rows": [{"symbol": "NABIL", "signal": "BUY", "confidence": 0.9}],
    }

    monkeypatch.setattr(api_app_module.service, "analytics_signal_summary", lambda top_n, sector_relative: {**base_rows_payload, "top_n": top_n, "sector_relative": sector_relative})
    monkeypatch.setattr(api_app_module.service, "analytics_bluechip_ranking", lambda top_n, sector_relative: {**base_rows_payload, "top_n": top_n, "sector_relative": sector_relative})
    monkeypatch.setattr(api_app_module.service, "analytics_opportunities", lambda top_n, sector_relative: {**base_rows_payload, "top_n": top_n, "sector_relative": sector_relative})

    monkeypatch.setattr(
        api_app_module.service,
        "analytics_backtest_summary",
        lambda top_n, lookback_days, rebalance, sector_relative: {
            "top_n": top_n,
            "lookback_days": lookback_days,
            "rebalance": rebalance,
            "sector_relative": sector_relative,
            "execution_id": "exec-backtest-1",
            "summary": {"workflow": "market_backtest", "execution_id": "exec-backtest-1"},
            "historical_validation": {
                "validated_symbols": 1,
                "sufficient_symbols": 1,
                "insufficient_symbols": 0,
                "required_lookback_days": lookback_days,
                "sufficient_history_symbols": ["NABIL"],
                "insufficient_history_symbols": [],
                "missing_history_symbols": [],
                "symbol_row_counts": {"NABIL": 300},
            },
            "portfolio_metrics": {
                "symbols_count": 1,
                "selected_buy_symbols": ["NABIL"],
                "backtested_symbols": ["NABIL"],
                "cagr": 0.1,
                "max_drawdown": -0.2,
                "sharpe_ratio": 1.1,
                "total_return": 0.2,
                "lookback_days": lookback_days,
                "rebalance": rebalance,
            },
        },
    )

    signal_response = client.get("/analytics/signal-summary", params={"top_n": 10, "sector_relative": False})
    assert signal_response.status_code == 200
    signal_payload = signal_response.json()
    assert set(["top_n", "sector_relative", "execution_id", "summary", "rows"]).issubset(signal_payload.keys())

    ranking_response = client.get("/analytics/bluechip-ranking", params={"top_n": 10, "sector_relative": False})
    assert ranking_response.status_code == 200
    ranking_payload = ranking_response.json()
    assert set(["top_n", "sector_relative", "execution_id", "summary", "rows"]).issubset(ranking_payload.keys())

    opportunities_response = client.get("/analytics/opportunities", params={"top_n": 10, "sector_relative": False})
    assert opportunities_response.status_code == 200
    opportunities_payload = opportunities_response.json()
    assert set(["top_n", "sector_relative", "execution_id", "summary", "rows"]).issubset(opportunities_payload.keys())

    backtest_response = client.get(
        "/analytics/backtest-summary",
        params={"top_n": 10, "lookback_days": 252, "rebalance": "monthly", "sector_relative": False},
    )
    assert backtest_response.status_code == 200
    backtest_payload = backtest_response.json()
    assert set(
        [
            "top_n",
            "lookback_days",
            "rebalance",
            "sector_relative",
            "execution_id",
            "summary",
            "historical_validation",
            "portfolio_metrics",
        ]
    ).issubset(backtest_payload.keys())
