from __future__ import annotations

"""Factory helpers for constructing data fetch coordinator components."""

from nepse_client import NepseClient

from config.settings import get_settings
from nepse_api.coordinator import DataFetchCoordinator
from nepse_api.data_persistence import DataPersistence
from nepse_api.normalizers import HistoricalNormalizer, SnapshotNormalizer
from nepse_api.providers import (
    NepseClientProvider,
    PersistedHistoryProvider,
    PersistedSnapshotProvider,
    RetryPolicy,
)


def build_data_fetch_coordinator() -> DataFetchCoordinator:
    """Build a fully wired DataFetchCoordinator from app settings."""
    settings = get_settings()

    client = NepseClient(timeout=float(settings.nepse_api_timeout))
    if hasattr(client, "setTLSVerification"):
        client.setTLSVerification(settings.nepse_tls_verify)

    remote = NepseClientProvider(
        client=client,
        retry=RetryPolicy(
            attempts=max(1, int(settings.market_fetch_retry_attempts)),
            backoff_seconds=max(0.0, float(settings.market_fetch_retry_backoff_seconds)),
            jitter_seconds=max(0.0, float(settings.market_fetch_retry_jitter_seconds)),
        ),
        suppress_output=bool(settings.suppress_unofficial_client_output),
    )

    persistence = DataPersistence(base_dir=f"{settings.data_cache_path}/datasets")
    snapshot_repo = PersistedSnapshotProvider(persistence=persistence)
    history_repo = PersistedHistoryProvider(persistence=persistence)

    return DataFetchCoordinator(
        remote=remote,
        snapshot_repo=snapshot_repo,
        history_repo=history_repo,
        snapshot_normalizer=SnapshotNormalizer(),
        history_normalizer=HistoricalNormalizer(),
    )
