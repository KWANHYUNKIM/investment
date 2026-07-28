"""사업보고서 파싱 결과의 티커별 파일 캐시.

DART 원문 파싱은 비싸다(문서 zip 내려받기 + 표 격자 복원). 사업보고서는 연 1회 나오니
결과를 ``data/dart_business/<접두사>_<티커>.json`` 에 한 달 캐시한다. 다섯 모듈이
(dart_full · dart_profile · labor_cost · report_business · report_notes) 이 캐시를 각자
구현하고 있었고, **무효화 규칙이 서로 달랐다.**

  · dart_full · report_business · report_notes  파서 버전(_v)이 바뀌면 캐시를 버렸다
  · dart_profile · labor_cost                   버전 검사가 없어서, **파서를 고쳐도
                                                30일 동안 옛 결과를 계속 돌려줬다**

그 규칙을 여기 한 곳에 둔다. 파서를 손볼 때는 그 모듈의 ``ReportCache(version=...)`` 를
올리면 되고, 올리는 것을 잊더라도 최소한 어디를 올려야 하는지가 한눈에 보인다.

디스크 형식은 **예전과 같다** — 페이로드에 ``_ts``(저장 시각)와 ``_v``(파서 버전)를 얹은
평평한 dict. 형식을 바꾸면 이미 쌓인 캐시가 통째로 무효가 되어 전 종목 재수집이 필요해지므로
그대로 둔다.

    _CACHE = ReportCache("notes", version=7)

    def notes(ticker: str, refresh: bool = False) -> dict:
        hit = _CACHE.get(ticker, refresh=refresh)
        if hit is not None:
            return hit
        out = ...무거운 파싱...
        return _CACHE.put(ticker, out)
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json

MONTH = 30 * 24 * 3600.0        # 사업보고서는 연 1회 — 한 달이면 충분히 짧다
_DIRNAME = "dart_business"


class ReportCache:
    """티커 하나당 JSON 파일 하나. 만료·파서버전 불일치·손상이면 미스로 본다."""

    def __init__(self, prefix: str, *, version: int, ttl: float = MONTH) -> None:
        self._prefix = prefix
        self._version = int(version)
        self._ttl = float(ttl)

    def path(self, ticker: str) -> Path:
        d = get_settings().data_dir / _DIRNAME
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{self._prefix}_{ticker}.json"

    def get(self, ticker: str, *, refresh: bool = False) -> dict | None:
        """캐시된 페이로드(``_ts``/``_v`` 벗긴 것). 없거나 못 쓰면 ``None``.

        ``refresh=True`` 면 캐시를 보지 않는다(사용자가 새로고침을 누른 경우).
        """
        if refresh:
            return None
        d = read_json(self.path(ticker))
        if not isinstance(d, dict):
            return None
        if time.time() - d.get("_ts", 0) >= self._ttl:
            return None
        if d.get("_v") != self._version:
            return None     # 파서가 바뀌었다 — 옛 결과를 주면 고친 게 반영되지 않는다
        d.pop("_ts", None)
        d.pop("_v", None)
        return d

    def put(self, ticker: str, payload: dict) -> dict:
        """페이로드를 캐시에 쓰고 **그대로 돌려준다**(호출부가 return 에 바로 쓰게).

        쓰기 실패는 삼킨다 — 캐시는 있으면 좋은 것이고, 못 써도 결과는 이미 손에 있다.
        """
        try:
            write_json(self.path(ticker), {**payload, "_ts": time.time(), "_v": self._version},
                       compact=False)
        except OSError:
            pass
        return payload

    def value(self, ticker: str, key: str, default: Any = None, *, refresh: bool = False) -> Any:
        """페이로드가 ``{key: 실제값}`` 한 겹으로 감싸인 경우의 편의 조회."""
        hit = self.get(ticker, refresh=refresh)
        return default if hit is None else hit.get(key, default)
