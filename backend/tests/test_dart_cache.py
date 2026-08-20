"""ReportCache 동작 고정 테스트 — 특히 **파서 버전 무효화**.

이 캐시는 30일이라 규칙이 틀리면 오래 틀린다. 예전엔 다섯 모듈이 각자 구현했고 그중
둘(dart_profile·labor_cost)은 버전 검사가 없어서, 파서를 고쳐도 한 달간 옛 결과를
돌려줬다. 그 규칙을 여기서 고정한다.

디스크 형식도 함께 고정한다 — 봉투 모양을 바꾸면 이미 쌓인 수백 개 캐시가 통째로
무효가 되어 전 종목 재수집이 필요해진다.
"""
from __future__ import annotations

import json
import time

import pytest

from app.data.fundamentals.dart_cache import ReportCache


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    """data_dir 를 tmp 로 돌린 ReportCache."""
    from app.core import config

    def _fake():
        s = config.Settings(data_dir=tmp_path)
        return s

    monkeypatch.setattr(config, "get_settings", _fake)
    monkeypatch.setattr("app.data.fundamentals.dart_cache.get_settings", _fake)
    return ReportCache("notes", version=7)


def test_miss_when_absent(cache) -> None:
    assert cache.get("005930") is None


def test_put_then_get(cache) -> None:
    cache.put("005930", {"available": True, "n": 3})
    assert cache.get("005930") == {"available": True, "n": 3}


def test_put_returns_payload_unchanged(cache) -> None:
    """`return _CACHE.put(t, out)` 관용구가 성립해야 한다."""
    out = {"a": 1}
    assert cache.put("005930", out) is out


def test_envelope_shape_on_disk(cache) -> None:
    """봉투는 payload 에 _ts·_v 를 얹은 평평한 dict — 예전 형식과 같아야 한다."""
    cache.put("005930", {"a": 1})
    raw = json.loads(cache.path("005930").read_text(encoding="utf-8"))
    assert raw["a"] == 1
    assert raw["_v"] == 7
    assert isinstance(raw["_ts"], float)


def test_get_strips_envelope_keys(cache) -> None:
    cache.put("005930", {"a": 1})
    assert set(cache.get("005930")) == {"a"}


def test_version_mismatch_is_a_miss(cache) -> None:
    """파서를 고쳐 버전을 올리면 옛 결과를 주지 않는다 — 이게 원래 없던 규칙."""
    cache.put("005930", {"a": "옛 파서 결과"})
    newer = ReportCache("notes", version=8)
    assert newer.get("005930") is None


def test_missing_version_is_a_miss(cache) -> None:
    """버전 없이 기록된 옛 파일(_v 부재)도 미스로 본다."""
    p = cache.path("005930")
    p.write_text(json.dumps({"a": 1, "_ts": time.time()}), encoding="utf-8")
    assert cache.get("005930") is None


def test_expired_is_a_miss(tmp_path, cache, monkeypatch) -> None:
    """만료를 **시계로 재지 않는다.**

    원래는 TTL 0.05초를 두고 sleep 으로 넘겼는데, 저장·조회가 파일 입출력이라
    디스크가 느린 날에는 넣자마자 읽어도 이미 만료다(실제로 그렇게 깨졌다).
    테스트가 하드웨어 속도에 달려 있으면 실패가 신호가 아니라 잡음이 된다.
    시각을 직접 옮겨 만료 조건만 검증한다.
    """
    from app.data.fundamentals import dart_cache as DC

    short = ReportCache("notes", version=7, ttl=60)
    short.put("005930", {"a": 1})
    assert short.get("005930") == {"a": 1}

    later = time.time() + 61
    monkeypatch.setattr(DC.time, "time", lambda: later)
    assert short.get("005930") is None


def test_corrupt_file_is_a_miss(cache) -> None:
    cache.path("005930").write_text('{"a": 1, "_ts":', encoding="utf-8")
    assert cache.get("005930") is None


def test_refresh_bypasses_cache(cache) -> None:
    cache.put("005930", {"a": 1})
    assert cache.get("005930", refresh=True) is None


def test_tickers_do_not_collide(cache) -> None:
    cache.put("005930", {"who": "삼성전자"})
    cache.put("000660", {"who": "SK하이닉스"})
    assert cache.get("005930")["who"] == "삼성전자"
    assert cache.get("000660")["who"] == "SK하이닉스"


def test_prefixes_do_not_collide(cache) -> None:
    """같은 티커라도 접두사가 다르면 다른 파일이어야 한다(notes vs labor)."""
    other = ReportCache("labor", version=1)
    cache.put("005930", {"kind": "notes"})
    other.put("005930", {"kind": "labor"})
    assert cache.get("005930")["kind"] == "notes"
    assert other.get("005930")["kind"] == "labor"


def test_value_helper_for_wrapped_payload(cache) -> None:
    """labor_cost 처럼 payload 가 {key: 값} 한 겹인 경우."""
    cache.put("005930", {"years": [1, 2, 3]})
    assert cache.value("005930", "years") == [1, 2, 3]
    assert cache.value("000000", "years", []) == []


def test_write_is_atomic_no_tmp_left(cache) -> None:
    cache.put("005930", {"a": 1})
    d = cache.path("005930").parent
    assert not [f.name for f in d.iterdir() if f.name.endswith(".tmp")]
