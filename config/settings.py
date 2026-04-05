"""Application configuration and logging setup."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    nepse_api_base_url: str = os.getenv("NEPSE_API_BASE_URL", "")
    nepse_api_timeout: int = int(os.getenv("NEPSE_API_TIMEOUT", "15"))
    nepse_tls_verify: bool = os.getenv("NEPSE_TLS_VERIFY", "true").lower() in {"1", "true", "yes", "on"}
    api_retry_attempts: int = int(os.getenv("API_RETRY_ATTEMPTS", "2"))
    api_retry_backoff_seconds: float = float(os.getenv("API_RETRY_BACKOFF_SECONDS", "0.25"))
    market_parallel_workers: int = int(os.getenv("MARKET_PARALLEL_WORKERS", "8"))
    market_fetch_retry_attempts: int = int(os.getenv("MARKET_FETCH_RETRY_ATTEMPTS", "3"))
    market_fetch_retry_backoff_seconds: float = float(os.getenv("MARKET_FETCH_RETRY_BACKOFF_SECONDS", "0.20"))
    market_fetch_retry_jitter_seconds: float = float(os.getenv("MARKET_FETCH_RETRY_JITTER_SECONDS", "0.08"))
    cache_market_snapshot_ttl_seconds: float = float(os.getenv("CACHE_MARKET_SNAPSHOT_TTL_SECONDS", "30"))
    cache_historical_ttl_seconds: float = float(os.getenv("CACHE_HISTORICAL_TTL_SECONDS", "900"))
    cache_ranking_ttl_seconds: float = float(os.getenv("CACHE_RANKING_TTL_SECONDS", "90"))
    cache_max_entries: int = int(os.getenv("CACHE_MAX_ENTRIES", "5000"))
    bluechip_sector_relative: bool = os.getenv("BLUECHIP_SECTOR_RELATIVE", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    bluechip_normalization_mode: str = os.getenv("BLUECHIP_NORMALIZATION_MODE", "robust")
    bluechip_sector_blend: float = float(os.getenv("BLUECHIP_SECTOR_BLEND", "0.15"))
    bluechip_lower_quantile: float = float(os.getenv("BLUECHIP_LOWER_QUANTILE", "0.05"))
    bluechip_upper_quantile: float = float(os.getenv("BLUECHIP_UPPER_QUANTILE", "0.95"))

    data_cache_path: str = os.getenv("DATA_CACHE_PATH", "./data")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    third_party_log_level: str = os.getenv("THIRD_PARTY_LOG_LEVEL", "WARNING")
    suppress_unofficial_client_output: bool = os.getenv("SUPPRESS_UNOFFICIAL_CLIENT_OUTPUT", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return application settings singleton."""
    return Settings()


def setup_logging() -> None:
    """Configure root logger using LOG_LEVEL environment variable."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    third_party_level = getattr(logging, settings.third_party_log_level.upper(), logging.WARNING)
    for logger_name in ("httpx", "httpcore", "nepse_client", "urllib3"):
        logging.getLogger(logger_name).setLevel(third_party_level)
