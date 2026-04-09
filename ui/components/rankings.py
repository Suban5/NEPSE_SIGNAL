"""Rankings panel rendering for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from ui.api_client import ApiClient, ApiClientError
from ui.utils.error_handling import render_empty_state, render_error_state, render_fetch_hint


ANALYTICS_ENDPOINT = "/analytics/bluechip-ranking"


def render(client: ApiClient, api_version: str) -> None:
    """Render the Blue-Chip Rankings panel."""
    st.subheader("Blue-Chip Rankings")

    col_top_n, col_sector, col_refresh = st.columns(3)
    with col_top_n:
        top_n = int(st.number_input("Top N", min_value=1, max_value=200, value=20, step=1, key="rankings_top_n"))
    with col_sector:
        sector_relative = bool(st.checkbox("Sector Relative", value=False, key="rankings_sector_relative"))
    with col_refresh:
        fetch_clicked = st.button("Fetch Rankings", key="rankings_fetch")

    if not fetch_clicked:
        render_fetch_hint("Click 'Fetch Rankings' to load data from /analytics/bluechip-ranking")
        return

    with st.spinner("Fetching blue-chip rankings..."):
        try:
            response = client.analytics_bluechip_ranking(
                top_n=top_n,
                sector_relative=sector_relative,
                api_version=api_version,
            )
        except ApiClientError as exc:
            render_error_state(exc)
            return

    st.caption(
        " | ".join(
            [
                f"request_id={response.request_id or 'n/a'}",
                f"contract_version={response.negotiated_version or 'n/a'}",
                f"supported={response.supported_versions or 'n/a'}",
            ]
        )
    )

    execution_id = response.payload.get("execution_id")
    if isinstance(execution_id, str) and execution_id.strip():
        execution_map = st.session_state.setdefault("ui_last_execution_ids", {})
        execution_map[ANALYTICS_ENDPOINT] = execution_id

    rows = response.payload.get("rows", [])
    if not isinstance(rows, list) or not rows:
        render_empty_state("bluechip-ranking")
        return

    st.dataframe(rows, use_container_width=True)
    st.json(
        {
            "top_n": response.payload.get("top_n"),
            "sector_relative": response.payload.get("sector_relative"),
            "execution_id": execution_id,
            "summary": response.payload.get("summary"),
        },
        expanded=False,
    )
