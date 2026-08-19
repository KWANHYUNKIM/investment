"""지도 위 주변시설(POI) — 학교·지하철역을 지도 범위(bbox)로 잘라 준다.

네이버 부동산의 학군·교통 레이어에 해당한다. 원본은 공공 표준데이터 파일이라
``scripts.ingest_poi`` 로 한 번 적재해 두고(``data/reference/*.json``) 여기서 읽는다.
전국 12,000곳을 통째로 내려보내면 1.8MB 라 지도가 버벅인다 — **화면에 보이는 범위만**
자르고, 그래도 많으면 상한(limit)까지만 준다.

파일이 없으면 available=False 로 조용히 비워 응답한다(지도는 그대로 뜨게).
"""
from __future__ import annotations

import json
import threading

from app.core.config import get_settings

_lock = threading.Lock()
_cache: dict[str, list[dict] | None] = {}


def _load(name: str) -> list[dict] | None:
    """reference/<name>.json 을 한 번만 읽어 메모리에 둔다(프로세스 수명 동안 불변)."""
    with _lock:
        if name in _cache:
            return _cache[name]
        path = get_settings().data_dir / "reference" / f"{name}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        _cache[name] = data
        return data


def _in_box(p: dict, sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float) -> bool:
    return sw_lat <= p["lat"] <= ne_lat and sw_lng <= p["lng"] <= ne_lng


def _query(name: str, sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
           limit: int, keep) -> dict:
    rows = _load(name)
    if rows is None:
        return {
            "available": False,
            "message": f"{name}.json 이 없습니다 — `python -m scripts.ingest_poi` 로 적재하세요.",
            "count": 0, "truncated": False, "items": [],
        }
    # 위/경도가 뒤집혀 들어와도 빈 결과가 되지 않게 정규화한다.
    if sw_lat > ne_lat:
        sw_lat, ne_lat = ne_lat, sw_lat
    if sw_lng > ne_lng:
        sw_lng, ne_lng = ne_lng, sw_lng

    hit = [p for p in rows if _in_box(p, sw_lat, sw_lng, ne_lat, ne_lng) and keep(p)]
    total = len(hit)
    return {
        "available": True, "message": None,
        "count": total, "truncated": total > limit,
        "items": hit[:limit],
    }


def schools(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
            levels: str | None = None, limit: int = 600) -> dict:
    """학교 — levels 는 "초등학교,중학교" 처럼 콤마로 준다(없으면 전부)."""
    want = {s.strip() for s in levels.split(",") if s.strip()} if levels else None
    return _query("schools", sw_lat, sw_lng, ne_lat, ne_lng, limit,
                  lambda p: not want or p["level"] in want)


def stations(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
             limit: int = 400) -> dict:
    """지하철역 — 같은 역이 노선별로 여러 행이라 이름 기준으로 한 번 더 접는다."""
    res = _query("stations", sw_lat, sw_lng, ne_lat, ne_lng, limit * 3, lambda _p: True)
    if not res["available"]:
        return res
    merged: dict[str, dict] = {}
    for s in res["items"]:
        cur = merged.get(s["name"])
        if cur is None:
            merged[s["name"]] = {**s, "lines": [s["line"]] if s["line"] else []}
        elif s["line"] and s["line"] not in cur["lines"]:
            cur["lines"].append(s["line"])
            cur["transfer"] = True
    items = list(merged.values())
    return {
        "available": True, "message": None,
        "count": len(items), "truncated": len(items) > limit,
        "items": items[:limit],
    }
