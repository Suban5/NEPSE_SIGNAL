"""Blue-chip stock detection and scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from config.settings import get_settings


@dataclass
class BlueChipWeights:
    """Weights for blue-chip score components."""

    market_cap: float = 0.30
    volume: float = 0.20
    stability: float = 0.20
    trend: float = 0.20
    fundamental: float = 0.10

    def __post_init__(self) -> None:
        """Validate weight configuration."""
        weights = [self.market_cap, self.volume, self.stability, self.trend, self.fundamental]
        if any(weight < 0 for weight in weights):
            raise ValueError("Blue-chip weights must be non-negative")
        total = sum(weights)
        if not np.isclose(total, 1.0, atol=1e-6):
            raise ValueError(f"Blue-chip weights must sum to 1.0, got {total:.6f}")


@dataclass(frozen=True)
class BlueChipScoringConfig:
    """Configuration for blue-chip scoring behavior."""

    normalization_mode: str = "robust"
    sector_relative: bool = False
    sector_blend: float = 0.15
    lower_quantile: float = 0.05
    upper_quantile: float = 0.95

    def __post_init__(self) -> None:
        """Validate scoring config values."""
        mode = self.normalization_mode.lower().strip()
        if mode not in {"robust", "minmax"}:
            raise ValueError("normalization_mode must be one of: robust, minmax")
        if not 0.0 <= self.sector_blend <= 1.0:
            raise ValueError("sector_blend must be between 0 and 1")
        if not 0.0 < self.lower_quantile < self.upper_quantile < 1.0:
            raise ValueError("lower_quantile and upper_quantile must satisfy 0 < lower < upper < 1")


class BlueChipDetector:
    """Computes quantitative blue-chip scores from market data."""

    SCORE_COLUMN = "bluechip_score"

    def __init__(
        self,
        weights: Optional[BlueChipWeights] = None,
        config: Optional[BlueChipScoringConfig] = None,
    ) -> None:
        """Initialize detector with optional custom weights."""
        settings = get_settings()
        self.weights = weights or BlueChipWeights()
        self.config = config or BlueChipScoringConfig(
            normalization_mode=settings.bluechip_normalization_mode,
            sector_relative=settings.bluechip_sector_relative,
            sector_blend=settings.bluechip_sector_blend,
            lower_quantile=settings.bluechip_lower_quantile,
            upper_quantile=settings.bluechip_upper_quantile,
        )

    @staticmethod
    def _normalize_minmax(series: pd.Series) -> pd.Series:
        """Min-max normalize values into [0, 1]."""
        series = series.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        min_val = series.min()
        max_val = series.max()
        if np.isclose(max_val - min_val, 0.0):
            return pd.Series(0.5, index=series.index)
        return (series - min_val) / (max_val - min_val)

    def _normalize_robust(self, series: pd.Series) -> pd.Series:
        """Winsorized min-max normalization using configured quantiles."""
        clean = series.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        lower = clean.quantile(self.config.lower_quantile)
        upper = clean.quantile(self.config.upper_quantile)
        clipped = clean.clip(lower=lower, upper=upper)
        return self._normalize_minmax(clipped)

    def _normalize(self, series: pd.Series) -> pd.Series:
        """Normalize using the configured scaling strategy."""
        mode = self.config.normalization_mode.lower().strip()
        if mode == "minmax":
            return self._normalize_minmax(series)
        return self._normalize_robust(series)

    @staticmethod
    def _compute_cagr(close_series: pd.Series, periods_per_year: int = 252) -> float:
        """Compute compound annual growth rate from close prices."""
        clean = close_series.dropna()
        if len(clean) < 2 or clean.iloc[0] <= 0:
            return 0.0
        total_periods = len(clean) - 1
        years = max(total_periods / periods_per_year, 1e-6)
        return (clean.iloc[-1] / clean.iloc[0]) ** (1 / years) - 1

    @staticmethod
    def _compute_volatility(close_series: pd.Series, periods_per_year: int = 252) -> float:
        """Compute annualized volatility from daily returns."""
        returns = close_series.pct_change().dropna()
        if returns.empty:
            return np.nan
        return float(returns.std(ddof=0) * np.sqrt(periods_per_year))

    @staticmethod
    def _sector_relative_scale(values: pd.Series, sectors: pd.Series) -> pd.Series:
        """Scale values within each sector into [0, 1]."""
        if values.empty:
            return values

        scaled = pd.Series(index=values.index, dtype=float)
        for sector in sectors.fillna("Unknown").astype(str).unique():
            mask = sectors.fillna("Unknown").astype(str) == sector
            sector_values = values.loc[mask]
            if sector_values.empty:
                continue
            if len(sector_values) == 1:
                scaled.loc[mask] = 0.5
                continue
            sector_min = sector_values.min()
            sector_max = sector_values.max()
            if np.isclose(sector_max - sector_min, 0.0):
                scaled.loc[mask] = 0.5
            else:
                scaled.loc[mask] = (sector_values - sector_min) / (sector_max - sector_min)
        return scaled.fillna(0.5)

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        """Convert scalar-like values to float with safe fallback.

        Args:
            value: Input value from market snapshot/fundamentals.
            default: Fallback when value cannot be converted.

        Returns:
            Float value or default.
        """
        if isinstance(value, pd.Series):
            if value.empty:
                return default
            value = value.iloc[-1]

        if value is None:
            return default

        if isinstance(value, (int, float, np.integer, np.floating)):
            parsed = float(value)
        elif isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return default
            try:
                parsed = float(candidate)
            except ValueError:
                return default
        else:
            return default

        if np.isnan(parsed) or np.isinf(parsed):
            return default
        return parsed

    def build_feature_table(
        self,
        market_snapshot: pd.DataFrame,
        historical_data: Dict[str, pd.DataFrame],
        fundamentals: Optional[Dict[str, dict]] = None,
    ) -> pd.DataFrame:
        """Create feature table for blue-chip scoring.

        Args:
            market_snapshot: Snapshot containing market-cap and sector fields.
            historical_data: Historical OHLCV per symbol.
            fundamentals: Optional fundamentals mapping per symbol.

        Returns:
            Feature DataFrame used for scoring.
        """
        fundamentals = fundamentals or {}
        rows = []
        snapshot_indexed = market_snapshot.set_index("symbol", drop=False)

        for symbol, history_df in historical_data.items():
            if history_df.empty or symbol not in snapshot_indexed.index:
                continue
            latest_value = snapshot_indexed.loc[symbol]
            latest = latest_value.iloc[-1] if isinstance(latest_value, pd.DataFrame) else latest_value
            volatility = self._compute_volatility(history_df["close"])
            cagr = self._compute_cagr(history_df["close"])
            avg_volume = float(history_df["volume"].tail(120).mean())
            avg_turnover = float(history_df.get("turnover", pd.Series(dtype=float)).tail(120).mean())

            fundamental = fundamentals.get(symbol, {})
            earnings_growth = float(fundamental.get("earnings_growth", 0.0) or 0.0)
            dividend_stability = float(fundamental.get("dividend_stability", 0.0) or 0.0)
            revenue_growth = float(fundamental.get("revenue_growth", 0.0) or 0.0)
            fundamental_strength = np.mean([earnings_growth, dividend_stability, revenue_growth])

            rows.append(
                {
                    "symbol": symbol,
                    "sector": latest.get("sector", "Unknown"),
                    "market_cap": self._to_float(latest.get("market_cap", 0.0), default=0.0),
                    "avg_volume": avg_volume,
                    "avg_turnover": avg_turnover,
                    "volatility": volatility,
                    "cagr": cagr,
                    "fundamental_strength": float(fundamental_strength),
                }
            )
        return pd.DataFrame(rows)

    def get_feature_importance(self) -> Dict[str, float]:
        """Return configured feature importance weights."""
        return {
            "market_cap": self.weights.market_cap,
            "volume": self.weights.volume,
            "stability": self.weights.stability,
            "trend": self.weights.trend,
            "fundamental": self.weights.fundamental,
        }

    def build_scoring_report(self, scored: pd.DataFrame) -> Dict[str, Any]:
        """Build a structured scoring report for validation and explainability."""
        if scored.empty:
            return {
                "feature_importance": self.get_feature_importance(),
                "symbol_breakdown": [],
                "sector_summary": {},
            }

        breakdown_columns = [
            "symbol",
            "sector",
            "bluechip_score",
            "base_bluechip_score",
            "market_cap_score",
            "volume_score",
            "stability_score",
            "trend_score",
            "fundamental_score",
            "sector_score",
            "rank",
        ]
        available_columns = [column for column in breakdown_columns if column in scored.columns]
        sector_summary = (
            scored.groupby("sector", dropna=False)["bluechip_score"].agg(["mean", "max", "count"]).reset_index().to_dict(orient="records")
            if "sector" in scored.columns
            else {}
        )
        return {
            "feature_importance": self.get_feature_importance(),
            "symbol_breakdown": scored[available_columns].to_dict(orient="records"),
            "sector_summary": sector_summary,
        }

    @classmethod
    def get_symbol_score(cls, scored: pd.DataFrame, symbol: str, default: float = 0.0) -> float:
        """Return canonical blue-chip score for a symbol from scored output."""
        if scored.empty or "symbol" not in scored.columns or cls.SCORE_COLUMN not in scored.columns:
            return float(default)
        match = scored.loc[scored["symbol"] == symbol, cls.SCORE_COLUMN]
        if match.empty:
            return float(default)
        return float(match.iloc[0])

    @classmethod
    def select_top_symbols(cls, scored: pd.DataFrame, top_n: int) -> list[str]:
        """Return top-N symbols ordered by canonical blue-chip score."""
        if scored.empty or "symbol" not in scored.columns or cls.SCORE_COLUMN not in scored.columns:
            return []
        ranked = scored.sort_values(cls.SCORE_COLUMN, ascending=False).head(int(top_n))
        return ranked["symbol"].astype(str).tolist()

    @classmethod
    def merge_bluechip_scores(cls, signal_df: pd.DataFrame, bluechip_df: pd.DataFrame) -> pd.DataFrame:
        """Attach canonical blue-chip score and core rank fields to signal rows."""
        if signal_df.empty:
            return signal_df.copy()
        if bluechip_df.empty or "symbol" not in signal_df.columns or "symbol" not in bluechip_df.columns:
            return signal_df.copy()

        bluechip_columns = [
            column
            for column in ["symbol", cls.SCORE_COLUMN, "volatility", "cagr", "rank"]
            if column in bluechip_df.columns
        ]
        merged = signal_df.merge(
            bluechip_df[bluechip_columns],
            on="symbol",
            how="left",
            suffixes=("", "_bluechip"),
        )
        bluechip_shadow_column = f"{cls.SCORE_COLUMN}_bluechip"
        if cls.SCORE_COLUMN not in merged.columns and bluechip_shadow_column in merged.columns:
            merged[cls.SCORE_COLUMN] = merged[bluechip_shadow_column]
        elif bluechip_shadow_column in merged.columns:
            merged[cls.SCORE_COLUMN] = merged[cls.SCORE_COLUMN].fillna(merged[bluechip_shadow_column])
        return merged

    def score_bluechips(self, features: pd.DataFrame) -> pd.DataFrame:
        """Compute weighted blue-chip score and ranking."""
        if features.empty:
            return features

        scored = features.copy()
        scored["market_cap_score"] = self._normalize(scored["market_cap"])
        liquidity_proxy = scored["avg_volume"].fillna(0) * 0.7 + scored["avg_turnover"].fillna(0) * 0.3
        scored["volume_score"] = self._normalize(liquidity_proxy)
        scored["stability_score"] = 1.0 - self._normalize(scored["volatility"].fillna(scored["volatility"].median()))
        scored["trend_score"] = self._normalize(scored["cagr"])
        scored["fundamental_score"] = self._normalize(scored.get("fundamental_strength", pd.Series(0.0, index=scored.index)))

        scored["base_bluechip_score"] = (
            self.weights.market_cap * scored["market_cap_score"]
            + self.weights.volume * scored["volume_score"]
            + self.weights.stability * scored["stability_score"]
            + self.weights.trend * scored["trend_score"]
            + self.weights.fundamental * scored["fundamental_score"]
        )

        if self.config.sector_relative and "sector" in scored.columns:
            scored["sector_score"] = self._sector_relative_scale(scored["base_bluechip_score"], scored["sector"])
            scored[self.SCORE_COLUMN] = (
                (1.0 - self.config.sector_blend) * scored["base_bluechip_score"]
                + self.config.sector_blend * scored["sector_score"]
            )
        else:
            scored["sector_score"] = 0.5
            scored[self.SCORE_COLUMN] = scored["base_bluechip_score"]

        scored["score_breakdown"] = scored.apply(
            lambda row: {
                "market_cap": float(row["market_cap_score"]),
                "volume": float(row["volume_score"]),
                "stability": float(row["stability_score"]),
                "trend": float(row["trend_score"]),
                "fundamental": float(row["fundamental_score"]),
                "sector": float(row["sector_score"]),
            },
            axis=1,
        )
        scored = scored.sort_values(self.SCORE_COLUMN, ascending=False).reset_index(drop=True)
        scored["rank"] = np.arange(1, len(scored) + 1)
        return scored
