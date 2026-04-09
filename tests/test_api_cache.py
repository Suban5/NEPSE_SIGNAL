"""Unit tests for API TTL cache behavior."""

from __future__ import annotations

from typing import Iterator

import pytest

from api.cache import TTLCache


@pytest.fixture
def cache() -> TTLCache:
    """Create a small cache instance for deterministic tests."""
    return TTLCache(ttl_seconds=10.0, max_entries=3)


def test_get_miss_increments_counter(cache: TTLCache) -> None:
    """Missing key should return None and increment miss count."""
    assert cache.get("unknown") is None
    stats = cache.snapshot()
    assert stats["misses"] == 1
    assert stats["hits"] == 0


def test_set_then_get_returns_value_and_hit(cache: TTLCache) -> None:
    """Stored key should be returned while fresh and increment hit count."""
    cache.set("foo", {"value": 1})

    result = cache.get("foo")

    assert result == {"value": 1}
    stats = cache.snapshot()
    assert stats["hits"] == 1
    assert stats["misses"] == 0


def test_expired_entry_returns_none_and_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired entries should return None, be removed, and increment misses."""
    timeline: Iterator[float] = iter([100.0, 112.0])

    import api.cache as cache_module

    monkeypatch.setattr(cache_module.time, "monotonic", lambda: next(timeline))

    ttl_cache = TTLCache(ttl_seconds=10.0)
    ttl_cache.set("foo", 1)

    assert ttl_cache.get("foo") is None
    assert ttl_cache.snapshot()["entries"] == 0
    assert ttl_cache.snapshot()["misses"] == 1


def test_set_with_override_ttl_uses_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Per-key TTL override should control expiration independent of default TTL."""
    timeline: Iterator[float] = iter([50.0, 51.0, 53.5])

    import api.cache as cache_module

    monkeypatch.setattr(cache_module.time, "monotonic", lambda: next(timeline))

    ttl_cache = TTLCache(ttl_seconds=30.0)
    ttl_cache.set("foo", "bar", ttl_seconds=2.0)

    assert ttl_cache.get("foo") == "bar"
    assert ttl_cache.get("foo") is None


def test_set_negative_ttl_expires_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative custom TTL should be clamped to zero and expire immediately."""
    timeline: Iterator[float] = iter([10.0, 10.0])

    import api.cache as cache_module

    monkeypatch.setattr(cache_module.time, "monotonic", lambda: next(timeline))

    ttl_cache = TTLCache(ttl_seconds=30.0)
    ttl_cache.set("foo", 1, ttl_seconds=-5.0)

    assert ttl_cache.get("foo") is None


def test_delete_removes_key(cache: TTLCache) -> None:
    """Delete should remove a present key."""
    cache.set("foo", 1)
    cache.delete("foo")

    assert cache.get("foo") is None


def test_clear_removes_all_entries(cache: TTLCache) -> None:
    """Clear should empty the entire store."""
    cache.set("a", 1)
    cache.set("b", 2)

    cache.clear()

    assert cache.snapshot()["entries"] == 0
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_evict_oldest_when_max_entries_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache should evict oldest expiration entry when at capacity."""
    timeline: Iterator[float] = iter([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    import api.cache as cache_module

    monkeypatch.setattr(cache_module.time, "monotonic", lambda: next(timeline))

    ttl_cache = TTLCache(ttl_seconds=100.0, max_entries=2)
    ttl_cache.set("first", 1)
    ttl_cache.set("second", 2)
    ttl_cache.set("third", 3)

    assert ttl_cache.snapshot()["entries"] == 2
    assert ttl_cache.get("first") is None
    assert ttl_cache.get("second") == 2
    assert ttl_cache.get("third") == 3


def test_zero_max_entries_disables_capacity_eviction() -> None:
    """max_entries=0 should skip eviction and allow growth."""
    ttl_cache = TTLCache(ttl_seconds=30.0, max_entries=0)
    for idx in range(5):
        ttl_cache.set(f"k{idx}", idx)

    assert ttl_cache.snapshot()["entries"] == 5


def test_snapshot_contains_hits_misses_and_entries(cache: TTLCache) -> None:
    """Snapshot should expose all cache counters and entry count."""
    cache.set("foo", 1)
    _ = cache.get("foo")
    _ = cache.get("bar")

    stats = cache.snapshot()

    assert set(stats.keys()) == {"hits", "misses", "entries"}
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["entries"] == 1


def test_evict_oldest_noop_when_store_empty(cache: TTLCache) -> None:
    """Eviction helper should no-op safely when store is empty."""
    cache._evict_oldest_locked()
    assert cache.snapshot()["entries"] == 0
