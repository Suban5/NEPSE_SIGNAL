"""Tests for persistent local NEPSE data storage."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from nepse_api.data_persistence import DataPersistence


def _snapshot_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"symbol": "NABIL", "close": 1000.0, "volume": 10000},
            {"symbol": "SBI", "close": 500.0, "volume": 5000},
        ]
    )


def _history_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2024-01-01", "open": 990.0, "high": 1010.0, "low": 980.0, "close": 1000.0, "volume": 1000},
            {"date": "2024-01-02", "open": 1000.0, "high": 1020.0, "low": 995.0, "close": 1010.0, "volume": 1200},
        ]
    )


def test_init_creates_directories(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path / "datasets")

    assert persistence.snapshots_dir.exists()
    assert persistence.historical_dir.exists()


def test_get_snapshot_path_uses_given_date(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    path = persistence._get_snapshot_path(date(2024, 1, 15))

    assert path.name == "market_snapshot_2024-01-15.csv"


def test_get_snapshot_path_defaults_today(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2025, 2, 3)

    import nepse_api.data_persistence as module

    monkeypatch.setattr(module, "date", _FakeDate)
    persistence = DataPersistence(tmp_path)

    path = persistence._get_snapshot_path()

    assert path.name == "market_snapshot_2025-02-03.csv"


def test_get_latest_snapshot_path(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    assert persistence._get_latest_snapshot_path().name == "market_snapshot_latest.csv"


def test_get_historical_path_sanitizes_symbol(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    path = persistence._get_historical_path("nabil/a\\b")

    assert path.name == "NABIL_A_B_history.csv"


def test_save_snapshot_writes_dated_and_latest(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    df = _snapshot_df()

    persistence.save_snapshot(df, date(2024, 1, 10))

    assert (persistence.snapshots_dir / "market_snapshot_2024-01-10.csv").exists()
    assert (persistence.snapshots_dir / "market_snapshot_latest.csv").exists()


def test_save_snapshot_empty_dataframe_skips(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    persistence.save_snapshot(pd.DataFrame(), date(2024, 1, 10))

    assert not (persistence.snapshots_dir / "market_snapshot_2024-01-10.csv").exists()


def test_save_snapshot_raises_on_to_csv_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)
    df = _snapshot_df()

    def _raise(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("write failed")

    monkeypatch.setattr(pd.DataFrame, "to_csv", _raise)

    with pytest.raises(RuntimeError, match="write failed"):
        persistence.save_snapshot(df, date(2024, 1, 10))


def test_load_snapshot_returns_none_when_missing(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    assert persistence.load_snapshot(date(2024, 1, 10)) is None


def test_load_snapshot_reads_existing_file(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    expected = _snapshot_df()
    expected.to_csv(persistence._get_snapshot_path(date(2024, 1, 10)), index=False)

    loaded = persistence.load_snapshot(date(2024, 1, 10))

    assert loaded is not None
    assert list(loaded["symbol"]) == ["NABIL", "SBI"]


def test_load_snapshot_returns_none_on_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)
    persistence.save_snapshot(_snapshot_df(), date(2024, 1, 10))

    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("boom")))

    assert persistence.load_snapshot(date(2024, 1, 10)) is None


def test_load_latest_snapshot_returns_none_when_missing(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    assert persistence.load_latest_snapshot() is None


def test_load_latest_snapshot_reads_file(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    _snapshot_df().to_csv(persistence._get_latest_snapshot_path(), index=False)

    loaded = persistence.load_latest_snapshot()

    assert loaded is not None
    assert len(loaded) == 2


def test_load_latest_snapshot_returns_none_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)
    _snapshot_df().to_csv(persistence._get_latest_snapshot_path(), index=False)
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("x")))

    assert persistence.load_latest_snapshot() is None


def test_get_latest_snapshot_before_picks_latest_eligible(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    pd.DataFrame([{"symbol": "A"}]).to_csv(persistence._get_snapshot_path(date(2024, 1, 1)), index=False)
    pd.DataFrame([{"symbol": "B"}]).to_csv(persistence._get_snapshot_path(date(2024, 1, 5)), index=False)
    pd.DataFrame([{"symbol": "C"}]).to_csv(persistence._get_snapshot_path(date(2024, 1, 10)), index=False)

    loaded = persistence.get_latest_snapshot_before(date(2024, 1, 8))

    assert loaded is not None
    assert loaded.iloc[0]["symbol"] == "B"


def test_get_latest_snapshot_before_returns_none_when_no_candidate(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    pd.DataFrame([{"symbol": "A"}]).to_csv(persistence._get_snapshot_path(date(2024, 1, 5)), index=False)

    assert persistence.get_latest_snapshot_before(date(2024, 1, 1)) is None


def test_get_latest_snapshot_before_skips_invalid_name_suffix(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    (persistence.snapshots_dir / "market_snapshot_invalid.csv").write_text("symbol\nX\n", encoding="utf-8")
    pd.DataFrame([{"symbol": "A"}]).to_csv(persistence._get_snapshot_path(date(2024, 1, 5)), index=False)

    loaded = persistence.get_latest_snapshot_before(date(2024, 1, 6))

    assert loaded is not None
    assert loaded.iloc[0]["symbol"] == "A"


def test_get_latest_snapshot_before_skips_non_prefixed_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)
    valid = persistence._get_snapshot_path(date(2024, 1, 5))
    pd.DataFrame([{"symbol": "A"}]).to_csv(valid, index=False)

    non_prefixed = persistence.snapshots_dir / "other_file.csv"
    non_prefixed.write_text("symbol\nX\n", encoding="utf-8")

    monkeypatch.setattr(persistence, "list_snapshots", lambda: [non_prefixed, valid])

    loaded = persistence.get_latest_snapshot_before(date(2024, 1, 6))

    assert loaded is not None
    assert loaded.iloc[0]["symbol"] == "A"


def test_get_latest_snapshot_before_returns_none_on_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)
    pd.DataFrame([{"symbol": "A"}]).to_csv(persistence._get_snapshot_path(date(2024, 1, 5)), index=False)

    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: (_ for _ in ()).throw(IOError("nope")))

    assert persistence.get_latest_snapshot_before(date(2024, 1, 6)) is None


def test_save_historical_writes_file(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    persistence.save_historical("nabil", _history_df())

    assert (persistence.historical_dir / "NABIL_history.csv").exists()


def test_save_historical_empty_skips(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    persistence.save_historical("NABIL", pd.DataFrame())

    assert not (persistence.historical_dir / "NABIL_history.csv").exists()


def test_save_historical_raises_on_write_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)
    df = _history_df()

    def _raise(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("cannot save")

    monkeypatch.setattr(pd.DataFrame, "to_csv", _raise)

    with pytest.raises(RuntimeError, match="cannot save"):
        persistence.save_historical("NABIL", df)


def test_load_historical_returns_none_when_missing(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    assert persistence.load_historical("NABIL") is None


def test_load_historical_parses_date_column(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    _history_df().to_csv(persistence._get_historical_path("NABIL"), index=False)

    loaded = persistence.load_historical("NABIL")

    assert loaded is not None
    assert str(loaded["date"].dtype).startswith("datetime64")


def test_load_historical_returns_none_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)
    _history_df().to_csv(persistence._get_historical_path("NABIL"), index=False)

    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("x")))

    assert persistence.load_historical("NABIL") is None


def test_save_universe_empty_skips(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    persistence.save_universe({})

    assert persistence.list_historical_symbols() == []


def test_save_universe_writes_multiple_symbols(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    persistence.save_universe({"NABIL": _history_df(), "SBI": _history_df()})

    assert persistence.list_historical_symbols() == ["NABIL", "SBI"]


def test_save_universe_continues_when_one_symbol_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)

    original = persistence.save_historical

    def _save(symbol: str, historical_df: pd.DataFrame) -> None:
        if symbol == "BAD":
            raise RuntimeError("fail")
        original(symbol, historical_df)

    monkeypatch.setattr(persistence, "save_historical", _save)

    persistence.save_universe({"BAD": _history_df(), "GOOD": _history_df()})

    assert "GOOD" in persistence.list_historical_symbols()


def test_load_universe_returns_only_found_non_empty(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    persistence.save_historical("NABIL", _history_df())
    persistence.save_historical("EMPTY", pd.DataFrame(columns=["date", "close"]))

    loaded = persistence.load_universe(["NABIL", "EMPTY", "MISSING"])

    assert list(loaded.keys()) == ["NABIL"]


def test_load_historical_many_aliases_load_universe(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    persistence.save_historical("NABIL", _history_df())

    loaded = persistence.load_historical_many(["NABIL"])

    assert "NABIL" in loaded


def test_get_snapshot_age_seconds_returns_none_when_missing(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    assert persistence.get_snapshot_age_seconds(date(2024, 1, 1)) is None


def test_get_snapshot_age_seconds_returns_int_age(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    target_path = persistence._get_snapshot_path(date(2024, 1, 1))
    _snapshot_df().to_csv(target_path, index=False)

    age = persistence.get_snapshot_age_seconds(date(2024, 1, 1))

    assert isinstance(age, int)
    assert age >= 0


def test_get_snapshot_age_seconds_returns_none_on_stat_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = DataPersistence(tmp_path)
    target_path = persistence._get_snapshot_path(date(2024, 1, 1))
    _snapshot_df().to_csv(target_path, index=False)

    import nepse_api.data_persistence as module

    class _BadDateTime:
        @staticmethod
        def fromtimestamp(ts: float) -> datetime:
            raise OSError("boom")

    monkeypatch.setattr(module, "datetime", _BadDateTime)

    assert persistence.get_snapshot_age_seconds(date(2024, 1, 1)) is None


def test_list_snapshots_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    # Remove snapshots directory to test guard path.
    for child in persistence.snapshots_dir.glob("*"):
        child.unlink()
    persistence.snapshots_dir.rmdir()

    assert persistence.list_snapshots() == []


def test_list_snapshots_excludes_latest_and_sorts_newest_first(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)

    older = persistence._get_snapshot_path(date(2024, 1, 1))
    newer = persistence._get_snapshot_path(date(2024, 1, 2))
    _snapshot_df().to_csv(older, index=False)
    _snapshot_df().to_csv(newer, index=False)
    _snapshot_df().to_csv(persistence._get_latest_snapshot_path(), index=False)

    # Force modification order: older then newer.
    now = datetime.now().timestamp()
    older.touch()
    newer.touch()
    older_mtime = now - 100
    newer_mtime = now - 10
    import os

    os.utime(older, (older_mtime, older_mtime))
    os.utime(newer, (newer_mtime, newer_mtime))

    snapshots = persistence.list_snapshots()

    assert [p.name for p in snapshots] == ["market_snapshot_2024-01-02.csv", "market_snapshot_2024-01-01.csv"]


def test_list_historical_symbols_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    for child in persistence.historical_dir.glob("*"):
        child.unlink()
    persistence.historical_dir.rmdir()

    assert persistence.list_historical_symbols() == []


def test_list_historical_symbols_sorted(tmp_path: Path) -> None:
    persistence = DataPersistence(tmp_path)
    persistence.save_historical("sbi", _history_df())
    persistence.save_historical("nabil", _history_df())

    assert persistence.list_historical_symbols() == ["NABIL", "SBI"]
