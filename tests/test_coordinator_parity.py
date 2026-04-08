"""End-to-end parity tests between CLI, workflow, and API coordinator usage."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
import json

import pandas as pd
import pytest

from nepse_api.coordinator import DataFetchCoordinator
from nepse_api.factory import build_data_fetch_coordinator
from workflows.common import fetch_market_snapshot, fetch_historical_universe, build_fundamentals_map
from api.service import NepseApiService


def _build_mock_snapshot() -> pd.DataFrame:
    """Build consistent mock snapshot for parity testing."""
    return pd.DataFrame(
        {
            "symbol": ["NABIL", "SCB", "SBL"],
            "sector": ["Banking", "Banking", "Banking"],
            "market_cap": [1_000_000_000, 900_000_000, 800_000_000],
            "open": [100.0, 110.0, 120.0],
            "high": [105.0, 115.0, 125.0],
            "low": [95.0, 105.0, 115.0],
            "close": [102.0, 112.0, 122.0],
            "volume": [10_000, 12_000, 8_000],
            "turnover": [1_000_000, 1_200_000, 800_000],
            "data_source": ["live_market", "live_market", "live_market"],
        }
    )


def _build_mock_history(symbol: str) -> pd.DataFrame:
    """Build consistent mock history for parity testing."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=220, freq="D"),
            "symbol": symbol,
            "open": [100.0 + i * 0.1 for i in range(220)],
            "high": [101.0 + i * 0.1 for i in range(220)],
            "low": [99.0 + i * 0.1 for i in range(220)],
            "close": [100.5 + i * 0.1 for i in range(220)],
            "volume": [10_000] * 220,
            "turnover": [1_000_000] * 220,
        }
    )


