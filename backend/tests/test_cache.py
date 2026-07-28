"""core.cache.TTLCache 동작 고정 테스트.

이 프리미티브 하나에 28개 모듈의 캐시가 얹혀 있다(app/data·app/domains 의 TTL 캐시).
그래서 만료·키 분리·falsy 값 취급 같은 규칙이 바뀌면 여러 화면이 동시에 영향을 받는다.
특히 **falsy 값** 취급이 중요하다: 호출부는 원래 코드의 의미를 그대로 옮겨
``if hit:``(빈 dict 는 미스로 보고 재계산) 또는 ``if hit is not None:``(빈 dict 도
캐시로 인정) 중 하나를 쓰는데, 그 선택이 가능해야 한다 — 즉 캐시는 저장한 값을
그대로 돌려줘야 하고 스스로 falsy 를 걸러서는 안 된다.
"""
from __future__ import annotations

import threading
import time

from app.core.cache import TTLCache


def test_miss_then_hit() -> None:
    c = TTLCache(ttl=60.0)
    assert c.get("k") is None
    c.set("k", {"v": 1})
    assert c.get("k") == {"v": 1}


def test_expiry() -> None:
    c = TTLCache(ttl=0.05)
    c.set("k", "v")
    assert c.get("k") == "v"
    time.sleep(0.08)
    assert c.get("k") is None


def test_keys_are_independent() -> None:
    c = TTLCache(ttl=60.0)
    c.set("a", 1)
    c.set("b", 2)
    assert (c.get("a"), c.get("b"), c.get("c")) == (1, 2, None)


def test_singleton_use_with_default_key() -> None:
    """싱글턴 캐시(모듈당 값 하나)는 키 없이 get()/set(None, ...) 으로 쓴다."""
    c = TTLCache(ttl=60.0)
    assert c.get() is None
    c.set(None, ["row"])
    assert c.get() == ["row"]


def test_falsy_values_are_returned_as_stored() -> None:
    """빈 dict/list/0 을 그대로 돌려줘야 호출부가 미스 판정 기준을 고를 수 있다."""
    c = TTLCache(ttl=60.0)
    for value in ({}, [], 0, "", False):
        c.set("k", value)
        got = c.get("k")
        assert got == value
        assert got is not None      # '저장됨'과 '미스'가 구분된다


def test_set_returns_the_value() -> None:
    """`return _cache.set(None, build())` 관용구가 성립한다."""
    c = TTLCache(ttl=60.0)
    assert c.set("k", 42) == 42


def test_clear_drops_everything() -> None:
    """invalidate() 계열이 이걸 쓴다."""
    c = TTLCache(ttl=60.0)
    c.set("a", 1)
    c.set(None, 2)
    c.clear()
    assert c.get("a") is None and c.get() is None


def test_get_or_set_computes_once_while_fresh() -> None:
    c = TTLCache(ttl=60.0)
    calls = []

    def factory() -> str:
        calls.append(1)
        return "built"

    assert c.get_or_set("k", factory) == "built"
    assert c.get_or_set("k", factory) == "built"
    assert len(calls) == 1


def test_concurrent_writers_do_not_corrupt() -> None:
    """모듈 캐시는 요청 스레드와 스케줄러 스레드가 같이 만진다."""
    c = TTLCache(ttl=60.0)

    def work(n: int) -> None:
        for i in range(200):
            c.set(n, i)
            c.get(n)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(c.get(n) == 199 for n in range(8))
