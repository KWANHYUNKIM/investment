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

모듈당 값 하나짜리(싱글턴) 캐시는 키 없이 쓴다 — 28개 모듈이 이 형태다.

    _cache = TTLCache(ttl=600.0)
    ...
    hit = _cache.get()
    if hit:                      # 원래 코드가 truthy 검사였으면 그대로 truthy 로.
        return hit               # `is not None` 이었으면 그쪽으로. 빈 dict 를 미스로
    return _cache.set(None, build())   # 볼지 말지가 달라지므로 옮길 때 맞춰야 한다.

**아직 이걸 안 쓰는 캐시가 남아 있고, 그중 일부는 일부러 그렇다.**

- ``market/investor.py``·``market/brokers.py``·``wealth/picks.py`` — 상류 호출이
  실패하면 **만료된 값이라도** 돌려주는 폴백이 있다. ``get()`` 은 만료를 None 으로
  덮어버려 "만료된 값이 있었는지"를 알 수 없으므로 옮기면 폴백이 죽는다.
- ``company_costmodel``·``unit_economics`` — TTL 이 아니라 **파일 mtime** 기준 캐시.
- ``loaders/sec_edgar``·``macro/realestate_map`` 의 지오코딩 캐시 — 만료가 없는 영구 캐시.
- ``admin/curation``·``admin/stats``·``market/watchlist``·``reports/daily_archive`` 등의
  ``_lock`` — 캐시가 아니라 **파일 쓰기 직렬화**용.
- 키 있는 TTL 캐시(``news``·``industry_research``·``asset_detail``·``peer_compare`` 등)는
  옮길 수 있지만 아직 각자 구현이다.
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
