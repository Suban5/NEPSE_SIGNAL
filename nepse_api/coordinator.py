from __future__ import annotations

"""Coordinator orchestrating provider, normalizer, and repository data flow."""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import logging

import pandas as pd


logger = logging.getLogger(__name__)


class DataFetchCoordinator:
    """Coordinate upstream fetching, normalization, persistence, and fallback."""

    def __init__(
        self,
        remote: Any,
        snapshot_repo: Any,
        history_repo: Any,
        snapshot_normalizer: Any,
        history_normalizer: Any,
    ) -> None:
        self.remote = remote
        self.snapshot_repo = snapshot_repo
        self.history_repo = history_repo
        self.snapshot_normalizer = snapshot_normalizer
        self.history_normalizer = history_normalizer
        self._snapshot_cache: Optional[pd.DataFrame] = None

    def get_market_snapshot(self, force_refresh: bool = False) -> pd.DataFrame:
        """Return market snapshot using live fetch, then persisted, then security master fallback."""
        if not force_refresh and self._snapshot_cache is not None and not self._snapshot_cache.empty:
            return self._snapshot_cache.copy()

        live_df = self._fetch_live_snapshot()
        if not live_df.empty:
            self.snapshot_repo.save(live_df.copy())
            self._snapshot_cache = live_df.copy()
            return live_df

        # Required fallback order: persisted snapshot before security master.
        persisted_df = None if force_refresh else self.snapshot_repo.load_latest()
        if isinstance(persisted_df, pd.DataFrame) and not persisted_df.empty:
            logger.warning("Using persisted latest snapshot fallback")
            self._snapshot_cache = persisted_df.copy()
            return persisted_df

        fallback_df = self._build_security_master_fallback()
        self._snapshot_cache = fallback_df.copy()
        return fallback_df

    def get_historical(
        self,
        symbol: str,
        start: Optional[date],
        end: Optional[date],
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Return historical OHLCV for one symbol with optional true refresh behavior."""
        normalized_symbol = symbol.upper().strip()
        final_end = end or date.today()
        final_start = start or (final_end - timedelta(days=365 * 5))

        if not force_refresh:
            from_disk = self.history_repo.load_many([normalized_symbol]).get(normalized_symbol)
            if isinstance(from_disk, pd.DataFrame) and not from_disk.empty:
                return from_disk

        raw_payload = self.remote.get_company_history_raw(symbol=normalized_symbol, start=final_start, end=final_end)
        history_df = self.history_normalizer.normalize_history(raw_payload, symbol=normalized_symbol)
        if not history_df.empty:
            self.history_repo.save_one(normalized_symbol, history_df.copy())
        return history_df

    def get_universe_with_history(self, lookback_years: int = 5, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        """Return historical universe keyed by symbol.

        This keeps compatibility with existing workflow call signatures.
        """
        snapshot_df = self.get_market_snapshot(force_refresh=force_refresh)
        if snapshot_df.empty or "symbol" not in snapshot_df.columns:
            return {}

        symbols = sorted(snapshot_df["symbol"].dropna().astype(str).str.upper().unique().tolist())
        if not symbols:
            return {}

        universe: Dict[str, pd.DataFrame] = {}
        if not force_refresh:
            universe.update(self.history_repo.load_many(symbols))

        end = date.today()
        start = end - timedelta(days=365 * lookback_years)
        missing_symbols = [s for s in symbols if s not in universe]
        for symbol in missing_symbols:
            history_df = self.get_historical(symbol=symbol, start=start, end=end, force_refresh=True)
            if not history_df.empty:
                universe[symbol] = history_df

        return universe

    def _fetch_live_snapshot(self) -> pd.DataFrame:
        """Fetch and normalize upstream live market payload."""
        try:
            payload = self.remote.get_live_market_raw()
        except Exception as exc:
            logger.warning("Live market fetch failed: %s", exc)
            return pd.DataFrame()
        return self.snapshot_normalizer.normalize_live_market(payload)

    def _build_security_master_fallback(self) -> pd.DataFrame:
        """Build metadata-only snapshot fallback from securities list."""
        try:
            payload = self.remote.get_security_list_raw()
        except Exception as exc:
            logger.warning("Security list fallback fetch failed: %s", exc)
            return pd.DataFrame()

        rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            symbol = row.get("symbol") or row.get("stockSymbol") or row.get("ticker")
            if not symbol:
                continue
            normalized.append(
                {
                    "symbol": str(symbol).upper(),
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.0,
                    "volume": 0.0,
                    "turnover": 0.0,
                    "market_cap": row.get("marketCap")
                    or row.get("market_cap")
                    or row.get("marketCapitalization")
                    or row.get("marketCapitalisation")
                    or 0.0,
                    "sector": row.get("businessSectorName")
                    or row.get("sectorName")
                    or row.get("sector")
                    or row.get("sectorType")
                    or "Unknown",
                    "data_source": "security_master_fallback",
                }
            )

        return pd.DataFrame(normalized)
