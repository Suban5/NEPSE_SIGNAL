"""Persistent local storage for NEPSE market data."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional
import logging

import pandas as pd


logger = logging.getLogger(__name__)


class DataPersistence:
    """Manages local storage and retrieval of NEPSE market data."""

    def __init__(self, base_dir: str | Path = "data/datasets") -> None:
        """Initialize persistence layer with base directory.

        Args:
            base_dir: Root directory for storing datasets.
        """
        self.base_dir = Path(base_dir)
        self.snapshots_dir = self.base_dir / "snapshots"
        self.historical_dir = self.base_dir / "historical"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create required directory structure."""
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.historical_dir.mkdir(parents=True, exist_ok=True)

    def _get_snapshot_path(self, snapshot_date: Optional[date] = None) -> Path:
        """Get path for snapshot file.

        Args:
            snapshot_date: Date for snapshot. Defaults to today.

        Returns:
            Path to snapshot CSV file.
        """
        if snapshot_date is None:
            snapshot_date = date.today()
        return self.snapshots_dir / f"market_snapshot_{snapshot_date.isoformat()}.csv"

    def _get_latest_snapshot_path(self) -> Path:
        """Get path for latest snapshot symlink/reference file."""
        return self.snapshots_dir / "market_snapshot_latest.csv"

    def _get_historical_path(self, symbol: str) -> Path:
        """Get path for historical data file.

        Args:
            symbol: Stock symbol (e.g., 'NABIL').

        Returns:
            Path to historical CSV file.
        """
        safe_symbol = symbol.upper().replace("/", "_").replace("\\", "_")
        return self.historical_dir / f"{safe_symbol}_history.csv"

    def save_snapshot(self, snapshot_df: pd.DataFrame, snapshot_date: Optional[date] = None) -> None:
        """Save market snapshot to disk.

        Args:
            snapshot_df: DataFrame containing market snapshot.
            snapshot_date: Date for snapshot. Defaults to today.
        """
        if snapshot_df.empty:
            logger.warning("Snapshot is empty, skipping save")
            return

        snapshot_date = snapshot_date or date.today()
        dated_path = self._get_snapshot_path(snapshot_date)
        latest_path = self._get_latest_snapshot_path()

        try:
            snapshot_df.to_csv(dated_path, index=False)
            logger.info(f"Saved snapshot to {dated_path}")

            # Also update latest reference
            snapshot_df.to_csv(latest_path, index=False)
            logger.info(f"Updated latest snapshot at {latest_path}")
        except Exception as exc:
            logger.error(f"Failed to save snapshot: {exc}")
            raise

    def load_snapshot(self, snapshot_date: Optional[date] = None) -> Optional[pd.DataFrame]:
        """Load market snapshot from disk.

        Args:
            snapshot_date: Date for snapshot. Defaults to today.

        Returns:
            DataFrame if found, None otherwise.
        """
        snapshot_date = snapshot_date or date.today()
        path = self._get_snapshot_path(snapshot_date)

        if not path.exists():
            logger.debug(f"Snapshot not found at {path}")
            return None

        try:
            df = pd.read_csv(path)
            logger.info(f"Loaded snapshot from {path}")
            return df
        except Exception as exc:
            logger.error(f"Failed to load snapshot: {exc}")
            return None

    def load_latest_snapshot(self) -> Optional[pd.DataFrame]:
        """Load latest available snapshot.

        Returns:
            DataFrame if found, None otherwise.
        """
        latest_path = self._get_latest_snapshot_path()

        if not latest_path.exists():
            logger.debug("No latest snapshot found")
            return None

        try:
            df = pd.read_csv(latest_path)
            logger.info(f"Loaded latest snapshot from {latest_path}")
            return df
        except Exception as exc:
            logger.error(f"Failed to load latest snapshot: {exc}")
            return None

    def get_latest_snapshot_before(self, date_value: date) -> Optional[pd.DataFrame]:
        """Load the most recent snapshot on or before the provided date.

        Args:
            date_value: Upper date bound for snapshot lookup.

        Returns:
            Snapshot DataFrame if found, otherwise None.
        """
        dated_snapshots: list[tuple[date, Path]] = []
        for snapshot_path in self.list_snapshots():
            name = snapshot_path.stem
            if not name.startswith("market_snapshot_"):
                continue
            suffix = name.replace("market_snapshot_", "", 1)
            try:
                snapshot_date = date.fromisoformat(suffix)
            except ValueError:
                continue
            if snapshot_date <= date_value:
                dated_snapshots.append((snapshot_date, snapshot_path))

        if not dated_snapshots:
            return None

        dated_snapshots.sort(key=lambda item: item[0], reverse=True)
        target_path = dated_snapshots[0][1]
        try:
            df = pd.read_csv(target_path)
            logger.info("Loaded snapshot fallback from %s", target_path)
            return df
        except Exception as exc:
            logger.error("Failed to load snapshot fallback %s: %s", target_path, exc)
            return None

    def save_historical(self, symbol: str, historical_df: pd.DataFrame) -> None:
        """Save historical OHLCV data for symbol.

        Args:
            symbol: Stock symbol (e.g., 'NABIL').
            historical_df: DataFrame containing historical OHLCV data.
        """
        if historical_df.empty:
            logger.warning(f"Historical data for {symbol} is empty, skipping save")
            return

        path = self._get_historical_path(symbol)

        try:
            historical_df.to_csv(path, index=False)
            logger.info(f"Saved historical data for {symbol} to {path}")
        except Exception as exc:
            logger.error(f"Failed to save historical data for {symbol}: {exc}")
            raise

    def load_historical(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load historical OHLCV data for symbol.

        Args:
            symbol: Stock symbol (e.g., 'NABIL').

        Returns:
            DataFrame if found, None otherwise.
        """
        path = self._get_historical_path(symbol)

        if not path.exists():
            logger.debug(f"Historical data not found for {symbol} at {path}")
            return None

        try:
            df = pd.read_csv(path)
            # Ensure date column is datetime
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            logger.debug(f"Loaded historical data for {symbol} from {path}")
            return df
        except Exception as exc:
            logger.error(f"Failed to load historical data for {symbol}: {exc}")
            return None

    def save_universe(self, universe: Dict[str, pd.DataFrame]) -> None:
        """Save all historical data from universe.

        Args:
            universe: Mapping of symbol to historical DataFrame.
        """
        if not universe:
            logger.warning("Universe is empty, skipping save")
            return

        for symbol, hist_df in universe.items():
            try:
                self.save_historical(symbol, hist_df)
            except Exception as exc:
                logger.warning(f"Failed to save historical data for {symbol}: {exc}")

        logger.info(f"Saved historical data for {len(universe)} symbols")

    def load_universe(self, symbols: list[str]) -> Dict[str, pd.DataFrame]:
        """Load historical data for multiple symbols.

        Args:
            symbols: List of stock symbols to load.

        Returns:
            Mapping of symbol to historical DataFrame (only for found symbols).
        """
        universe: Dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            hist_df = self.load_historical(symbol)
            if hist_df is not None and not hist_df.empty:
                universe[symbol] = hist_df
            else:
                logger.debug(f"Could not load historical data for {symbol}")

        logger.info(f"Loaded historical data for {len(universe)} of {len(symbols)} requested symbols")
        return universe

    def load_historical_many(self, symbols: list[str]) -> Dict[str, pd.DataFrame]:
        """Load historical data for multiple symbols.

        This is a naming alias used by the coordinator-facing repository contract.
        """
        return self.load_universe(symbols)

    def get_snapshot_age_seconds(self, snapshot_date: Optional[date] = None) -> Optional[int]:
        """Get age of snapshot file in seconds.

        Args:
            snapshot_date: Date for snapshot. Defaults to today.

        Returns:
            Age in seconds, or None if file doesn't exist.
        """
        snapshot_date = snapshot_date or date.today()
        path = self._get_snapshot_path(snapshot_date)

        if not path.exists():
            return None

        try:
            file_time = datetime.fromtimestamp(path.stat().st_mtime)
            age = datetime.now() - file_time
            return int(age.total_seconds())
        except Exception as exc:
            logger.error(f"Failed to get snapshot age: {exc}")
            return None

    def list_snapshots(self) -> list[Path]:
        """List all available snapshot files.

        Returns:
            List of snapshot file paths, sorted by date (newest first).
        """
        if not self.snapshots_dir.exists():
            return []

        snapshots = list(self.snapshots_dir.glob("market_snapshot_*.csv"))
        # Filter out latest reference and sort by modification time
        snapshots = [s for s in snapshots if "latest" not in s.name]
        snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return snapshots

    def list_historical_symbols(self) -> list[str]:
        """List all symbols with cached historical data.

        Returns:
            List of stock symbols.
        """
        if not self.historical_dir.exists():
            return []

        symbols = []
        for path in self.historical_dir.glob("*_history.csv"):
            symbol = path.stem.replace("_history", "")
            symbols.append(symbol)
        return sorted(symbols)
