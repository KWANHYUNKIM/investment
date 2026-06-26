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


# --- 단지별 지도(호갱노노 스타일) — 읍/면/동 지오코딩 + 단지명 jitter ----------
_LAWD_INFO = {lawd: (sido, name) for (lawd, sido, name) in SIGUNGU}

_dong_lock = threading.Lock()
_dong_cache: dict[str, list[float]] | None = None
# lawd별 동 지오코딩 워밍 진행상태(중복 스레드 방지)
_dong_warm: dict[str, bool] = {}


def _dong_geo_path():
    d = get_settings().data_dir / "cache" / "geo"
    d.mkdir(parents=True, exist_ok=True)
    return d / "dong.json"


def _load_dong() -> dict[str, list[float]]:
    global _dong_cache
    if _dong_cache is None:
        try:
            _dong_cache = json.loads(_dong_geo_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _dong_cache = {}
    return _dong_cache


def _save_dong() -> None:
    try:
        _dong_geo_path().write_text(
            json.dumps(_dong_cache, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


import hashlib
import math

# 처리 시도한(성공/실패 무관) 동 — 같은 프로세스에서 재호출 방지(Nominatim은 한국 리 단위 거의 미수록)
_dong_tried: set[str] = set()


def _hash01(*parts: str) -> float:
    """문자열 → [0,1) 결정적 해시(좌표 레이아웃용)."""
    h = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _dong_base(center: list[float], dong: str, idx: int, total: int) -> tuple[float, float]:
    """동(읍·면·동)별 군집 중심 — 시군구 중심 주위에 결정적으로 분산(겹침 없이)."""
    if not dong or total <= 1:
        return center[0], center[1]
    # 황금각으로 고르게 펼치고, 동 해시로 살짝 회전·반경 변화 → 결정적이지만 자연스럽게
    ang = idx * 2.399963 + _hash01(dong) * 6.283
    rad = 0.006 + 0.011 * math.sqrt((idx + 0.5) / total)   # ~0.7~1.9km
    # 위도 보정(경도 1도가 위도보다 짧음, 한국 ~cos36°≈0.81)
    return (center[0] + rad * math.sin(ang),
            center[1] + rad * math.cos(ang) / 0.81)


def _apt_jitter(name: str) -> tuple[float, float]:
    """단지명 기반 결정적 미세 분산(같은 동 안에서 단지들이 겹치지 않게). ±~150m."""
    return ((_hash01(name, "lat") - 0.5) / 350.0,
            (_hash01(name, "lng") - 0.5) / 350.0 / 0.81)


def _warm_dongs(sido: str, region: str, dongs: list[str]) -> None:
    """도시 행정동은 Nominatim에 있을 수 있어 한 번 시도해 캐시(실패해도 재시도 안 함)."""
    cache = _load_dong()
    for dong in dongs:
        key = f"{sido} {region} {dong}"
        if key in cache or key in _dong_tried:
            continue
        _dong_tried.add(key)
        coord = _geocode_net(f"대한민국 {sido} {region} {dong}")
        if coord:
            with _dong_lock:
                cache[key] = coord
                _save_dong()


def _start_dong_warm(lawd: str, sido: str, region: str, dongs: list[str]) -> None:
    cache = _load_dong()
    todo = [d for d in dongs
            if f"{sido} {region} {d}" not in cache
            and f"{sido} {region} {d}" not in _dong_tried]
    if not todo or _dong_warm.get(lawd):
        return
    _dong_warm[lawd] = True

    def run():
        try:
            _warm_dongs(sido, region, todo)
        finally:
            _dong_warm[lawd] = False

    threading.Thread(target=run, name=f"re-dong-{lawd}", daemon=True).start()


def region_apartments(lawd: str, ym: str | None = None) -> dict:
    """한 시군구의 실거래를 **단지 단위**로 묶어 지도 마커용으로 반환(호갱노노 스타일).

    정밀 좌표는 시군구 중심점 + 동별 군집 + 단지명 미세분산으로 결정적 배치한다.
    (Nominatim이 한국 읍·면·동·리 한글주소를 거의 못 찾아, 네트워크 의존 대신 결정적 레이아웃.
     도시 행정동으로 캐시된 좌표가 있으면 그것을 우선 사용.)
    """
    sido, region = _LAWD_INFO.get(lawd, ("", ""))
    deals = realestate.deals(lawd, ym)

    # 시군구 중심(지오코딩 캐시 → 없으면 시도 중심)
    center = _cached_coord(sido, region) if sido else None
    if center is None:
        center = list(_sido_centroid(sido)) if sido else [36.5, 127.8]

    # 단지(apt+dong) 단위 그룹
    groups: dict[tuple[str, str], list[dict]] = {}
    for d in deals:
        groups.setdefault((d["apt"], d["dong"]), []).append(d)

    dongs = sorted({dong for (_apt, dong) in groups if dong})
    if sido and region and dongs:
        _start_dong_warm(lawd, sido, region, dongs)   # 도시 동만 기회적 정밀화

    dong_cache = _load_dong()
    dong_idx = {d: i for i, d in enumerate(dongs)}     # 동별 군집 위치 인덱스
    apartments: list[dict] = []
    for (apt, dong), ds in groups.items():
        ds.sort(key=lambda x: (x["date"], x["amount_eok"]), reverse=True)
        recent = ds[0]
        prices = [x["amount_eok"] for x in ds]
        areas = sorted({x["area"] for x in ds if x["area"] is not None})

        geo = dong_cache.get(f"{sido} {region} {dong}") if dong else None
        precise = geo is not None
        if precise:
            base = (geo[0], geo[1])
        else:
            base = _dong_base(center, dong, dong_idx.get(dong, 0), len(dongs))
        jt = _apt_jitter(apt + dong)
        lat = round(base[0] + jt[0], 6)
        lng = round(base[1] + jt[1], 6)

        apartments.append({
            "apt": apt, "dong": dong, "count": len(ds),
            "recent_eok": recent["amount_eok"], "recent_area": recent["area"],
            "recent_date": recent["date"], "recent_floor": recent["floor"],
            "build_year": recent["build_year"],
            "min_eok": min(prices), "max_eok": max(prices),
            "areas": areas,
            "lat": lat, "lng": lng, "approx": not precise,
            "deals": ds[:12],
        })

    apartments.sort(key=lambda a: a["recent_eok"], reverse=True)
    geocoded = sum(1 for a in apartments if not a["approx"])
    return {
        "lawd": lawd, "sido": sido, "region": region, "ym": ym,
        "count": len(apartments), "deal_count": len(deals),
        "geocoded": geocoded, "geocoding": bool(_dong_warm.get(lawd)),
        "center": center, "apartments": apartments,
    }


# --- 단지 상세(네이버 부동산 스타일): 시군구 N개월 거래이력 캐시 + 면적별 시세/실거래 ----
_HIST_MONTHS = 120          # 10년
_HIST_TTL = 7 * 24 * 3600.0  # 7일(과거월은 불변, 최신월만 갱신)
_hist_mem: dict[str, dict] = {}                 # lawd -> {ts, months, deals}
_hist_warm: dict[str, dict] = {}                # lawd -> {running, done, total, ok}
_hist_lock = threading.Lock()


def _hist_path(lawd: str):
    d = get_settings().data_dir / "cache" / "realestate" / "history"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{lawd}.json"


def _load_hist(lawd: str) -> dict | None:
    if lawd in _hist_mem:
        return _hist_mem[lawd]
    try:
        data = json.loads(_hist_path(lawd).read_text(encoding="utf-8"))
        _hist_mem[lawd] = data
        return data
    except (OSError, ValueError):
        return None


def _save_hist(lawd: str, data: dict) -> None:
    _hist_mem[lawd] = data
    try:
        _hist_path(lawd).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _hist_warm_run(lawd: str, months: int) -> None:
    yms = realestate._recent_months(months)
    st = _hist_warm[lawd] = {"running": True, "done": 0, "total": len(yms), "ok": 0}
    rows: list[dict] = []

    def run(ym):
        for a in range(3):                       # 429 백오프 재시도
            ds, ok = realestate.month_deals(lawd, ym)
            if ok:
                return ym, ds, True
            time.sleep(1.2 * (a + 1))
        return ym, ds, False

    try:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for ym, ds, ok in ex.map(run, yms):
                st["done"] += 1
                if ok:
                    st["ok"] += 1
                    rows.extend(ds)
        _save_hist(lawd, {"ts": time.time(), "months": months, "deals": rows})
    finally:
        st["running"] = False


def _ensure_hist(lawd: str, months: int) -> dict | None:
    cache = _load_hist(lawd)
    fresh = cache and (time.time() - cache.get("ts", 0) < _HIST_TTL) and cache.get("months", 0) >= months
    if fresh:
        return cache
    warm = _hist_warm.get(lawd)
    if not (warm and warm["running"]):
        with _hist_lock:
            warm = _hist_warm.get(lawd)
            if not (warm and warm["running"]):
                threading.Thread(target=_hist_warm_run, args=(lawd, months),
                                 name=f"re-hist-{lawd}", daemon=True).start()
    return cache  # 있으면(오래됐어도) 우선 보여주고 갱신은 백그라운드


def _area_bucket(area: float | None) -> float | None:
    """전용면적을 0.5㎡ 버킷으로 그룹(같은 평형 묶기)."""
    if area is None:
        return None
    return round(area * 2) / 2.0


def apartment_detail(lawd: str, apt: str, dong: str | None = None,
                     months: int = _HIST_MONTHS) -> dict:
    """한 단지의 면적별 시세/실거래 시계열 — 차트·거래이력·요약 통계.

    정적 단지정보(세대수·용적률·건설사 등)는 K-apt 미연동으로 비움(추후 연동 슬롯).
    """
    sido, region = _LAWD_INFO.get(lawd, ("", ""))
    cache = _ensure_hist(lawd, months)
    warm = _hist_warm.get(lawd) or {}

    if not cache or not cache.get("deals"):
        return {
            "lawd": lawd, "sido": sido, "region": region, "apt": apt, "dong": dong or "",
            "ready": False, "warming": bool(warm.get("running")),
            "progress": {"done": warm.get("done", 0), "total": warm.get("total", months)},
            "areas": [], "series": {}, "build_year": None, "static": _empty_static(),
            "message": "시세·실거래 수집 중… 잠시 후 자동 표시됩니다.",
        }

    mine = [d for d in cache["deals"]
            if d["apt"] == apt and (not dong or d["dong"] == dong)]
    # 면적 버킷별 그룹
    by_area: dict[float, list[dict]] = {}
    for d in mine:
        b = _area_bucket(d["area"])
        if b is not None:
            by_area.setdefault(b, []).append(d)

    areas_sorted = sorted(by_area.keys())
    areas_meta = []
    series: dict[str, list[dict]] = {}
    for b in areas_sorted:
        ds = sorted(by_area[b], key=lambda x: x["date"])
        # 월별 집계
        by_m: dict[str, list[float]] = {}
        for d in ds:
            ym = d["date"][:7]   # YYYY-MM
            by_m.setdefault(ym, []).append(d["amount_eok"])
        pts = []
        for ym in sorted(by_m):
            v = by_m[ym]
            pts.append({
                "ym": ym, "avg": round(sum(v) / len(v), 2),
                "min": round(min(v), 2), "max": round(max(v), 2), "count": len(v),
            })
        # 개별 거래(점)
        deals_pts = [{"date": d["date"], "eok": d["amount_eok"],
                      "floor": d["floor"], "area": d["area"]} for d in ds]
        key = f"{b:g}"
        series[key] = pts
        prices = [d["amount_eok"] for d in ds]
        areas_meta.append({
            "area": b, "key": key, "count": len(ds),
            "min_eok": round(min(prices), 2), "max_eok": round(max(prices), 2),
            "recent_eok": ds[-1]["amount_eok"], "recent_date": ds[-1]["date"],
            "deals": deals_pts,
        })

    build_year = mine[0]["build_year"] if mine else None
    total_deals = len(mine)
    last_date = max((d["date"] for d in mine), default=None)
    # 대표 면적: 거래 많은 순
    areas_meta.sort(key=lambda a: a["count"], reverse=True)

    return {
        "lawd": lawd, "sido": sido, "region": region, "apt": apt, "dong": dong or "",
        "ready": True, "warming": bool(warm.get("running")),
        "progress": {"done": warm.get("done", 0), "total": warm.get("total", months)},
        "months": cache.get("months", months),
        "hist_from": realestate._recent_months(cache.get("months", months))[0],
        "build_year": build_year, "total_deals": total_deals, "last_date": last_date,
        "areas": areas_meta, "series": series,
        "static": _empty_static(),
        "source": "국토교통부 실거래가(RTMS) · data.go.kr",
        "note": "월별 평균·범위는 실거래 기반 추정 시세(공식 시세·호가 아님).",
    }


def _empty_static() -> dict:
    """K-apt 미연동 — 정적 단지정보 슬롯(추후 공동주택 기본정보 API 연동 시 채움)."""
    return {
        "available": False,
        "reason": "세대수·용적률·건설사 등은 K-apt(공동주택 기본정보) API 연동 필요.",
        "households": None, "dong_count": None, "approval_date": None,
        "floors": None, "parking": None, "far": None, "bcr": None,
        "builder": None, "heating": None, "office_tel": None, "road_address": None,
    }
