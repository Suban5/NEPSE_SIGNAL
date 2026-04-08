from __future__ import annotations

"""NEPSE API data fetching module."""

from contextlib import redirect_stderr, redirect_stdout
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
import io
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

import pandas as pd
from api.cache import TTLCache
from config.settings import get_settings
from nepse_api.data_persistence import DataPersistence


logger = logging.getLogger(__name__)


@dataclass
class NepseApiConfig:
    """Configuration object for NEPSE API calls."""

    base_url: str
    timeout_seconds: int
    tls_verify: bool
    suppress_unofficial_client_output: bool

    @classmethod
    def from_env(cls) -> "NepseApiConfig":
        """Create API config from application settings."""
        settings = get_settings()
        return cls(
            base_url=settings.nepse_api_base_url,
            timeout_seconds=settings.nepse_api_timeout,
            tls_verify=settings.nepse_tls_verify,
            suppress_unofficial_client_output=settings.suppress_unofficial_client_output,
        )


class LegacyNepseDataFetcher:
    """Legacy fetcher kept for backward compatibility during coordinator migration."""

    def __init__(self, config: Optional[NepseApiConfig] = None, enable_persistence: bool = True) -> None:
        self.config = config or NepseApiConfig.from_env()
        if not self.config.base_url:
            raise ValueError("NEPSE_API_BASE_URL must be configured in environment")
        settings = get_settings()
        self._snapshot_cache = TTLCache(
            ttl_seconds=max(1.0, float(settings.cache_market_snapshot_ttl_seconds)),
            max_entries=max(50, int(settings.cache_max_entries)),
        )
        self._historical_cache = TTLCache(
            ttl_seconds=max(1.0, float(settings.cache_historical_ttl_seconds)),
            max_entries=max(200, int(settings.cache_max_entries)),
        )
        self._persistence = DataPersistence() if enable_persistence else None
        self._sector_lookup_cache: Optional[Dict[str, str]] = None
        self._unofficial_client = self._init_unofficial_client()
        if self._unofficial_client is None:
            raise RuntimeError(
                "nepse_client is required for NEPSE data fetching. "
                "Install dependency and verify NEPSE base URL configuration."
            )

    @staticmethod
    def _build_jitter(symbol: str, attempt: int, max_jitter_seconds: float) -> float:
        """Build deterministic jitter value for retry backoff."""
        if max_jitter_seconds <= 0:
            return 0.0
        seed = sum(ord(char) for char in f"{symbol}:{attempt}") % 1000
        return (seed / 1000.0) * max_jitter_seconds

    def _fetch_historical_with_retry(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch historical rows with bounded retries and jitter."""
        settings = get_settings()
        attempts = max(1, int(settings.market_fetch_retry_attempts))
        backoff = max(0.0, float(settings.market_fetch_retry_backoff_seconds))
        jitter = max(0.0, float(settings.market_fetch_retry_jitter_seconds))
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return self.fetch_historical_ohlcv(symbol=symbol, start_date=start_date, end_date=end_date)
            except Exception as exc:
                last_exc = exc
                if attempt >= attempts:
                    break
                sleep_for = (backoff * attempt) + self._build_jitter(symbol, attempt, jitter)
                if sleep_for > 0:
                    time.sleep(sleep_for)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Historical fetch failed for {symbol}")

    @staticmethod
    def _historical_cache_key(symbol: str, start_date: date, end_date: date) -> str:
        """Build cache key for historical symbol window."""
        return f"history:{symbol.upper()}:{start_date.isoformat()}:{end_date.isoformat()}"

    def invalidate_cache(self, scope: str = "all") -> None:
        """Invalidate fetcher caches.

        Args:
            scope: One of all, snapshot, historical.
        """
        normalized_scope = scope.lower().strip()
        if normalized_scope in {"all", "snapshot"}:
            self._snapshot_cache.clear()
        if normalized_scope in {"all", "historical"}:
            self._historical_cache.clear()

    def _init_unofficial_client(self) -> Optional[Any]:
        """Initialize maintained unofficial NEPSE client as preferred adapter.

        Returns:
            Nepse client instance when available, else None.
        """
        base_url = self.config.base_url.lower()
        if "nepalstock.com" not in base_url:
            return None

        try:
            from nepse_client import NepseClient
        except ImportError:
            logger.info(
                "Package 'nepse_client' not installed; cannot fetch NEPSE data for %s",
                self.config.base_url,
            )
            return None

        try:
            unofficial_client = NepseClient(timeout=float(self.config.timeout_seconds))
            if hasattr(unofficial_client, "setTLSVerification"):
                unofficial_client.setTLSVerification(self.config.tls_verify)
            logger.info("Using nepse_client as default adapter for NEPSE data fetching")
            return unofficial_client
        except Exception as exc:
            logger.warning("Failed to initialize nepse_client adapter: %s", exc)
            return None

    def _call_unofficial_client(self, method_name: str, **kwargs: Any) -> Any:
        """Call unofficial client method with optional stdout/stderr suppression.

        Args:
            method_name: Method name on unofficial client.
            **kwargs: Method keyword arguments.

        Returns:
            Method return payload.
        """
        if self._unofficial_client is None:
            raise RuntimeError("Unofficial client is not initialized")
        method = getattr(self._unofficial_client, method_name)
        if not self.config.suppress_unofficial_client_output:
            return method(**kwargs)

        silent_buffer = io.StringIO()
        with redirect_stdout(silent_buffer), redirect_stderr(silent_buffer):
            return method(**kwargs)

    @staticmethod
    def _coerce_symbol_rows(payload: Any) -> List[Dict[str, Any]]:
        """Extract list rows from mixed API response schemas."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "result", "items", "content"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def _extract_sector_lookup(payload: Any) -> Dict[str, str]:
        """Extract symbol->sector mapping from getSectorScrips payload."""
        lookup: Dict[str, str] = {}
        if not isinstance(payload, dict):
            return lookup

        for sector_name, entries in payload.items():
            if not isinstance(sector_name, str) or not sector_name.strip():
                continue
            if not isinstance(entries, list):
                continue
            normalized_sector = sector_name.strip()
            for entry in entries:
                symbol: Optional[str] = None
                if isinstance(entry, str):
                    symbol = entry
                elif isinstance(entry, dict):
                    symbol = entry.get("symbol") or entry.get("stockSymbol") or entry.get("ticker")
                if symbol:
                    lookup[str(symbol).upper()] = normalized_sector
        return lookup

    def _load_sector_lookup_from_file(self) -> Dict[str, str]:
        """Load optional local symbol->sector mapping CSV."""
        settings = get_settings()
        path = Path(settings.sector_master_path)
        if not path.exists():
            return {}

        try:
            mapping_df = pd.read_csv(path)
        except Exception as exc:
            logger.warning("Failed to read sector master file %s: %s", path, exc)
            return {}

        required = {"symbol", "sector"}
        if not required.issubset(set(mapping_df.columns)):
            logger.warning("Sector master file missing required columns: symbol, sector")
            return {}

        cleaned_df = mapping_df[["symbol", "sector"]].dropna()
        cleaned_df["symbol"] = cleaned_df["symbol"].astype(str).str.upper().str.strip()
        cleaned_df["sector"] = cleaned_df["sector"].astype(str).str.strip()
        cleaned_df = cleaned_df[(cleaned_df["symbol"] != "") & (cleaned_df["sector"] != "")]
        return dict(zip(cleaned_df["symbol"], cleaned_df["sector"]))

    def _get_sector_lookup(self) -> Dict[str, str]:
        """Build and cache symbol->sector lookup from API and optional local file."""
        if self._sector_lookup_cache is not None:
            return self._sector_lookup_cache

        lookup: Dict[str, str] = {}
        try:
            payload = self._call_unofficial_client("getSectorScrips")
            lookup.update(self._extract_sector_lookup(payload))
        except Exception as exc:
            logger.debug("Sector mapping endpoint unavailable: %s", exc)

        # Local CSV overrides API entries when explicitly configured by user.
        local_lookup = self._load_sector_lookup_from_file()
        if local_lookup:
            lookup.update(local_lookup)

        self._sector_lookup_cache = lookup
        return lookup

    @staticmethod
    def _coerce_numeric(value: Any) -> float:
        """Convert mixed numeric values to float with safe fallback.

        Args:
            value: Value to coerce to float (can be numeric, string, or other type).

        Returns:
            Float value or 0.0 if coercion fails.
        """
        if value is None:
            return 0.0
        if isinstance(value, (list, dict)) and not value:
            return 0.0

        try:
            numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            return float(numeric) if pd.notna(numeric) else 0.0
        except (ValueError, TypeError, AttributeError):
            return 0.0

    @staticmethod
    def _first_non_empty(row: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
        """Return first non-empty value from row for provided keys."""
        for key in keys:
            value = row.get(key)
            if value is not None and value != "":
                return value
        return default

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        """Convert value to float and return None for invalid values."""
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(numeric):
            return None
        return numeric

    def _hydrate_snapshot_from_local_history(self, snapshot_df: pd.DataFrame) -> pd.DataFrame:
        """Fill fallback snapshot OHLCV fields from latest local historical rows.

        Args:
            snapshot_df: Snapshot built from security master fallback.

        Returns:
            Snapshot with best-effort OHLCV enrichment from persisted history.
        """
        persistence = getattr(self, "_persistence", None)
        if persistence is None or snapshot_df.empty or "symbol" not in snapshot_df.columns:
            return snapshot_df

        symbols = snapshot_df["symbol"].dropna().astype(str).str.upper().unique().tolist()
        if not symbols:
            return snapshot_df

        try:
            historical_universe = persistence.load_universe(symbols)
        except Exception as exc:
            logger.warning("Failed loading local historical universe for fallback enrichment: %s", exc)
            return snapshot_df

        if not historical_universe:
            return snapshot_df

        enriched_count = 0
        for symbol, history_df in historical_universe.items():
            if history_df is None or history_df.empty:
                continue

            ordered_history = history_df.sort_values("date") if "date" in history_df.columns else history_df
            latest_row = ordered_history.iloc[-1]

            close_val = self._as_float(latest_row.get("close"))
            open_val = self._as_float(latest_row.get("open"))
            high_val = self._as_float(latest_row.get("high"))
            low_val = self._as_float(latest_row.get("low"))
            volume_val = self._as_float(latest_row.get("volume"))
            turnover_val = self._as_float(latest_row.get("turnover"))

            if close_val is None:
                continue

            selector = snapshot_df["symbol"] == symbol
            if not selector.any():
                continue

            snapshot_df.loc[selector, "close"] = close_val
            snapshot_df.loc[selector, "open"] = open_val if open_val is not None else close_val
            snapshot_df.loc[selector, "high"] = high_val if high_val is not None else close_val
            snapshot_df.loc[selector, "low"] = low_val if low_val is not None else close_val
            if volume_val is not None:
                snapshot_df.loc[selector, "volume"] = volume_val
            if turnover_val is not None:
                snapshot_df.loc[selector, "turnover"] = turnover_val
            snapshot_df.loc[selector, "data_source"] = "historical_fallback"
            enriched_count += 1

        if enriched_count > 0:
            logger.info("Hydrated fallback snapshot from local history for %d symbols", enriched_count)
        return snapshot_df

    def fetch_symbols(self) -> pd.DataFrame:
        """Fetch security master list.

        Returns:
            DataFrame with symbol, sector, and market cap.
        """
        rows = self._coerce_symbol_rows(self._call_unofficial_client("getSecurityList"))
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            symbol = row.get("symbol") or row.get("stockSymbol") or row.get("ticker")
            if not symbol:
                continue
            normalized.append(
                {
                    "symbol": str(symbol).upper(),
                    "id": row.get("id") or row.get("securityId") or row.get("companyId"),
                    "sector": self._first_non_empty(
                        row,
                        ["businessSectorName", "sectorName", "sector", "sectorType"],
                        "Unknown",
                    ),
                    "market_cap": self._first_non_empty(
                        row,
                        ["marketCap", "market_cap", "marketCapitalization", "marketCapitalisation"],
                        0,
                    ),
                }
            )
        symbols_df = pd.DataFrame(normalized).drop_duplicates(subset=["symbol"])
        if not symbols_df.empty and "market_cap" in symbols_df.columns:
            symbols_df["market_cap"] = pd.to_numeric(symbols_df["market_cap"], errors="coerce").fillna(0.0)
        if not symbols_df.empty and "sector" in symbols_df.columns:
            sector_lookup = self._get_sector_lookup()
            if sector_lookup:
                mapped_sector = symbols_df["symbol"].map(sector_lookup)
                symbols_df["sector"] = symbols_df["sector"].where(
                    ~symbols_df["sector"].isin(["Unknown", ""]),
                    mapped_sector,
                )
                symbols_df["sector"] = symbols_df["sector"].fillna("Unknown")
        return symbols_df

    def fetch_daily_market_snapshot(self, force_refresh: bool = False) -> pd.DataFrame:
        """Fetch daily market snapshot with OHLCV and liquidity fields.
        
        Args:
            force_refresh: If True, bypass local cache and fetch from API.
            
        Returns:
            Market snapshot DataFrame.
        """
        # Try memory cache first (fast path)
        if not force_refresh:
            cached_snapshot = self._snapshot_cache.get("market_snapshot")
            if isinstance(cached_snapshot, pd.DataFrame):
                return cached_snapshot.copy()

        # Fetch from API
        logger.info("Fetching fresh market snapshot from NEPSE API")
        payload = self._call_unofficial_client("getLiveMarket")
        rows = self._coerce_symbol_rows(payload)
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            symbol = row.get("symbol") or row.get("stockSymbol") or row.get("ticker")
            if not symbol:
                continue
            normalized.append(
                {
                    "symbol": str(symbol).upper(),
                    "open": row.get("openPrice") or row.get("open") or row.get("previousClosing") or 0,
                    "high": row.get("highPrice") or row.get("high") or row.get("highPrice52Week") or 0,
                    "low": row.get("lowPrice") or row.get("low") or row.get("lowPrice52Week") or 0,
                    "close": row.get("closePrice")
                    or row.get("lastTradedPrice")
                    or row.get("ltp")
                    or row.get("close")
                    or 0,
                    "volume": row.get("totalTradedQuantity")
                    or row.get("volume")
                    or row.get("totalTradeQuantity")
                    or row.get("tradeVolume")
                    or 0,
                    "turnover": row.get("totalTradedValue")
                    or row.get("totalTradeValue")
                    or row.get("turnover")
                    or row.get("totalTrades")
                    or row.get("tradeTurnover")
                    or 0,
                    "market_cap": self._first_non_empty(
                        row,
                        ["marketCap", "market_cap", "marketCapitalization", "marketCapitalisation"],
                        0,
                    ),
                    "sector": self._first_non_empty(
                        row,
                        ["businessSectorName", "sectorName", "sector", "sectorType"],
                        "Unknown",
                    ),
                    "data_source": "live_market",
                }
            )
        snapshot_df = pd.DataFrame(normalized)
        numeric_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover",
            "market_cap",
        ]
        for col in numeric_cols:
            if col in snapshot_df.columns:
                snapshot_df[col] = pd.to_numeric(snapshot_df[col], errors="coerce").fillna(0.0)

        if snapshot_df.empty:
            logger.warning("Live market snapshot payload is empty")

            # Prefer the full security master as a fallback because it contains
            # the complete tradable symbol universe, unlike the persisted sample snapshot.
            symbols_df = self.fetch_symbols()
            if not symbols_df.empty:
                fallback_snapshot = symbols_df.copy()
                for column in ["open", "high", "low", "close", "volume", "turnover"]:
                    fallback_snapshot[column] = 0.0
                if "sector" not in fallback_snapshot.columns:
                    fallback_snapshot["sector"] = "Unknown"
                if "market_cap" not in fallback_snapshot.columns:
                    fallback_snapshot["market_cap"] = 0.0
                fallback_snapshot["data_source"] = "security_master_fallback"

                fallback_snapshot = self._hydrate_snapshot_from_local_history(fallback_snapshot)
                for column in ["open", "high", "low"]:
                    fallback_snapshot[column] = fallback_snapshot[column].where(
                        fallback_snapshot[column] > 0,
                        fallback_snapshot["close"],
                    )

                ordered_columns = [
                    "symbol",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "turnover",
                    "market_cap",
                    "sector",
                    "data_source",
                ]
                fallback_snapshot = fallback_snapshot[[col for col in ordered_columns if col in fallback_snapshot.columns]]
                logger.warning("Using securities list fallback for market snapshot")
                self._snapshot_cache.set("market_snapshot", fallback_snapshot.copy())
                persistence = getattr(self, "_persistence", None)
                if persistence:
                    try:
                        persistence.save_snapshot(fallback_snapshot.copy())
                    except Exception as exc:
                        logger.warning("Failed to persist securities fallback snapshot: %s", exc)
                return fallback_snapshot

            self._snapshot_cache.set("market_snapshot", snapshot_df.copy())
            return snapshot_df

        symbols_df = self.fetch_symbols()
        if not symbols_df.empty:
            metadata = symbols_df[["symbol", "sector", "market_cap"]].rename(
                columns={
                    "sector": "sector_meta",
                    "market_cap": "market_cap_meta",
                }
            )
            snapshot_df = snapshot_df.merge(metadata, on="symbol", how="left")
            snapshot_df["sector"] = snapshot_df["sector"].fillna("Unknown")
            snapshot_df["sector"] = snapshot_df.apply(
                lambda row: row["sector_meta"]
                if (row["sector"] in {"Unknown", ""} and pd.notna(row["sector_meta"]))
                else row["sector"],
                axis=1,
            )
            snapshot_df["market_cap"] = snapshot_df["market_cap"].fillna(0.0)
            snapshot_df["market_cap"] = snapshot_df["market_cap"].where(
                snapshot_df["market_cap"] > 0,
                snapshot_df["market_cap_meta"],
            )
            snapshot_df["market_cap"] = pd.to_numeric(snapshot_df["market_cap"], errors="coerce").fillna(0.0)
            snapshot_df = snapshot_df.drop(columns=["sector_meta", "market_cap_meta"])

        # Save to memory and disk caches
        self._snapshot_cache.set("market_snapshot", snapshot_df.copy())
        persistence = getattr(self, "_persistence", None)
        if persistence:
            try:
                persistence.save_snapshot(snapshot_df.copy())
            except Exception as exc:
                logger.warning(f"Failed to persist snapshot to disk: {exc}")
        
        return snapshot_df

    @staticmethod
    def normalize_fundamentals(payload: Dict[str, Any]) -> Dict[str, float]:
        """Normalize fundamentals payload into scoring fields with validation.

        Args:
            payload: Raw company fundamentals payload.

        Returns:
            Dictionary with normalized earnings/revenue/dividend metrics (percentages).
        """
        if not payload or not isinstance(payload, dict):
            logger.debug("Empty or invalid fundamentals payload; using defaults")
            return {
                "earnings_growth": 0.0,
                "dividend_stability": 0.0,
                "revenue_growth": 0.0,
            }

        def pick(keys: List[str]) -> float:
            """Extract first available key value, coercing to float."""
            for key in keys:
                if key in payload:
                    value = LegacyNepseDataFetcher._coerce_numeric(payload.get(key))
                    return value
            return 0.0

        # Extract and validate (percentages can exceed 100 in exceptional cases)
        earnings_growth = LegacyNepseDataFetcher._validate_metric(
            pick(
                [
                    "earningsGrowth",
                    "earnings_growth",
                    "epsGrowth",
                    "eps_growth",
                    "profitGrowth",
                    "profit_growth",
                ]
            ),
            metric_name="earnings_growth",
        )
        revenue_growth = LegacyNepseDataFetcher._validate_metric(
            pick(["revenueGrowth", "revenue_growth", "salesGrowth", "sales_growth"]),
            metric_name="revenue_growth",
        )
        dividend_stability = LegacyNepseDataFetcher._validate_metric(
            pick(
                [
                    "dividendStability",
                    "dividend_stability",
                    "dividendYield",
                    "dividend_yield",
                    "dividendRate",
                    "dividend_rate",
                ]
            ),
            metric_name="dividend_stability",
        )
        return {
            "earnings_growth": earnings_growth,
            "dividend_stability": dividend_stability,
            "revenue_growth": revenue_growth,
        }

    @staticmethod
    def _validate_metric(value: float, metric_name: str = "metric") -> float:
        """Validate metric value and clamp negatives to zero.

        Args:
            value: Numeric value to validate (typically percentage-based).
            metric_name: Name of metric for logging purposes.

        Returns:
            Validated float value (>= 0.0, no upper limit to allow exceptional cases).
        """
        if value < 0:
            logger.debug("Negative value detected for %s (%.4f); clamping to 0.0", metric_name, value)
            return 0.0
        return value

    def fetch_historical_ohlcv(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data for a symbol.

        Args:
            symbol: NEPSE symbol.
            start_date: Optional start date.
            end_date: Optional end date.

        Returns:
            Normalized OHLCV DataFrame.
        """
        start = start_date or (date.today() - timedelta(days=365 * 5))
        end = end_date or date.today()
        cache_key = self._historical_cache_key(symbol=symbol, start_date=start, end_date=end)
        cached_history = self._historical_cache.get(cache_key)
        if isinstance(cached_history, pd.DataFrame):
            return cached_history.copy()

        payload = self._call_unofficial_client(
            "getCompanyPriceVolumeHistory",
            symbol=symbol.upper(),
            start_date=start,
            end_date=end,
        )
        rows = self._coerce_symbol_rows(payload)
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            raw_date = row.get("businessDate") or row.get("date") or row.get("tradeDate")
            if not raw_date:
                continue
            parsed_date = pd.to_datetime(raw_date, errors="coerce")
            if pd.isna(parsed_date):
                continue
            normalized.append(
                {
                    "date": parsed_date,
                    "symbol": symbol.upper(),
                    "open": row.get("openPrice") or row.get("open") or row.get("previousClose") or 0,
                    "high": row.get("highPrice") or row.get("high") or row.get("maxPrice") or 0,
                    "low": row.get("lowPrice") or row.get("low") or row.get("minPrice") or 0,
                    "close": row.get("closePrice") or row.get("close") or row.get("lastTradedPrice") or 0,
                    "volume": row.get("totalTradedQuantity")
                    or row.get("volume")
                    or row.get("totalTradeQuantity")
                    or row.get("tradeVolume")
                    or 0,
                    "turnover": row.get("totalTradedValue")
                    or row.get("totalTradeValue")
                    or row.get("turnover")
                    or row.get("totalTrades")
                    or row.get("tradeTurnover")
                    or 0,
                }
            )
        history_df = pd.DataFrame(normalized)
        if history_df.empty:
            self._historical_cache.set(cache_key, history_df.copy())
            return history_df
        for col in ["open", "high", "low", "close", "volume", "turnover"]:
            history_df[col] = pd.to_numeric(history_df[col], errors="coerce")
        history_df = history_df.dropna(subset=["date", "close"]).sort_values("date")
        out = history_df.reset_index(drop=True)
        self._historical_cache.set(cache_key, out.copy())
        return out

    def fetch_company_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Fetch and validate optional company fundamentals payload.

        Args:
            symbol: Stock symbol to fetch fundamentals for.

        Returns:
            Validated fundamentals dictionary or empty dict if unavailable.
        """
        try:
            if hasattr(self._unofficial_client, "getCompanyDetails"):
                payload = self._call_unofficial_client("getCompanyDetails", symbol=symbol.upper())
            else:
                logger.debug("getCompanyDetails method not available on client")
                return {}

            # Validate response structure
            if not isinstance(payload, dict):
                logger.warning("Fundamentals payload for %s is not a dict: %s", symbol, type(payload).__name__)
                return {}

            if not payload:
                logger.debug("Empty fundamentals payload for %s", symbol)
                return {}

            # Log available fields for debugging
            available_keys = [k for k in payload.keys() if k not in ["symbol", "companyName"]]
            logger.debug("Fundamentals for %s | available_fields=%d keys=%s", symbol, len(available_keys), available_keys[:5])

            return payload
        except Exception as exc:
            logger.debug("Failed to fetch fundamentals for %s: %s", symbol, exc)
            return {}

    def fetch_universe_with_history(
        self,
        lookback_years: int = 5,
        min_history_rows: int = 180,
        force_refresh: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch universe and historical data for qualifying symbols.

        Args:
            lookback_years: Number of years of history to request.
            min_history_rows: Minimum rows needed to retain symbol.
            force_refresh: If True, bypass local cache and fetch from API.

        Returns:
            Mapping of symbol to historical OHLCV DataFrame.
        """
        # Get the list of symbols to fetch
        try:
            try:
                snapshot = self.fetch_daily_market_snapshot(force_refresh=force_refresh)
            except TypeError:
                snapshot = self.fetch_daily_market_snapshot()
            symbols = snapshot["symbol"].dropna().unique().tolist() if not snapshot.empty else []
        except Exception as exc:
            logger.warning("Live snapshot unavailable for universe build, falling back to securities list: %s", exc)
            securities = self.fetch_symbols()
            symbols = securities["symbol"].dropna().unique().tolist() if not securities.empty else []
        
        sorted_symbols = sorted({str(symbol).upper() for symbol in symbols if symbol})

        # Load local history first, even on refresh, to avoid refetching symbols we already have on disk.
        universe: Dict[str, pd.DataFrame] = {}
        persistence = getattr(self, "_persistence", None)
        if persistence:
            logger.info("Attempting to load historical data from local storage")
            universe = persistence.load_universe(sorted_symbols)
            if universe:
                logger.info("Loaded %d symbols from local storage", len(universe))
        
        start = date.today() - timedelta(days=365 * lookback_years)
        end = date.today()
        settings = get_settings()
        max_workers = max(1, min(int(settings.market_parallel_workers), 2))

        if not sorted_symbols:
            return universe

        # Determine which symbols still need fetching.
        # Even on force refresh, reuse cached local history when available to reduce upstream pressure.
        symbols_to_fetch = [s for s in sorted_symbols if s not in universe]
        
        if symbols_to_fetch:
            logger.info(f"Fetching historical data for {len(symbols_to_fetch)} symbols from API")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_by_symbol: Dict[str, Future[pd.DataFrame]] = {
                    symbol: executor.submit(
                        self._fetch_historical_with_retry,
                        symbol,
                        start,
                        end,
                    )
                    for symbol in symbols_to_fetch
                }

                for symbol in symbols_to_fetch:
                    try:
                        hist = future_by_symbol[symbol].result()
                    except Exception as exc:
                        logger.warning("Skipping %s due to API error: %s", symbol, exc)
                        continue
                    
                    if len(hist) >= min_history_rows:
                        universe[symbol] = hist
                        # Save individual symbol to disk immediately
                        if persistence:
                            try:
                                persistence.save_historical(symbol, hist)
                            except Exception as exc:
                                logger.warning(f"Failed to persist historical data for {symbol}: {exc}")
        
        logger.info(f"Universe contains {len(universe)} symbols with sufficient history")
        return universe


# Backward compatibility alias while call sites migrate to coordinator/factory.
NepseDataFetcher = LegacyNepseDataFetcher
