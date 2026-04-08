"""Tests for DataFetchCoordinator fallback and refresh behavior."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from nepse_api.coordinator import DataFetchCoordinator


class _RemoteStub:
    """Remote provider stub with call counters."""

    def __init__(
        self,
        live_payload: Any = None,
        securities_payload: Any = None,
        history_payload: Any = None,
    ) -> None:
        self.live_payload = [] if live_payload is None else live_payload
        self.securities_payload = [] if securities_payload is None else securities_payload
        self.history_payload = [] if history_payload is None else history_payload
        self.live_calls = 0
        self.security_calls = 0
        self.history_calls = 0

    def get_live_market_raw(self) -> Any:
        self.live_calls += 1
        return self.live_payload

    def get_security_list_raw(self) -> Any:
        self.security_calls += 1
        return self.securities_payload

    def get_company_history_raw(self, symbol: str, start: date, end: date) -> Any:
        del symbol, start, end
        self.history_calls += 1
        return self.history_payload


class _SnapshotRepoStub:
    """Snapshot repository stub."""

    def __init__(self, persisted: pd.DataFrame | None = None) -> None:
        self.persisted = persisted
        self.saved: list[pd.DataFrame] = []
        self.load_calls = 0

    def load_latest(self) -> pd.DataFrame | None:
        self.load_calls += 1
        if self.persisted is None:
            return None
        return self.persisted.copy()

    def save(self, snapshot_df: pd.DataFrame) -> None:
        self.saved.append(snapshot_df.copy())


class _HistoryRepoStub:
    """Historical repository stub."""

    def __init__(self, stored: dict[str, pd.DataFrame] | None = None) -> None:
        self.stored = {} if stored is None else {k: v.copy() for k, v in stored.items()}
        self.load_calls = 0
        self.save_calls = 0

    def load_many(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        self.load_calls += 1
        return {symbol: self.stored[symbol].copy() for symbol in symbols if symbol in self.stored}

    def save_one(self, symbol: str, history_df: pd.DataFrame) -> None:
        self.save_calls += 1
        self.stored[symbol] = history_df.copy()


class _SnapshotNormalizerStub:
    """Snapshot normalizer stub converting payload rows into DataFrame."""

    def normalize_live_market(self, payload: Any) -> pd.DataFrame:
        rows = payload if isinstance(payload, list) else []
        return pd.DataFrame(rows)


class _HistoryNormalizerStub:
    """History normalizer stub converting payload rows into DataFrame."""

    def normalize_history(self, payload: Any, symbol: str) -> pd.DataFrame:
        rows = payload if isinstance(payload, list) else []
        frame = pd.DataFrame(rows)
        if not frame.empty and "symbol" not in frame.columns:
            frame["symbol"] = symbol
        return frame


def _build_coordinator(
    remote: _RemoteStub,
    snapshot_repo: _SnapshotRepoStub,
    history_repo: _HistoryRepoStub,
) -> DataFetchCoordinator:
    return DataFetchCoordinator(
        remote=remote,
        snapshot_repo=snapshot_repo,
        history_repo=history_repo,
        snapshot_normalizer=_SnapshotNormalizerStub(),
        history_normalizer=_HistoryNormalizerStub(),
    )


def test_market_snapshot_uses_persisted_fallback_before_security_master() -> None:
    """Coordinator should use persisted snapshot before security master fallback."""
    persisted = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "close": 101.0,
                "data_source": "persisted_snapshot",
            }
        ]
    )
    remote = _RemoteStub(
        live_payload=[],
        securities_payload=[{"symbol": "BBB"}],
    )
    snapshot_repo = _SnapshotRepoStub(persisted=persisted)
    history_repo = _HistoryRepoStub()
    coordinator = _build_coordinator(remote, snapshot_repo, history_repo)

    snapshot = coordinator.get_market_snapshot(force_refresh=False)

    assert len(snapshot) == 1
    assert snapshot.iloc[0]["symbol"] == "AAA"
    assert snapshot_repo.load_calls == 1
    assert remote.security_calls == 0


def test_market_snapshot_force_refresh_skips_persisted_and_uses_security_master() -> None:
    """Force refresh should skip persisted snapshot fallback path."""
    persisted = pd.DataFrame([{"symbol": "AAA", "close": 101.0}])
    remote = _RemoteStub(
        live_payload=[],
        securities_payload=[{"symbol": "CCC", "businessSectorName": "Hydro"}],
    )
    snapshot_repo = _SnapshotRepoStub(persisted=persisted)
    history_repo = _HistoryRepoStub()
    coordinator = _build_coordinator(remote, snapshot_repo, history_repo)

    snapshot = coordinator.get_market_snapshot(force_refresh=True)

    assert len(snapshot) == 1
    assert snapshot.iloc[0]["symbol"] == "CCC"
    assert snapshot.iloc[0]["data_source"] == "security_master_fallback"
    assert snapshot_repo.load_calls == 0
    assert remote.security_calls == 1


def test_get_historical_uses_disk_cache_when_not_force_refresh() -> None:
    """Historical reads should use disk cache when refresh is not forced."""
    cached_history = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-01-01"), "close": 100.0, "symbol": "AAA"},
            {"date": pd.Timestamp("2026-01-02"), "close": 101.0, "symbol": "AAA"},
        ]
    )
    remote = _RemoteStub(history_payload=[{"date": "2026-01-03", "close": 102.0}])
    snapshot_repo = _SnapshotRepoStub()
    history_repo = _HistoryRepoStub(stored={"AAA": cached_history})
    coordinator = _build_coordinator(remote, snapshot_repo, history_repo)

    history = coordinator.get_historical(symbol="AAA", start=None, end=None, force_refresh=False)

    assert len(history) == 2
    assert remote.history_calls == 0
    assert history_repo.save_calls == 0


def test_get_historical_force_refresh_fetches_remote_and_persists() -> None:
    """Forced historical reads should bypass disk cache and persist fresh payload."""
    cached_history = pd.DataFrame([{"date": pd.Timestamp("2026-01-01"), "close": 100.0, "symbol": "AAA"}])
    remote = _RemoteStub(
        history_payload=[
            {"date": pd.Timestamp("2026-02-01"), "close": 110.0},
            {"date": pd.Timestamp("2026-02-02"), "close": 111.0},
        ]
    )
    snapshot_repo = _SnapshotRepoStub()
    history_repo = _HistoryRepoStub(stored={"AAA": cached_history})
    coordinator = _build_coordinator(remote, snapshot_repo, history_repo)

    history = coordinator.get_historical(symbol="AAA", start=None, end=None, force_refresh=True)

    assert len(history) == 2
    assert remote.history_calls == 1
    assert history_repo.save_calls == 1
    assert float(history.iloc[-1]["close"]) == 111.0
