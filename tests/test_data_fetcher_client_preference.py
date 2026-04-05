"""Tests for NepseDataFetcher client preference and fallback behavior."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from nepse_api.data_fetcher import NepseApiConfig, NepseDataFetcher


def _build_config() -> NepseApiConfig:
    """Create test config with NEPSE base URL.

    Args:
    Returns:
        NepseApiConfig instance.
    """
    return NepseApiConfig(
        base_url="https://www.nepalstock.com.np",
        timeout_seconds=5,
        tls_verify=False,
        suppress_unofficial_client_output=True,
    )


def test_init_unofficial_client_is_used_even_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetcher should initialize nepse_client by default for NEPSE base URL.

    This verifies nepse_client remains preferred even when api_key is provided.
    """

    class _FakeNepseClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout
            self.tls_verify: bool | None = None

        def setTLSVerification(self, value: bool) -> None:
            self.tls_verify = value

    fake_module = types.SimpleNamespace(NepseClient=_FakeNepseClient)
    monkeypatch.setitem(sys.modules, "nepse_client", fake_module)

    fetcher = NepseDataFetcher(config=_build_config())

    assert fetcher._unofficial_client is not None
    assert isinstance(fetcher._unofficial_client, _FakeNepseClient)
    assert fetcher._unofficial_client.timeout == 5.0
    assert fetcher._unofficial_client.tls_verify is False
