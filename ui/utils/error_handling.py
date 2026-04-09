"""Shared UI state renderers for loading/error/empty handling."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from ui.api_client import ApiClientError


@dataclass(frozen=True)
class ErrorState:
    """Normalized UI error state for panel rendering."""

    kind: str
    text: str


def classify_api_error(exc: ApiClientError) -> ErrorState:
    """Classify API client exceptions into stable UI error categories."""
    message = str(exc)
    lower_message = message.lower()

    if exc.status_code == 504 or "timeout" in lower_message or "timed out" in lower_message:
        return ErrorState(
            kind="timeout",
            text=(
                "Request timed out. "
                f"endpoint={exc.endpoint}, status={exc.status_code}, request_id={exc.request_id}, message={message}"
            ),
        )

    return ErrorState(
        kind="error",
        text=(
            "Request failed. "
            f"endpoint={exc.endpoint}, status={exc.status_code}, request_id={exc.request_id}, message={message}"
        ),
    )


def render_error_state(exc: ApiClientError) -> None:
    """Render standardized error state for API failures."""
    state = classify_api_error(exc)
    if state.kind == "timeout":
        st.warning(state.text)
    else:
        st.error(state.text)


def render_empty_state(entity_label: str) -> None:
    """Render standardized empty-data state."""
    st.info(f"No {entity_label} data returned by API for current filters.")


def render_fetch_hint(message: str) -> None:
    """Render standardized pre-fetch helper text."""
    st.caption(message)
