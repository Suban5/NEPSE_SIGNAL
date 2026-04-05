"""Simple in-memory TTL cache for API service responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Any, Dict, Optional, Tuple


@dataclass
class TTLCache:
    """Thread-safe TTL cache with basic hit/miss counters."""

    ttl_seconds: float
    max_entries: int = 5000
    _store: Dict[str, Tuple[float, Any]] = field(default_factory=dict)
    _hits: int = 0
    _misses: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def get(self, key: str) -> Optional[Any]:
        """Return cached value when present and fresh."""
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            expires_at, value = entry
            if expires_at <= now:
                self._store.pop(key, None)
                self._misses += 1
                return None

            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """Store a value with default or overridden TTL."""
        with self._lock:
            if self.max_entries > 0 and len(self._store) >= self.max_entries:
                self._evict_oldest_locked()
            ttl = self.ttl_seconds if ttl_seconds is None else max(0.0, float(ttl_seconds))
            self._store[key] = (time.monotonic() + ttl, value)

    def delete(self, key: str) -> None:
        """Delete a single cache key when present."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._store.clear()

    def _evict_oldest_locked(self) -> None:
        """Evict the oldest cache entry to enforce max size."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda cache_key: self._store[cache_key][0])
        self._store.pop(oldest_key, None)

    def snapshot(self) -> Dict[str, int]:
        """Return cache statistics."""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "entries": len(self._store),
            }
