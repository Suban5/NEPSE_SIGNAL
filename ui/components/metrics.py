"""Observability and contract diagnostics panel for Streamlit UI."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from ui.api_client import ApiClient, ApiClientError
from ui.utils.error_handling import render_empty_state, render_error_state, render_fetch_hint


def build_execution_id_correlations(
    local_execution_ids: Dict[str, str],
    metrics_payload: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build endpoint-level execution ID correlation rows for observability panel."""
    metrics_map = metrics_payload.get("last_execution_id_by_endpoint", {})
    if not isinstance(metrics_map, dict):
        metrics_map = {}

    all_endpoints = sorted(set(local_execution_ids.keys()) | set(str(k) for k in metrics_map.keys()))
    rows: List[Dict[str, str]] = []
    for endpoint in all_endpoints:
        local_value = local_execution_ids.get(endpoint) or ""
        metrics_value_raw = metrics_map.get(endpoint)
        metrics_value = metrics_value_raw if isinstance(metrics_value_raw, str) else ""
        rows.append(
            {
                "endpoint": endpoint,
                "ui_execution_id": local_value or "n/a",
                "metrics_execution_id": metrics_value or "n/a",
                "match": "yes" if local_value and metrics_value and local_value == metrics_value else "no",
            }
        )
    return rows


def render(client: ApiClient, api_version: str) -> None:
    """Render metrics and contract diagnostics panel."""
    st.subheader("Workflow Observability")

    fetch_clicked = st.button("Fetch Metrics and Contracts", key="metrics_fetch")
    if not fetch_clicked:
        render_fetch_hint("Click 'Fetch Metrics and Contracts' to load /metrics and /contracts")
        return

    with st.spinner("Fetching metrics and contract metadata..."):
        try:
            metrics_response = client.metrics(api_version=api_version)
            contracts_response = client.contracts(api_version=api_version)
        except ApiClientError as exc:
            render_error_state(exc)
            return

    if not isinstance(metrics_response.payload, dict) or not metrics_response.payload:
        render_empty_state("metrics")
        return

    local_execution_ids = st.session_state.get("ui_last_execution_ids", {})
    if not isinstance(local_execution_ids, dict):
        local_execution_ids = {}

    correlation_rows = build_execution_id_correlations(
        local_execution_ids={str(k): str(v) for k, v in local_execution_ids.items()},
        metrics_payload=metrics_response.payload,
    )

    st.caption(
        " | ".join(
            [
                f"metrics_request_id={metrics_response.request_id or 'n/a'}",
                f"metrics_contract_version={metrics_response.negotiated_version or 'n/a'}",
                f"contracts_request_id={contracts_response.request_id or 'n/a'}",
            ]
        )
    )

    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown("**Metrics Snapshot**")
        st.json(metrics_response.payload, expanded=False)

    with right_col:
        st.markdown("**Contracts Snapshot**")
        st.json(contracts_response.payload, expanded=False)

    st.markdown("**Execution ID Correlation**")
    st.dataframe(correlation_rows, use_container_width=True)
