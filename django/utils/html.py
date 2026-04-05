"""Minimal HTML helpers used by nepse_client news endpoints."""

from __future__ import annotations

import re
from html import unescape


_TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(value: str) -> str:
    """Remove HTML tags from a string.

    Args:
        value: Input HTML text.

    Returns:
        Text with tags removed and HTML entities unescaped.
    """
    if not isinstance(value, str):
        return ""
    return unescape(_TAG_RE.sub("", value))