"""Thread-safe TTL cache — replaces the ad-hoc module-level ``_lock``/``_cache``
patterns scattered across ``app/data`` with one reusable primitive.

    cache = TTLCache(ttl=30.0)
    hit = cache.get(market)
    if hit is None:
        hit = expensive()
        cache.set(market, hit)

Keys may be any hashable (``None`` included). Values are returned as stored;
expiry is checked lazily on read. Designed to be held by a service instance and
injected, so caching is a property of the service — not a global side effect.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Hashable


class TTLCache:
    """Small thread-safe cache with per-instance TTL and lazy expiry."""

    def __init__(self, ttl: float) -> None:
        self._ttl = float(ttl)
        self._lock = threading.Lock()
        self._store: dict[Hashable, tuple[float, Any]] = {}

    def get(self, key: Hashable = None) -> Any | None:
        """Return the cached value, or ``None`` if absent/expired."""
        with self._lock:
            hit = self._store.get(key)
            if hit and (time.time() - hit[0] < self._ttl):
                return hit[1]
        return None

    def set(self, key: Hashable, value: Any) -> Any:
        """Store ``value`` under ``key`` (stamped now) and return it."""
        with self._lock:
            self._store[key] = (time.time(), value)
        return value

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        """Return the cached value or compute, store, and return it.

        ``factory`` runs outside the lock so a slow producer never blocks other
        keys; a concurrent miss may compute twice but never serves stale data.
        """
        hit = self.get(key)
        if hit is not None:
            return hit
        return self.set(key, factory())

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
