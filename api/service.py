"""Service layer wrapping nepse_client for HTTP API exposure."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, cast

import pandas as pd
from nepse_client import NepseClient

from api.cache import TTLCache
from api.models import BlueChipRankingResponse, BlueChipRankingItem, ScoreBreakdown, FeatureImportance
from analysis.indicators import add_indicators
from bluechip.detector import BlueChipDetector, BlueChipScoringConfig
from candlestick.patterns import detect_patterns
from config.settings import get_settings
from market.market_scanner import MarketScanner
from nepse_api.factory import build_data_fetch_coordinator
from ranking.opportunity_ranker import rank_opportunities
from ranking.stock_ranker import build_ranked_views
from signals.signal_engine import build_trade_signal
from workflows.context import validate_positive_int, validate_symbol
from workflows.market_scan import MarketScanDependencies, run_market_scan_workflow
from workflows.market_backtest import MarketBacktestDependencies, run_market_backtest_workflow


class NepseApiService:
    """Wrapper around nepse_client methods used by HTTP endpoints."""

    RETRYABLE_EXCEPTIONS = {"TimeoutError", "ReadTimeout", "ConnectTimeout", "ConnectionError", "NepseNetworkError"}

    @staticmethod
    def _call(client: NepseClient, method_name: str, **kwargs: Any) -> Any:
        """Call NepseClient method by name with validation.

        Args:
            client: NepseClient instance.
            method_name: Method name to invoke.
            **kwargs: Keyword arguments for method.

        Returns:
            Raw method response payload.

        Raises:
            AttributeError: If method does not exist on installed library version.
        """
        method = getattr(client, method_name, None)
        if method is None:
            raise AttributeError(f"Installed nepse_client does not expose method: {method_name}")
        settings = get_settings()
        max_attempts = max(1, int(settings.api_retry_attempts))
        backoff_seconds = max(0.0, float(settings.api_retry_backoff_seconds))
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return method(**kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt >= max_attempts or not NepseApiService._should_retry_exception(exc):
                    raise
                sleep_for = backoff_seconds * attempt
                if sleep_for > 0:
                    time.sleep(sleep_for)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Failed to invoke method: {method_name}")

    @staticmethod
    def _should_retry_exception(exc: Exception) -> bool:
        """Return True when an upstream call is safe to retry."""
        if exc.__class__.__name__ in NepseApiService.RETRYABLE_EXCEPTIONS:
            return True
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int) and status_code in {408, 429, 500, 502, 503, 504}:
            return exc.__class__.__name__ not in {"RuntimeError"}
        return False

    @staticmethod
    def _coerce_rows(payload: Any) -> List[Dict[str, Any]]:
        """Normalize SDK payloads into list rows.

        Args:
            payload: Raw SDK payload that may be list or wrapped dict.

        Returns:
            List of dictionary rows.
        """
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("data", "result", "items", "content"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
        return []

    @staticmethod
    def _coerce_dict(payload: Any) -> Dict[str, Any]:
        """Normalize SDK payloads into dictionary shape."""
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _coerce_text(payload: Any) -> str:
        """Normalize SDK payloads into text shape."""
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload
        return str(payload)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Validate and normalize a stock symbol."""
        return validate_symbol(symbol)

    @staticmethod
    def _normalize_company_id(company_id: str) -> str:
        """Validate and normalize a company identifier."""
        normalized = str(company_id).strip()
        if not normalized:
            raise ValueError("company_id is required")
        return normalized

    @staticmethod
    def _normalize_business_date(business_date: str) -> str:
        """Validate and normalize an ISO business date string."""
        normalized = str(business_date).strip()
        if not normalized:
            raise ValueError("business_date is required")
        try:
            date.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("business_date must be in YYYY-MM-DD format") from exc
        return normalized

    @staticmethod
    def _validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> None:
        """Validate that an optional date range is ordered."""
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date must be <= end_date")

    @staticmethod
    def _normalize_page(value: Any, field_name: str, minimum: int = 1) -> int:
        """Validate and normalize pagination values."""
        return validate_positive_int(value, field_name, minimum)

    def __init__(self) -> None:
        settings = get_settings()
        self._client = NepseClient(timeout=float(settings.nepse_api_timeout))
        if hasattr(self._client, "setTLSVerification"):
            self._client.setTLSVerification(settings.nepse_tls_verify)
        self._coordinator = build_data_fetch_coordinator()
        self._caches = {
            "market_status": TTLCache(30.0),
            "market_summary": TTLCache(60.0),
            "nepse_index": TTLCache(60.0),
            "nepse_sub_indices": TTLCache(60.0),
            "companies": TTLCache(300.0),
            "securities": TTLCache(300.0),
            "company_details": TTLCache(300.0),
            "company_history": TTLCache(120.0),
            "company_financial_details": TTLCache(300.0),
            "company_agm": TTLCache(300.0),
            "company_dividend": TTLCache(300.0),
            "company_market_depth": TTLCache(120.0),
            "press_release": TTLCache(120.0),
            "nepse_notice": TTLCache(120.0),
            "holiday_list": TTLCache(3600.0),
            "price_volume_history": TTLCache(300.0),
            "company_id_key_map": TTLCache(3600.0),
            "security_id_key_map": TTLCache(3600.0),
            "sector_scrips": TTLCache(3600.0),
            "analytics_scan": TTLCache(120.0),
            "analytics_backtest": TTLCache(120.0),
        }

    def _analytics_output_dir(self) -> Path:
        """Return output directory used by workflow-backed analytics endpoints."""
        settings = get_settings()
        output_dir = Path(settings.data_cache_path) / "api" / "analytics"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _build_analytics_payload(self, top_n: int, sector_relative: bool) -> Dict[str, Any]:
        """Compute analytics payload by reusing the market scan workflow modules."""
        output_dir = self._analytics_output_dir() / f"scan_top_{top_n}_sector_{int(sector_relative)}"
        detector = BlueChipDetector(config=BlueChipScoringConfig(sector_relative=sector_relative))
        context = run_market_scan_workflow(
            dependencies=MarketScanDependencies(
                coordinator=self._coordinator,
                scanner=MarketScanner(),
                detector=detector,
                add_indicators_fn=add_indicators,
                detect_patterns_fn=detect_patterns,
                build_trade_signal_fn=build_trade_signal,
                rank_opportunities_fn=rank_opportunities,
                build_ranked_views_fn=build_ranked_views,
            ),
            output_dir=output_dir,
            top_n=top_n,
            plot=False,
        )
        signal_summary = context.signal_df.copy()
        summary_columns = [
            column
            for column in [
                "symbol",
                "signal",
                "confidence",
                "bluechip_score",
                "trade_score",
                "trade_score_rank",
                "confidence_rank",
                "bluechip_rank",
                "relative_trade_score",
                "trade_score_breakdown",
                "ranking_rationale",
            ]
            if column in signal_summary.columns
        ]

        return {
            "top_n": top_n,
            "sector_relative": sector_relative,
            "execution_id": context.execution_id,
            "generated_from": "workflows.market_scan.run_market_scan_workflow",
            "summary": context.to_summary(),
            "bluechip_ranking": context.bluechip_ranked.to_dict(orient="records"),
            "opportunities": context.signal_df.to_dict(orient="records"),
            "signal_summary": signal_summary[summary_columns].to_dict(orient="records"),
        }

    @staticmethod
    def _build_analytics_response(
        payload: Dict[str, Any],
        rows_key: str,
    ) -> Dict[str, Any]:
        """Build a uniform analytics response contract."""
        return {
            "top_n": payload["top_n"],
            "sector_relative": payload["sector_relative"],
            "execution_id": payload.get("execution_id", ""),
            "summary": payload.get("summary"),
            "rows": payload[rows_key],
        }

    def _analytics_payload(self, top_n: int, sector_relative: bool) -> Dict[str, Any]:
        """Return cached analytics payload for query parameters."""
        normalized_top_n = max(1, min(int(top_n), 200))
        normalized_sector_relative = bool(sector_relative)
        cache_key = self._cache_key(
            "analytics_scan",
            top_n=normalized_top_n,
            sector_relative=normalized_sector_relative,
        )
        cached_payload = self._caches["analytics_scan"].get(cache_key)
        if isinstance(cached_payload, dict):
            return cached_payload

        payload = self._build_analytics_payload(
            top_n=normalized_top_n,
            sector_relative=normalized_sector_relative,
        )
        self._caches["analytics_scan"].set(cache_key, payload)
        return payload

    def analytics_bluechip_ranking(self, top_n: int = 20, sector_relative: bool = False) -> Dict[str, Any]:
        """Return workflow-backed blue-chip ranking output."""
        return self._build_analytics_response(
            self._analytics_payload(top_n=top_n, sector_relative=sector_relative),
            "bluechip_ranking",
        )

    def analytics_opportunities(self, top_n: int = 20, sector_relative: bool = False) -> Dict[str, Any]:
        """Return workflow-backed ranked opportunities output."""
        return self._build_analytics_response(
            self._analytics_payload(top_n=top_n, sector_relative=sector_relative),
            "opportunities",
        )

    def analytics_signal_summary(self, top_n: int = 20, sector_relative: bool = False) -> Dict[str, Any]:
        """Return workflow-backed signal summary output."""
        return self._build_analytics_response(
            self._analytics_payload(top_n=top_n, sector_relative=sector_relative),
            "signal_summary",
        )

    def analytics_backtest_summary(
        self,
        top_n: int = 20,
        lookback_days: int = 252,
        rebalance: str = "static",
        sector_relative: bool = False,
    ) -> Dict[str, Any]:
        """Return workflow-backed market backtest summary and validation payload."""
        normalized_top_n = max(1, min(int(top_n), 200))
        normalized_lookback_days = max(1, min(int(lookback_days), 2000))
        normalized_rebalance = str(rebalance).strip().lower()
        normalized_sector_relative = bool(sector_relative)

        cache_key = self._cache_key(
            "analytics_backtest",
            top_n=normalized_top_n,
            lookback_days=normalized_lookback_days,
            rebalance=normalized_rebalance,
            sector_relative=normalized_sector_relative,
        )
        cached_payload = self._caches["analytics_backtest"].get(cache_key)
        if isinstance(cached_payload, dict):
            return cached_payload

        output_dir = self._analytics_output_dir() / (
            f"backtest_top_{normalized_top_n}"
            f"_lookback_{normalized_lookback_days}"
            f"_rebalance_{normalized_rebalance}"
            f"_sector_{int(normalized_sector_relative)}"
        )
        detector = BlueChipDetector(config=BlueChipScoringConfig(sector_relative=normalized_sector_relative))
        context = run_market_backtest_workflow(
            dependencies=MarketBacktestDependencies(
                coordinator=self._coordinator,
                scanner=MarketScanner(),
                detector=detector,
                add_indicators_fn=add_indicators,
                detect_patterns_fn=detect_patterns,
                build_trade_signal_fn=build_trade_signal,
                rank_opportunities_fn=rank_opportunities,
            ),
            output_dir=output_dir,
            top_n=normalized_top_n,
            lookback_days=normalized_lookback_days,
            rebalance=normalized_rebalance,
        )

        payload = {
            "top_n": normalized_top_n,
            "lookback_days": normalized_lookback_days,
            "rebalance": normalized_rebalance,
            "sector_relative": normalized_sector_relative,
            "execution_id": context.execution_id,
            "summary": context.to_summary(),
            "historical_validation": context.historical_validation,
            "portfolio_metrics": context.portfolio_metrics,
        }
        self._caches["analytics_backtest"].set(cache_key, payload)
        return payload

    def build_bluechip_ranking_response(
        self, bluechip_ranked: pd.DataFrame, sector_relative: bool = False, top_n: int = 20
    ) -> BlueChipRankingResponse:
        """Build structured blue-chip ranking response with score breakdowns and explainability.

        Args:
            bluechip_ranked: Scored dataframe from BlueChipDetector.score_bluechips()
            sector_relative: Whether sector-relative scoring was used
            top_n: Target number for top selected stocks

        Returns:
            Typed BlueChipRankingResponse with score breakdown for each stock.
        """
        if bluechip_ranked.empty:
            return BlueChipRankingResponse(
                top_n=top_n,
                sector_relative=sector_relative,
                generated_from="api.service.build_bluechip_ranking_response",
                feature_importance=FeatureImportance(
                    market_cap=0.30, volume=0.20, stability=0.20, trend=0.20, fundamental=0.10
                ),
                ranking=[],
                sector_summary=[],
            )

        ranking_items = []
        for _, row in bluechip_ranked.iterrows():
            # Extract score breakdown or build from components
            score_breakdown_dict = row.get("score_breakdown", {})
            if isinstance(score_breakdown_dict, dict) and score_breakdown_dict:
                # Use provided breakdown dict if not empty
                try:
                    breakdown = ScoreBreakdown(**score_breakdown_dict)
                except (TypeError, ValueError):
                    # Fallback to component scores if dict is malformed
                    breakdown = ScoreBreakdown(
                        market_cap=float(row.get("market_cap_score", 0.0)),
                        volume=float(row.get("volume_score", 0.0)),
                        stability=float(row.get("stability_score", 0.0)),
                        trend=float(row.get("trend_score", 0.0)),
                        fundamental=float(row.get("fundamental_score", 0.0)),
                        sector=float(row.get("sector_score", 0.5)),
                    )
            else:
                # Fallback: compute from individual scores if breakdown not present or empty
                breakdown = ScoreBreakdown(
                    market_cap=float(row.get("market_cap_score", 0.0)),
                    volume=float(row.get("volume_score", 0.0)),
                    stability=float(row.get("stability_score", 0.0)),
                    trend=float(row.get("trend_score", 0.0)),
                    fundamental=float(row.get("fundamental_score", 0.0)),
                    sector=float(row.get("sector_score", 0.5)),
                )

            item = BlueChipRankingItem(
                rank=int(row.get("rank", 0)),
                symbol=str(row.get("symbol", "")),
                sector=str(row.get("sector", "Unknown")),
                bluechip_score=float(row.get("bluechip_score", 0.0)),
                base_bluechip_score=float(row.get("base_bluechip_score", 0.0)),
                score_breakdown=breakdown,
                market_cap=float(row.get("market_cap", 0.0)),
                avg_volume=float(row.get("avg_volume", 0.0)),
                volatility=float(row.get("volatility", 0.0)),
                cagr=float(row.get("cagr", 0.0)),
                fundamental_strength=float(row.get("fundamental_strength", 0.0)),
            )
            ranking_items.append(item)

        # Build feature importance from detector config if possible
        detector = BlueChipDetector(config=BlueChipScoringConfig(sector_relative=sector_relative))
        importance_dict = detector.get_feature_importance()
        feature_importance = FeatureImportance(**importance_dict)

        # Optional: compute sector summary
        sector_summary = []
        if "sector" in bluechip_ranked.columns and not bluechip_ranked.empty:
            grouped = bluechip_ranked.groupby("sector", dropna=False)["bluechip_score"].agg(["mean", "max", "count"])
            for sector, row_data in grouped.iterrows():
                sector_summary.append(
                    {
                        "sector": str(sector),
                        "mean_score": float(row_data["mean"]),
                        "max_score": float(row_data["max"]),
                        "count": int(row_data["count"]),
                    }
                )

        return BlueChipRankingResponse(
            top_n=top_n,
            sector_relative=sector_relative,
            generated_from="api.service.build_bluechip_ranking_response",
            feature_importance=feature_importance,
            ranking=ranking_items,
            sector_summary=sector_summary if sector_summary else None,
        )

    def _cache_key(self, method_name: str, **kwargs: Any) -> str:
        """Build stable cache key for a method invocation."""
        parts = [method_name]
        for key in sorted(kwargs):
            parts.append(f"{key}={kwargs[key]!r}")
        return "|".join(parts)

    def _call_cached(self, cache_name: str, method_name: str, **kwargs: Any) -> Any:
        """Call method using a TTL cache when configured."""
        cache = self._caches.get(cache_name)
        cache_key = self._cache_key(method_name, **kwargs)
        if cache is not None:
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

        result = self._call(self._client, method_name, **kwargs)
        if cache is not None:
            cache.set(cache_key, result)
        return result

    def health(self) -> Dict[str, Any]:
        """Return lightweight API health information."""
        status = self._call(self._client, "getMarketStatus")
        return {
            "ok": True,
            "marketStatus": status,
        }

    def market_status(self) -> Dict[str, Any]:
        """Return market open/closed status payload."""
        return self._coerce_dict(self._call_cached("market_status", "getMarketStatus"))

    def market_summary(self) -> Dict[str, Any]:
        """Return market summary payload."""
        return self._coerce_dict(self._call_cached("market_summary", "getSummary"))

    def nepse_index(self) -> Any:
        """Return NEPSE index payload."""
        return self._coerce_rows(self._call_cached("nepse_index", "getNepseIndex"))

    def nepse_sub_indices(self) -> Any:
        """Return NEPSE sub-indices payload."""
        return self._coerce_rows(self._call_cached("nepse_sub_indices", "getNepseSubIndices"))

    def live_market(self) -> List[Dict[str, Any]]:
        """Return live market rows."""
        snapshot_df = self._coordinator.get_market_snapshot(force_refresh=False)
        if snapshot_df.empty:
            return []
        return cast(List[Dict[str, Any]], snapshot_df.to_dict(orient="records"))

    def price_volume(self) -> Any:
        """Return price-volume payload."""
        return self._coerce_rows(self._call(self._client, "getPriceVolume"))

    def supply_demand(self) -> Any:
        """Return supply-demand payload."""
        return self._coerce_dict(self._call(self._client, "getSupplyDemand"))

    def top_gainers(self) -> List[Dict[str, Any]]:
        """Return top gainers rows."""
        return self._coerce_rows(self._call(self._client, "getTopGainers"))

    def top_losers(self) -> List[Dict[str, Any]]:
        """Return top losers rows."""
        return self._coerce_rows(self._call(self._client, "getTopLosers"))

    def top_ten_trade_scrips(self) -> List[Dict[str, Any]]:
        """Return top ten trade scrip rows."""
        return self._coerce_rows(self._call(self._client, "getTopTenTradeScrips"))

    def top_ten_transaction_scrips(self) -> List[Dict[str, Any]]:
        """Return top ten transaction scrip rows."""
        return self._coerce_rows(self._call(self._client, "getTopTenTransactionScrips"))

    def top_ten_turnover_scrips(self) -> List[Dict[str, Any]]:
        """Return top ten turnover scrip rows."""
        return self._coerce_rows(self._call(self._client, "getTopTenTurnoverScrips"))

    def companies(self) -> List[Dict[str, Any]]:
        """Return company list."""
        return self._coerce_rows(self._call_cached("companies", "getCompanyList"))

    def securities(self) -> List[Dict[str, Any]]:
        """Return security list."""
        return self._coerce_rows(self._call_cached("securities", "getSecurityList"))

    def company_details(self, symbol: str) -> Dict[str, Any]:
        """Return company details for a symbol."""
        normalized_symbol = self._normalize_symbol(symbol)
        return self._coerce_dict(
            self._call_cached("company_details", "getCompanyDetails", symbol=normalized_symbol)
        )

    def company_history(
        self,
        symbol: str,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        """Return company price-volume history for date range."""
        normalized_symbol = self._normalize_symbol(symbol)
        self._validate_date_range(start_date, end_date)
        history_df = self._coordinator.get_historical(
            symbol=normalized_symbol,
            start=start_date,
            end=end_date,
            force_refresh=False,
        )
        if history_df.empty:
            return []
        return cast(List[Dict[str, Any]], history_df.to_dict(orient="records"))

    def daily_scrip_price_graph(self, symbol: str) -> Any:
        """Return daily scrip price graph payload."""
        return self._call(self._client, "getDailyScripPriceGraph", symbol=self._normalize_symbol(symbol))

    def company_financial_details(self, company_id: str) -> Any:
        """Return company financial details payload."""
        normalized_company_id = self._normalize_company_id(company_id)
        return self._coerce_rows(
            self._call_cached("company_financial_details", "getCompanyFinancialDetails", company_id=normalized_company_id)
        )

    def company_agm(self, company_id: str) -> Any:
        """Return company AGM payload."""
        normalized_company_id = self._normalize_company_id(company_id)
        return self._coerce_rows(self._call_cached("company_agm", "getCompanyAGM", company_id=normalized_company_id))

    def company_dividend(self, company_id: str) -> Any:
        """Return company dividend payload."""
        normalized_company_id = self._normalize_company_id(company_id)
        return self._coerce_rows(
            self._call_cached("company_dividend", "getCompanyDividend", company_id=normalized_company_id)
        )

    def company_market_depth(self, company_id: str) -> Any:
        """Return company market depth payload."""
        normalized_company_id = self._normalize_company_id(company_id)
        return self._coerce_rows(
            self._call_cached("company_market_depth", "getCompanyMarketDepth", company_id=normalized_company_id)
        )

    def floor_sheet(self, show_progress: bool = False) -> Any:
        """Return floor sheet payload."""
        return self._coerce_rows(self._call(self._client, "getFloorSheet", show_progress=show_progress))

    def floor_sheet_of(self, symbol: str, business_date: str) -> Any:
        """Return floor sheet payload for one symbol/date."""
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_business_date = self._normalize_business_date(business_date)
        return self._coerce_rows(self._call(
            self._client,
            "getFloorSheetOf",
            symbol=normalized_symbol,
            business_date=normalized_business_date,
        ))

    def trading_average(self, business_date: str, n_days: int = 180) -> Any:
        """Return trading average payload."""
        normalized_business_date = self._normalize_business_date(business_date)
        normalized_n_days = validate_positive_int(n_days, "n_days")
        return self._coerce_rows(
            self._call(self._client, "getTradingAverage", business_date=normalized_business_date, nDays=normalized_n_days)
        )

    def symbol_market_depth(self, symbol: str) -> Any:
        """Return symbol market depth payload."""
        return self._coerce_text(self._call(self._client, "getSymbolMarketDepth", symbol=self._normalize_symbol(symbol)))

    def company_news_list(self, page: int = 1, page_size: int = 100, is_strip_tags: bool = True) -> Any:
        """Return company news list payload."""
        normalized_page = self._normalize_page(page, "page")
        normalized_page_size = self._normalize_page(page_size, "page_size")
        return self._call(
            self._client,
            "getCompanyNewsList",
            page=normalized_page,
            page_size=normalized_page_size,
            is_strip_tags=is_strip_tags,
        )

    def news_alert_list(self, page: int = 1, page_size: int = 100, is_strip_tags: bool = True) -> Any:
        """Return news and alert list payload."""
        normalized_page = self._normalize_page(page, "page")
        normalized_page_size = self._normalize_page(page_size, "page_size")
        return self._call(
            self._client,
            "getNewsAndAlertList",
            page=normalized_page,
            page_size=normalized_page_size,
            is_strip_tags=is_strip_tags,
        )

    def press_release(self) -> Any:
        """Return press release payload."""
        return self._coerce_dict(self._call_cached("press_release", "getPressRelease"))

    def nepse_notice(self, page: int = 0) -> Any:
        """Return NEPSE notice payload."""
        normalized_page = self._normalize_page(page, "page", minimum=0)
        return self._coerce_dict(self._call_cached("nepse_notice", "getNepseNotice", page=normalized_page))

    def holiday_list(self, year: int) -> Any:
        """Return holiday list payload for year."""
        return self._coerce_rows(self._call_cached("holiday_list", "getHolidayList", year=year))

    def debenture_bond_list(self, instrument_type: str) -> Any:
        """Return debenture/bond list payload."""
        return self._call(self._client, "getDebentureAndBondList", bond_type=instrument_type)

    def price_volume_history(self, business_date: str) -> Any:
        """Return price-volume history payload for date."""
        return self._coerce_rows(
            self._call_cached("price_volume_history", "getPriceVolumeHistory", business_date=business_date)
        )

    def company_id_key_map(self, force_update: bool = False) -> Any:
        """Return company ID key map payload."""
        return self._coerce_dict(
            self._call_cached("company_id_key_map", "getCompanyIDKeyMap", force_update=force_update)
        )

    def security_id_key_map(self, force_update: bool = False) -> Any:
        """Return security ID key map payload."""
        return self._coerce_dict(
            self._call_cached("security_id_key_map", "getSecurityIDKeyMap", force_update=force_update)
        )

    def sector_scrips(self) -> Any:
        """Return sector-wise scrip mapping payload."""
        return self._coerce_dict(self._call_cached("sector_scrips", "getSectorScrips"))

    def cache_stats(self) -> Dict[str, Dict[str, int]]:
        """Return cache hit/miss statistics."""
        return {name: cache.snapshot() for name, cache in self._caches.items()}
