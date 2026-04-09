"""Streamlit dashboard for NepseSignal read-only UI.

Implemented scopes:
- C1: Page shell and tab layout
- C3: API-backed panel components
- C5: Version negotiation and contract diagnostics

The UI performs no business logic and only renders API responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Final

from dotenv import load_dotenv
import streamlit as st
from ui.api_client import ApiClient, ApiClientConfig, ApiClientError
from ui.components import backtest, explorer, metrics, opportunities, rankings, signals


logger = logging.getLogger(__name__)

APP_TITLE: Final[str] = "NepseSignal Dashboard"
APP_ICON: Final[str] = "📈"
DEFAULT_API_VERSION: Final[str] = "v1"
SUPPORTED_API_VERSIONS: Final[tuple[str, ...]] = ("v1", "v2")


def _init_page() -> None:
    """Initialize static Streamlit page configuration."""
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def _init_state() -> None:
    """Initialize session state used by shell-only UI placeholders."""
    if "ui_last_refresh_utc" not in st.session_state:
        st.session_state["ui_last_refresh_utc"] = datetime.now(timezone.utc)
    if "ui_health_status" not in st.session_state:
        st.session_state["ui_health_status"] = "Not Fetched"
    if "ui_api_version" not in st.session_state:
        st.session_state["ui_api_version"] = DEFAULT_API_VERSION
    if "ui_contract_diagnostics" not in st.session_state:
        st.session_state["ui_contract_diagnostics"] = None


def _build_api_client() -> ApiClient:
    """Build API client from environment configuration."""
    base_url = os.getenv("NEPSE_UI_API_BASE_URL", "http://localhost:8000").strip() or "http://localhost:8000"
    timeout_seconds = float(os.getenv("NEPSE_UI_TIMEOUT_SECONDS", "10"))
    max_attempts = int(os.getenv("NEPSE_UI_MAX_ATTEMPTS", "3"))
    backoff_seconds = float(os.getenv("NEPSE_UI_BACKOFF_SECONDS", "0.5"))
    default_api_version = os.getenv("NEPSE_UI_DEFAULT_API_VERSION", DEFAULT_API_VERSION).strip().lower() or DEFAULT_API_VERSION

    config = ApiClientConfig(
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        default_api_version=default_api_version,
    )
    return ApiClient(config=config)


def _render_contract_diagnostics(client: ApiClient, api_version: str) -> None:
    """Render contract/version diagnostics from /contracts endpoint."""
    refresh_clicked = st.button("Refresh Contract Diagnostics", key="contract_diag_refresh")
    diagnostics = st.session_state.get("ui_contract_diagnostics")

    if diagnostics is None or refresh_clicked:
        try:
            response = client.contracts(api_version=api_version)
        except ApiClientError as exc:
            st.warning(
                "Contract diagnostics unavailable. "
                f"endpoint={exc.endpoint}, status={exc.status_code}, request_id={exc.request_id}, message={exc}"
            )
            return

        diagnostics = {
            "request_id": response.request_id,
            "negotiated_version_header": response.negotiated_version,
            "supported_versions_header": response.supported_versions,
            "contracts_payload": response.payload,
        }
        st.session_state["ui_contract_diagnostics"] = diagnostics

    if not isinstance(diagnostics, dict):
        return

    payload = diagnostics.get("contracts_payload", {})
    negotiated_version = payload.get("negotiated_version") if isinstance(payload, dict) else None
    default_version = payload.get("default_version") if isinstance(payload, dict) else None

    st.caption(
        " | ".join(
            [
                f"contracts_request_id={diagnostics.get('request_id') or 'n/a'}",
                f"negotiated={negotiated_version or diagnostics.get('negotiated_version_header') or 'n/a'}",
                f"default={default_version or 'n/a'}",
                f"supported={diagnostics.get('supported_versions_header') or 'n/a'}",
            ]
        )
    )
    st.json(payload if isinstance(payload, dict) else {}, expanded=False)


def _render_header(client: ApiClient, api_version: str) -> None:
    """Render top-level dashboard header and contract diagnostics."""
    st.title(APP_TITLE)

    col_health, col_refresh, col_version = st.columns(3)
    with col_health:
        st.caption("Service Health")
        st.info(str(st.session_state["ui_health_status"]))

    with col_refresh:
        last_refresh = st.session_state["ui_last_refresh_utc"]
        st.caption("Last Refresh (UTC)")
        st.info(last_refresh.strftime("%Y-%m-%d %H:%M:%S"))

    with col_version:
        st.caption("API Version (UI Header)")
        selected_version = st.selectbox(
            label="Version",
            options=SUPPORTED_API_VERSIONS,
            index=SUPPORTED_API_VERSIONS.index(str(st.session_state["ui_api_version"])),
            key="ui_api_version_selector",
            label_visibility="collapsed",
        )
        st.session_state["ui_api_version"] = selected_version

    base_url = os.getenv("NEPSE_UI_API_BASE_URL", "http://localhost:8000")
    st.caption(f"API Base URL: {base_url}")
    _render_contract_diagnostics(client=client, api_version=api_version)


def _render_tabs(client: ApiClient, api_version: str) -> None:
    """Render read-only tab layout defined by UI guidance."""
    tab_signals, tab_rankings, tab_opportunities, tab_backtest, tab_metrics, tab_explorer = st.tabs(
        ["Signals", "Rankings", "Opportunities", "Backtest", "Metrics", "API Explorer"]
    )

    with tab_signals:
        signals.render(client=client, api_version=api_version)
    with tab_rankings:
        rankings.render(client=client, api_version=api_version)
    with tab_opportunities:
        opportunities.render(client=client, api_version=api_version)
    with tab_backtest:
        backtest.render(client=client, api_version=api_version)
    with tab_metrics:
        metrics.render(client=client, api_version=api_version)
    with tab_explorer:
        explorer.render(client=client, api_version=api_version)


def main() -> None:
    """Run the Streamlit dashboard shell."""
    load_dotenv()
    _init_page()
    _init_state()
    client = _build_api_client()
    api_version = str(st.session_state["ui_api_version"])
    _render_header(client=client, api_version=api_version)
    st.divider()
    _render_tabs(client=client, api_version=api_version)


if __name__ == "__main__":
    main()
