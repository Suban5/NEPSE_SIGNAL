"""Backtest summary panel rendering for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from ui.api_client import ApiClient, ApiClientError
from ui.utils.error_handling import render_empty_state, render_error_state, render_fetch_hint


ANALYTICS_ENDPOINT = "/analytics/backtest-summary"


def render(client: ApiClient, api_version: str) -> None:
    """Render the Portfolio Backtest Summary panel."""
    st.subheader("Portfolio Backtest Summary")

    col_top_n, col_lookback, col_rebalance, col_sector = st.columns(4)
    with col_top_n:
        top_n = int(st.number_input("Top N", min_value=1, max_value=200, value=20, step=1, key="backtest_top_n"))
    with col_lookback:
        lookback_days = int(
            st.number_input("Lookback Days", min_value=1, max_value=2000, value=252, step=1, key="backtest_lookback_days")
        )
    with col_rebalance:
        rebalance = st.selectbox(
            "Rebalance",
            options=("static", "weekly", "monthly"),
            index=0,
            key="backtest_rebalance",
        )
    with col_sector:
        sector_relative = bool(st.checkbox("Sector Relative", value=False, key="backtest_sector_relative"))

    fetch_clicked = st.button("Fetch Backtest Summary", key="backtest_fetch")
    if not fetch_clicked:
        render_fetch_hint("Click 'Fetch Backtest Summary' to load data from /analytics/backtest-summary")
        return

    with st.spinner("Fetching backtest summary..."):
        try:
            response = client.analytics_backtest_summary(
                top_n=top_n,
                lookback_days=lookback_days,
                rebalance=rebalance,
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

    portfolio_metrics = response.payload.get("portfolio_metrics", {})
    if not isinstance(portfolio_metrics, dict) or not portfolio_metrics:
        render_empty_state("backtest-summary")
        return

    col_cagr, col_drawdown, col_sharpe, col_total_return = st.columns(4)
    with col_cagr:
        st.metric("CAGR", str(portfolio_metrics.get("cagr", "n/a")))
    with col_drawdown:
        st.metric("Max Drawdown", str(portfolio_metrics.get("max_drawdown", "n/a")))
    with col_sharpe:
        st.metric("Sharpe Ratio", str(portfolio_metrics.get("sharpe_ratio", "n/a")))
    with col_total_return:
        st.metric("Total Return", str(portfolio_metrics.get("total_return", "n/a")))

    st.json(
        {
            "top_n": response.payload.get("top_n"),
            "lookback_days": response.payload.get("lookback_days"),
            "rebalance": response.payload.get("rebalance"),
            "sector_relative": response.payload.get("sector_relative"),
            "execution_id": execution_id,
            "summary": response.payload.get("summary"),
            "historical_validation": response.payload.get("historical_validation"),
            "portfolio_metrics": response.payload.get("portfolio_metrics"),
        },
        expanded=False,
    )
