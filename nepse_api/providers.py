from __future__ import annotations

"""Provider layer for upstream and persisted NEPSE data sources."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import date
import io
import random
import time
from typing import Any, Dict, List, Optional

import pandas as pd
from nepse_client import NepseClient


@dataclass(frozen=True)
class RetryPolicy:
    """Retry policy for provider calls."""

    attempts: int = 3
    backoff_seconds: float = 0.25
    jitter_seconds: float = 0.10


class NepseClientProvider:
    """Thin provider wrapping nepse_client method calls with retry and jitter."""

    def __init__(
        self,
        client: NepseClient,
        retry: RetryPolicy,
        suppress_output: bool = True,
    ) -> None:
        self.client = client
        self.retry = retry
        self.suppress_output = suppress_output

    def get_live_market_raw(self) -> Any:
        """Fetch live market payload from upstream."""
        return self._call_with_retry("getLiveMarket")

    def get_security_list_raw(self) -> Any:
        """Fetch security master list payload from upstream."""
        return self._call_with_retry("getSecurityList")

    def get_sector_scrips_raw(self) -> Any:
        """Fetch sector-to-symbol mapping payload from upstream."""
        return self._call_with_retry("getSectorScrips")

    def get_company_history_raw(self, symbol: str, start: date, end: date) -> Any:
        """Fetch company OHLCV history payload from upstream."""
        return self._call_with_retry(
            "getCompanyPriceVolumeHistory",
            symbol=symbol.upper(),
            start_date=start,
            end_date=end,
        )

    def get_company_details_raw(self, symbol: str) -> Any:
        """Fetch company details payload from upstream."""
        return self._call_with_retry("getCompanyDetails", symbol=symbol.upper())

    def _call_with_retry(self, method_name: str, **kwargs: Any) -> Any:
        """Invoke client method with bounded retries and random jitter."""
        last_exc: Exception | None = None
        for attempt in range(1, self.retry.attempts + 1):
            try:
                method = getattr(self.client, method_name)
                if not self.suppress_output:
                    return method(**kwargs)

                sink = io.StringIO()
                with redirect_stdout(sink), redirect_stderr(sink):
                    return method(**kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt >= self.retry.attempts:
                    break
                sleep_for = (self.retry.backoff_seconds * attempt) + random.uniform(0, self.retry.jitter_seconds)
                if sleep_for > 0:
                    time.sleep(sleep_for)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Failed call: {method_name}")


class PersistedSnapshotProvider:
    """Provider for persisted snapshot access."""

    def __init__(self, persistence: Any) -> None:
        self.persistence = persistence

    def load_latest(self) -> Optional[pd.DataFrame]:
        """Load latest persisted snapshot."""
        return self.persistence.load_latest_snapshot()

    def save(self, snapshot_df: pd.DataFrame) -> None:
        """Persist latest snapshot."""
        self.persistence.save_snapshot(snapshot_df)


class PersistedHistoryProvider:
    """Provider for persisted historical access."""

    def __init__(self, persistence: Any) -> None:
        self.persistence = persistence

    def load_many(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Load historical data for multiple symbols from disk."""
        return self.persistence.load_universe(symbols)

    def save_one(self, symbol: str, history_df: pd.DataFrame) -> None:
        """Persist historical data for one symbol."""
        self.persistence.save_historical(symbol, history_df)
