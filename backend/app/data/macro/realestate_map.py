"""부동산 실거래 지도 — 국토부 실거래(시군구 집계)를 좌표에 얹어 지도로.

지도용은 **완성 최신월 1개월(약 250콜)** 만 받아 쿼터 부담을 6개월 대비 1/6로 줄이고,
동시요청을 낮추고 429에 백오프 재시도한다. 결과는 디스크 캐시(12h)로 재시작 시 재호출 방지.
좌표는 키 없는 OSM Nominatim 지오코딩(캐시·시도중심 폴백). 호가 매물은 정부 API에 없어 제외.
데이터가 아직 없어도 지도(빈 베이스맵)는 항상 보이도록 응답한다.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from app.core.config import get_settings
from app.data.infra.lawd_codes import SIGUNGU
from app.data.macro import realestate

# 17개 시도 중심점 (지오코딩 폴백)
_SIDO_CENTROID = {
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756),
    "대구": (35.8714, 128.6014), "인천": (37.4563, 126.7052),
    "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "세종": (36.4801, 127.2890),
    "경기": (37.4138, 127.5183), "강원": (37.8228, 128.1555),
    "충북": (36.6357, 127.4917), "충남": (36.5184, 126.8000),
    "전북": (35.7175, 127.1530), "전남": (34.8161, 126.4630),
    "경북": (36.4919, 128.8889), "경남": (35.4606, 128.2132),
    "제주": (33.4996, 126.5312),
}


def _sido_centroid(sido: str) -> tuple[float, float]:
    for k, v in _SIDO_CENTROID.items():
        if sido.startswith(k) or k in sido:
            return v
    return (36.5, 127.8)


def _jitter(name: str) -> tuple[float, float]:
    h = sum(ord(ch) for ch in name)
    return (((h % 37) - 18) / 100.0, ((h // 37 % 37) - 18) / 100.0)


# --- Nominatim 지오코딩 (무키, 디스크 캐시) ------------------------------------
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_geo_lock = threading.Lock()
_geo_cache: dict[str, list[float]] | None = None
_last_geo = [0.0]
_GEO_INTERVAL = 1.1


def _geo_path():
    d = get_settings().data_dir / "cache" / "geo"
    d.mkdir(parents=True, exist_ok=True)
    return d / "sigungu.json"


def _load_geo() -> dict[str, list[float]]:
    global _geo_cache
    if _geo_cache is None:
        try:
            _geo_cache = json.loads(_geo_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _geo_cache = {}
    return _geo_cache


def _save_geo() -> None:
    try:
        _geo_path().write_text(json.dumps(_geo_cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _geocode_net(query: str) -> list[float] | None:
    with _geo_lock:
        wait = _GEO_INTERVAL - (time.time() - _last_geo[0])
        if wait > 0:
            time.sleep(wait)
        _last_geo[0] = time.time()
    try:
        r = requests.get(
            _NOMINATIM,
            params={"q": query, "format": "json", "countrycodes": "kr", "limit": "1"},
            headers={"User-Agent": "investment-dashboard/1.0 (realestate map)"},
            timeout=12,
        )
        arr = r.json()
        if arr:
            return [round(float(arr[0]["lat"]), 5), round(float(arr[0]["lon"]), 5)]
    except Exception:
        return None
    return None


def _cached_coord(sido: str, region: str) -> list[float] | None:
    return _load_geo().get(f"{sido} {region}")


_geo_warm = {"started": False, "running": False, "done": 0, "total": 0}


def warm_geocode() -> None:
    cache = _load_geo()
    todo = [(lawd, sido, name) for (lawd, sido, name) in SIGUNGU
            if f"{sido} {name}" not in cache]
    _geo_warm.update(running=True, total=len(todo), done=0)
    for _lawd, sido, name in todo:
        coord = _geocode_net(f"대한민국 {sido} {name}")
        if coord:
            cache[f"{sido} {name}"] = coord
            _save_geo()
        _geo_warm["done"] += 1
    _geo_warm["running"] = False


def start_geocode_warm() -> None:
    if _geo_warm["started"]:
        return
    _geo_warm["started"] = True
    threading.Thread(target=warm_geocode, name="re-geocode", daemon=True).start()


# --- 실거래(지도용, 최신 1개월) 수집 + 디스크 캐시 ---------------------------
_MAP_TTL = 12 * 3600.0
_map_warm = {"running": False, "started_ts": 0.0, "done": 0, "total": 0, "msg": None}


def _map_path():
    d = get_settings().data_dir / "cache" / "realestate"
    d.mkdir(parents=True, exist_ok=True)
    return d / "map_latest.json"


def _load_map() -> dict | None:
    try:
        return json.loads(_map_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_map(data: dict) -> None:
    try:
        _map_path().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _fetch_region(lawd: str, ym: str, retries: int = 3) -> tuple[int, float, bool]:
    """한 시군구 최신월 집계. 429/실패 시 백오프 재시도."""
    for a in range(retries):
        c, amt, ok = realestate._fetch_one(lawd, ym)
        if ok:
            return c, amt, True
        time.sleep(1.5 * (a + 1))
    return 0, 0.0, False


def map_warm() -> None:
    if not get_settings().data_go_kr_key:
        _map_warm["msg"] = "DATA_GO_KR_KEY 미설정 — backend/.env에 키를 넣으세요."
        return
    _map_warm.update(running=True, msg=None, done=0, total=len(SIGUNGU))
    ym = realestate._recent_months(2)[0]   # 완성 최신월(전월)
    rows: list[dict] = []
    ok_any = False

    def run(item):
        lawd, sido, name = item
        c, amt, ok = _fetch_region(lawd, ym)
        return lawd, sido, name, c, amt, ok

    try:
        with ThreadPoolExecutor(max_workers=6) as ex:   # 동시요청 낮춤(버스트 방지)
            for lawd, sido, name, c, amt, ok in ex.map(run, SIGUNGU):
                _map_warm["done"] += 1
                if ok:
                    ok_any = True
                if c > 0:
                    rows.append({"region": name, "sido": sido, "lawd": lawd, "count": c,
                                 "amount_eok": round(amt / 10000.0, 1),
                                 "avg_eok": round(amt / 10000.0 / c, 2) if c else None})
        if ok_any:
            _save_map({"ym": ym, "ts": time.time(), "regions": rows})
            _map_warm["msg"] = None
        else:
            _map_warm["msg"] = ("data.go.kr 호출이 모두 실패(429 한도/반영지연 가능). "
                                "한도 반영 후 자동으로 채워집니다.")
    finally:
        _map_warm["running"] = False


def _maybe_warm(cache: dict | None) -> None:
    fresh = cache and (time.time() - cache.get("ts", 0) < _MAP_TTL)
    if get_settings().data_go_kr_key and not _map_warm["running"] and not fresh:
        # 직전 시도 후 60초 안엔 재시도 안 함(429 폭주 방지)
        if time.time() - _map_warm["started_ts"] > 60:
            _map_warm["started_ts"] = time.time()
            threading.Thread(target=map_warm, name="re-map-warm", daemon=True).start()


# --- 공개 ---------------------------------------------------------------------
def map_snapshot() -> dict:
    """지도용 데이터. 데이터가 없어도 항상 렌더 가능한 형태로 응답(빈 지도 + 안내)."""
    start_geocode_warm()
    cache = _load_map()
    _maybe_warm(cache)

    regions = []
    label = None
    if cache and cache.get("regions"):
        ym = cache["ym"]
        label = f"{ym[:4]}.{ym[4:]}"
        for r in cache["regions"]:
            coord = _cached_coord(r["sido"], r["region"])
            approx = coord is None
            if approx:
                base = _sido_centroid(r["sido"])
                jt = _jitter(r["region"])
                coord = [round(base[0] + jt[0], 5), round(base[1] + jt[1], 5)]
            regions.append({
                "region": r["region"], "sido": r["sido"], "lawd": r["lawd"],
                "count": r["count"], "amount_eok": r["amount_eok"], "avg_eok": r["avg_eok"],
                "lat": coord[0], "lng": coord[1], "approx": approx,
            })

    ready = len(regions) > 0
    geocoded = sum(1 for r in regions if not r["approx"])
    if ready:
        message = None
    elif _map_warm["running"]:
        prog = f" ({_map_warm['done']}/{_map_warm['total']})" if _map_warm["total"] else ""
        message = f"국토부 실거래 수집 중…{prog} 잠시 후 새로고침하세요."
    else:
        message = _map_warm["msg"] or "실거래 수집 대기 중. 곧 채워집니다."

    return {
        "ready": ready,
        "warming": _map_warm["running"],
        "message": message,
        "region_ym": cache.get("ym") if cache else None,
        "latest_label": label,
        "count": len(regions),
        "geocoded": geocoded,
        "regions": regions,
        "source": "국토교통부 실거래가(RTMS) · data.go.kr",
        "note": "국토부 실거래(완성 최신월) · 시군구 단위. 좌표는 무키 지오코딩(미완료는 시도중심 근사). 호가 매물은 정부 API 미제공으로 제외.",
    }


def region_deals(lawd: str, ym: str | None = None) -> dict:
    items = realestate.deals(lawd, ym)
    return {"lawd": lawd, "count": len(items), "deals": items}
