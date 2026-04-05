"""Lightweight request telemetry helpers for the FastAPI API."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict


@dataclass
class RequestMetrics:
    """In-memory request metrics snapshot."""

    request_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    status_counts: Counter[str] = field(default_factory=Counter)
    endpoint_counts: Counter[str] = field(default_factory=Counter)

    def record(self, endpoint: str, status_code: int, duration_ms: float) -> None:
        """Record a single request observation."""
        self.request_count += 1
        if status_code >= 400:
            self.error_count += 1
        self.total_duration_ms += duration_ms
        self.status_counts[str(status_code)] += 1
        self.endpoint_counts[endpoint] += 1

    def snapshot(self) -> Dict[str, Any]:
        """Return a serializable metrics snapshot."""
        avg_duration_ms = self.total_duration_ms / self.request_count if self.request_count else 0.0
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "avg_duration_ms": round(avg_duration_ms, 3),
            "status_counts": dict(self.status_counts),
            "endpoint_counts": dict(self.endpoint_counts),
        }


class MetricsRegistry:
    """Thread-safe registry for API request metrics."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._metrics = RequestMetrics()

    def record(self, endpoint: str, status_code: int, duration_ms: float) -> None:
        """Store a request observation."""
        with self._lock:
            self._metrics.record(endpoint, status_code, duration_ms)

    def snapshot(self) -> Dict[str, Any]:
        """Return current metrics snapshot."""
        with self._lock:
            return self._metrics.snapshot()


metrics_registry = MetricsRegistry()