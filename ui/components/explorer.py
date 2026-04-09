"""Generic API Explorer panel for non-core endpoint groups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import streamlit as st

from ui.api_client import ApiClient, ApiClientError
from ui.utils.error_handling import render_error_state, render_fetch_hint


@dataclass(frozen=True)
class QueryParamDef:
    """Typed query parameter definition for explorer endpoint controls."""

    name: str
    kind: str
    default: Any
    required: bool = False
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class EndpointDef:
    """Definition of one API endpoint exposed in explorer."""

    group: str
    label: str
    path_template: str
    path_vars: tuple[str, ...] = ()
    query_params: tuple[QueryParamDef, ...] = ()


def render_path_template(path_template: str, values: Dict[str, str]) -> str:
    """Render path template with provided placeholder values."""
    rendered = path_template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    if "{" in rendered or "}" in rendered:
        raise ValueError("missing path variable values")
    return rendered


ENDPOINTS: tuple[EndpointDef, ...] = (
    EndpointDef("Market", "Market Status", "/market/status"),
    EndpointDef("Market", "Market Summary", "/market/summary"),
    EndpointDef("Market", "Market Index", "/market/index"),
    EndpointDef("Market", "Market Sub-Indices", "/market/sub-indices"),
    EndpointDef("Market", "Market Live", "/market/live"),
    EndpointDef("Market", "Market Price-Volume", "/market/price-volume"),
    EndpointDef("Market", "Market Supply-Demand", "/market/supply-demand"),
    EndpointDef("Market", "Top Gainers", "/market/top-gainers"),
    EndpointDef("Market", "Top Losers", "/market/top-losers"),
    EndpointDef("Market", "Top Trade Scrips", "/market/top-trade-scrips"),
    EndpointDef("Market", "Top Transaction Scrips", "/market/top-transaction-scrips"),
    EndpointDef("Market", "Top Turnover Scrips", "/market/top-turnover-scrips"),
    EndpointDef("Company/Security", "Companies", "/companies"),
    EndpointDef("Company/Security", "Securities", "/securities"),
    EndpointDef("Company/Security", "Company Details", "/companies/{symbol}", path_vars=("symbol",)),
    EndpointDef(
        "Company/Security",
        "Company History",
        "/companies/{symbol}/history",
        path_vars=("symbol",),
        query_params=(
            QueryParamDef("start_date", "str", "", required=False),
            QueryParamDef("end_date", "str", "", required=False),
        ),
    ),
    EndpointDef("Company/Security", "Company Graph", "/companies/{symbol}/graph", path_vars=("symbol",)),
    EndpointDef("Company/Security", "Company Financials", "/companies/{company_id}/financials", path_vars=("company_id",)),
    EndpointDef("Company/Security", "Company AGM", "/companies/{company_id}/agm", path_vars=("company_id",)),
    EndpointDef("Company/Security", "Company Dividend", "/companies/{company_id}/dividend", path_vars=("company_id",)),
    EndpointDef(
        "Company/Security",
        "Company Market Depth",
        "/companies/{company_id}/market-depth",
        path_vars=("company_id",),
    ),
    EndpointDef(
        "Trading",
        "Trading Floor Sheet",
        "/trading/floor-sheet",
        query_params=(
            QueryParamDef("show_progress", "bool", False),
            QueryParamDef("timeout_seconds", "int", 30),
        ),
    ),
    EndpointDef(
        "Trading",
        "Trading Floor Sheet By Symbol",
        "/trading/floor-sheet/{symbol}",
        path_vars=("symbol",),
        query_params=(QueryParamDef("business_date", "str", "", required=True),),
    ),
    EndpointDef(
        "Trading",
        "Trading Average",
        "/trading/average",
        query_params=(
            QueryParamDef("business_date", "str", "", required=True),
            QueryParamDef("n_days", "int", 180),
        ),
    ),
    EndpointDef("Trading", "Trading Market Depth", "/trading/market-depth/{symbol}", path_vars=("symbol",)),
    EndpointDef(
        "News",
        "Company News",
        "/news/company",
        query_params=(
            QueryParamDef("page", "int", 1),
            QueryParamDef("page_size", "int", 100),
            QueryParamDef("is_strip_tags", "bool", True),
        ),
    ),
    EndpointDef(
        "News",
        "News Alerts",
        "/news/alerts",
        query_params=(
            QueryParamDef("page", "int", 1),
            QueryParamDef("page_size", "int", 100),
            QueryParamDef("is_strip_tags", "bool", True),
        ),
    ),
    EndpointDef("News", "Press Releases", "/news/press-releases"),
    EndpointDef("News", "Notices", "/news/notices", query_params=(QueryParamDef("page", "int", 0),)),
    EndpointDef("Other", "Holidays", "/other/holidays", query_params=(QueryParamDef("year", "int", 2026, required=True),)),
    EndpointDef(
        "Other",
        "Debentures/Bonds",
        "/other/debentures-bonds",
        query_params=(QueryParamDef("instrument_type", "enum", "debenture", options=("debenture", "bond")),),
    ),
    EndpointDef(
        "Other",
        "Price Volume History",
        "/other/price-volume-history",
        query_params=(QueryParamDef("business_date", "str", "", required=True),),
    ),
    EndpointDef("Mappings", "Company ID Mapping", "/mappings/company-id", query_params=(QueryParamDef("force_update", "bool", False),)),
    EndpointDef("Mappings", "Security ID Mapping", "/mappings/security-id", query_params=(QueryParamDef("force_update", "bool", False),)),
    EndpointDef("Mappings", "Sector Scrips Mapping", "/mappings/sector-scrips"),
)


def _query_widget_key(path_template: str, name: str) -> str:
    return f"explorer_{path_template}_{name}".replace("/", "_").replace("{", "").replace("}", "")


def _build_query_params(endpoint: EndpointDef) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for param in endpoint.query_params:
        key = _query_widget_key(endpoint.path_template, param.name)
        if param.kind == "bool":
            value = st.checkbox(param.name, value=bool(param.default), key=key)
        elif param.kind == "int":
            value = int(st.number_input(param.name, value=int(param.default), step=1, key=key))
        elif param.kind == "enum":
            value = st.selectbox(param.name, options=param.options, index=param.options.index(str(param.default)), key=key)
        else:
            value = st.text_input(param.name, value=str(param.default), key=key)

        if param.required and (value is None or str(value).strip() == ""):
            raise ValueError(f"required query parameter missing: {param.name}")
        if isinstance(value, str) and not value.strip() and not param.required:
            continue
        params[param.name] = value
    return params


def _build_path_values(endpoint: EndpointDef) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for variable in endpoint.path_vars:
        key = _query_widget_key(endpoint.path_template, f"path_{variable}")
        value = st.text_input(f"path:{variable}", value="", key=key)
        if not value.strip():
            raise ValueError(f"required path variable missing: {variable}")
        values[variable] = value.strip()
    return values


def render(client: ApiClient, api_version: str) -> None:
    """Render generic explorer for non-core endpoint groups."""
    st.subheader("API Explorer")

    groups = sorted({endpoint.group for endpoint in ENDPOINTS})
    selected_group = st.selectbox("Endpoint Group", options=groups, key="explorer_group")
    endpoints_in_group = [endpoint for endpoint in ENDPOINTS if endpoint.group == selected_group]
    selected_label = st.selectbox(
        "Endpoint",
        options=[endpoint.label for endpoint in endpoints_in_group],
        key="explorer_endpoint",
    )
    endpoint = next(item for item in endpoints_in_group if item.label == selected_label)

    st.caption(f"Path Template: {endpoint.path_template}")

    try:
        path_values = _build_path_values(endpoint)
        params = _build_query_params(endpoint)
        endpoint_path = render_path_template(endpoint.path_template, path_values)
    except ValueError as exc:
        render_fetch_hint(f"Provide required endpoint inputs. {exc}")
        return

    fetch_clicked = st.button("Fetch Endpoint", key="explorer_fetch")
    if not fetch_clicked:
        render_fetch_hint("Click 'Fetch Endpoint' to execute the selected read-only API endpoint.")
        return

    with st.spinner("Fetching endpoint response..."):
        try:
            response = client.fetch_endpoint(endpoint_path, params=params, api_version=api_version)
        except ApiClientError as exc:
            render_error_state(exc)
            return

    st.caption(
        " | ".join(
            [
                f"endpoint={endpoint_path}",
                f"request_id={response.request_id or 'n/a'}",
                f"contract_version={response.negotiated_version or 'n/a'}",
                f"supported={response.supported_versions or 'n/a'}",
            ]
        )
    )

    st.json(response.payload, expanded=False)