class _CoordinatorStub:
    """Stub coordinator that simulates fetch behavior for parity tests."""

    def __init__(self, live_available: bool = True, force_persisted: bool = False) -> None:
        self.live_available = live_available
        self.force_persisted = force_persisted
        self.get_market_snapshot_calls = 0
        self.get_historical_calls = 0
        self.get_universe_calls = 0

    def get_market_snapshot(self, force_refresh: bool = False) -> pd.DataFrame:
        """Simulate coordinator snapshot fetch."""
        self.get_market_snapshot_calls += 1

        if self.force_persisted and force_refresh:
            # Force refresh still returns live data when available
            if self.live_available:
                return _build_mock_snapshot()
            return pd.DataFrame()

        if self.live_available:
            return _build_mock_snapshot()
        return pd.DataFrame()

    def get_historical(
        self,
        symbol: str,
        start: date | None,
        end: date | None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Simulate coordinator historical fetch."""
        self.get_historical_calls += 1
        return _build_mock_history(symbol)

    def get_universe_with_history(self, lookback_years: int = 5, force_refresh: bool = False) -> dict[str, pd.DataFrame]:
        """Simulate coordinator universe fetch."""
        self.get_universe_calls += 1
        return {
            "NABIL": _build_mock_history("NABIL"),
            "SCB": _build_mock_history("SCB"),
            "SBL": _build_mock_history("SBL"),
        }

    def fetch_company_fundamentals(self, symbol: str) -> dict[str, Any]:
        """Simulate fundamentals fetch (legacy method for compatibility)."""
        return {
            "epsGrowth": 10.0,
            "salesGrowth": 8.0,
            "dividendYield": 3.0,
        }

    def normalize_fundamentals(self, payload: dict[str, Any]) -> dict[str, float]:
        """Normalize fundamentals (legacy method for compatibility)."""
        return {
            "earnings_growth": payload.get("epsGrowth", 0.0),
            "dividend_stability": payload.get("dividendYield", 0.0),
            "revenue_growth": payload.get("salesGrowth", 0.0),
        }


def test_cli_and_workflow_snapshot_parity() -> None:
    """CLI and workflow paths should fetch identical snapshots via coordinator."""
    coordinator = _CoordinatorStub(live_available=True)

    snapshot_via_workflow = fetch_market_snapshot(coordinator, force_refresh=False)
    snapshot_via_workflow_again = fetch_market_snapshot(coordinator, force_refresh=False)

    assert len(snapshot_via_workflow) == 3
    assert list(snapshot_via_workflow["symbol"]) == ["NABIL", "SCB", "SBL"]
    assert snapshot_via_workflow.equals(snapshot_via_workflow_again)
    assert coordinator.get_market_snapshot_calls == 2


def test_force_refresh_bypasses_cache_in_workflow() -> None:
    """Force refresh should call coordinator fresh for both CLI and workflow."""
    coordinator = _CoordinatorStub(live_available=True)

    # Without force_refresh, should still hit coordinator per call
    snap1 = fetch_market_snapshot(coordinator, force_refresh=False)
    snap2 = fetch_market_snapshot(coordinator, force_refresh=False)

    assert coordinator.get_market_snapshot_calls == 2

    # With force_refresh explicitly requested
    snap3 = fetch_market_snapshot(coordinator, force_refresh=True)
    assert coordinator.get_market_snapshot_calls == 3

    assert snap1.equals(snap2)
    assert snap1.equals(snap3)


def test_workflow_and_api_historical_parity() -> None:
    """Workflow and API paths should fetch identical historical data."""
    coordinator = _CoordinatorStub()

    # Via workflow
    universe = fetch_historical_universe(coordinator, lookback_years=5, force_refresh=False)
    assert len(universe) == 3
    assert "NABIL" in universe
    assert len(universe["NABIL"]) == 220

    # Via coordinator directly (API path)
    nabil_history = coordinator.get_historical(symbol="NABIL", start=None, end=None, force_refresh=False)
    assert len(nabil_history) == 220
    assert nabil_history.equals(universe["NABIL"])


def test_cli_and_api_fundamentals_parity() -> None:
    """CLI and API should use same fundamentals path via coordinator."""
    coordinator = _CoordinatorStub()

    symbols = ["NABIL", "SCB"]

    # Via workflow helper (used by CLI)
    fundamentals_via_workflow = build_fundamentals_map(coordinator, symbols)
    assert len(fundamentals_via_workflow) == 2
    assert fundamentals_via_workflow["NABIL"]["earnings_growth"] == 10.0

    # Via coordinator directly
    fundamentals_direct = {}
    for symbol in symbols:
        payload = coordinator.fetch_company_fundamentals(symbol)
        fundamentals_direct[symbol] = coordinator.normalize_fundamentals(payload)

    assert fundamentals_via_workflow == fundamentals_direct


def test_force_refresh_consistency_across_paths() -> None:
    """Force refresh behavior must be identical: live → persisted → fallback."""
    # Scenario 1: Live market available
    coordinator_live = _CoordinatorStub(live_available=True)
    snap_live_refresh_false = fetch_market_snapshot(coordinator_live, force_refresh=False)
    snap_live_refresh_true = fetch_market_snapshot(coordinator_live, force_refresh=True)

    assert snap_live_refresh_false.equals(snap_live_refresh_true)

    # Scenario 2: Live market unavailable should raise error per workflow validation
    coordinator_fallback = _CoordinatorStub(live_available=False, force_persisted=True)
    with pytest.raises(RuntimeError, match="No market snapshot data retrieved"):
        fetch_market_snapshot(coordinator_fallback, force_refresh=False)


def test_coordinator_calls_are_tracked() -> None:
    """Verify coordinator call patterns match expected CLI/workflow/API usage."""
    coordinator = _CoordinatorStub()

    # CLI scan-market path: fetch snapshot, then universe
    fetch_market_snapshot(coordinator)
    fetch_historical_universe(coordinator, lookback_years=5)

    assert coordinator.get_market_snapshot_calls == 1
    assert coordinator.get_universe_calls == 1

    # API analytics path: fetch via coordinator
    coordinator.get_market_snapshot(force_refresh=False)

    assert coordinator.get_market_snapshot_calls == 2


def test_snapshot_contains_data_source_marker() -> None:
    """Snapshot rows should indicate their source (live/persisted/fallback) for observability."""
    coordinator = _CoordinatorStub()

    snapshot = fetch_market_snapshot(coordinator)

    assert "data_source" in snapshot.columns
    assert (snapshot["data_source"] == "live_market").all()


def test_historical_empty_handling_consistency() -> None:
    """Empty historical responses should be rejected per workflow validation contract."""
    class _EmptyCoordinator(_CoordinatorStub):
        def get_historical(self, symbol: str, start: date | None, end: date | None, force_refresh: bool = False) -> pd.DataFrame:
            return pd.DataFrame()

        def get_universe_with_history(self, lookback_years: int = 5, force_refresh: bool = False) -> dict[str, pd.DataFrame]:
            return {}

    coordinator = _EmptyCoordinator()

    # Workflow should reject empty universe per validation
    with pytest.raises(RuntimeError, match="No historical data found"):
        fetch_historical_universe(coordinator, lookback_years=5)

    # Coordinator itself can return empty (validation is workflow concern)
    history = coordinator.get_historical(symbol="NONEXISTENT", start=None, end=None)
    assert history.empty
