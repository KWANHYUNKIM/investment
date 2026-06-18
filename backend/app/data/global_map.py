"""글로벌 경쟁지도 조립 — 한국(WICS+재무) + 해외(Finnhub)를 기술 클러스터로 합친다.

각 클러스터는 한국 종목(``industry`` 그룹에서 해당 WICS 업종을 끌어옴)과 해외 대표
경쟁사(``global_universe`` + ``foreign_fin``)를 하나로 묶어, 시총(USD 환산)·영업이익률·
등락률로 한 줄에 비교한다. '얼마나 남는지'(영업이익률) 기준으로 정렬·집계도 제공.
"""
from __future__ import annotations

import threading
import time

from app.data import industry, store, finnhub, global_universe

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 600.0


def _num(v) -> float | None:
    """JSON-safe float — pandas NaN(빈 셀)을 None으로. (해외 데이터 직렬화 보호)"""
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _krw_usd() -> float:
    return finnhub._fx_map().get("KRW", 0.00073)


def _kr_members_by_wics() -> dict[str, list[dict]]:
    """WICS 업종명 -> 한국 멤버 리스트(industry 그룹 재사용)."""
    out: dict[str, list[dict]] = {}
    for g in industry.industries():
        out[g["industry"]] = g["members"]
    return out


def _unify_kr(m: dict, krw: float) -> dict:
    cap = _num(m.get("market_cap"))
    return {
        "market": "KR", "code": m.get("ticker"), "name": m.get("name"),
        "country": "KR", "market_cap_usd": (cap * krw) if cap else None,
        "op_margin": _num(m.get("op_margin")), "change_pct": _num(m.get("change_pct")),
        "note": m.get("products"),
    }


def _clean_str(v) -> str | None:
    """pandas NaN(float) 문자열 셀을 None으로."""
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    return v


def _unify_foreign(sym: str, label: str, country: str, fin: dict | None) -> dict:
    f = fin or {}
    return {
        "market": "GL", "code": sym, "name": _clean_str(f.get("name")) or label,
        "country": _clean_str(f.get("country")) or country,
        "market_cap_usd": _num(f.get("market_cap_usd")),
        "op_margin": _num(f.get("op_margin")), "change_pct": _num(f.get("change_pct")),
        "note": _clean_str(f.get("industry")),
    }


def _assemble() -> list[dict]:
    krw = _krw_usd()
    kr_by_wics = _kr_members_by_wics()
    fmap = store.foreign_fin_map()

    clusters: list[dict] = []
    for c in global_universe.CLUSTERS:
        members: list[dict] = []
        # 한국 멤버
        for wics in c["kr_wics"]:
            for m in kr_by_wics.get(wics, []):
                members.append(_unify_kr(m, krw))
        # 해외 멤버
        for sym, label, country in c["foreign"]:
            if sym.endswith(".KS"):
                continue
            members.append(_unify_foreign(sym, label, country, fmap.get(sym)))

        # de-dup by name (some 해외 심볼 중복: BYD 등)
        seen: set = set()
        uniq: list[dict] = []
        for m in members:
            k = (m["name"] or m["code"])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(m)
        uniq.sort(key=lambda x: (x["market_cap_usd"] or 0), reverse=True)

        caps = [m["market_cap_usd"] for m in uniq if m["market_cap_usd"]]
        countries = sorted({m["country"] for m in uniq if m.get("country")})
        kr_n = sum(1 for m in uniq if m["market"] == "KR")
        # 영업이익률은 시총 가중평균 — 소형주/무매출 이상치(매출 대비 극단 마진)는 제외.
        elig = [m for m in uniq if m["op_margin"] is not None and m["market_cap_usd"]
                and abs(m["op_margin"]) <= 200]
        wsum = sum(m["market_cap_usd"] for m in elig)
        wmar = (sum(m["op_margin"] * m["market_cap_usd"] for m in elig) / wsum) if wsum else None
        clusters.append({
            "key": c["key"], "label": c["label"], "desc": c["desc"],
            "count": len(uniq), "kr_count": kr_n, "foreign_count": len(uniq) - kr_n,
            "countries": countries,
            "market_cap_usd": sum(caps) if caps else 0.0,
            "avg_op_margin": round(wmar, 1) if wmar is not None else None,
            "leader": uniq[0]["name"] if uniq else None,
            "members": uniq,
        })
    clusters.sort(key=lambda c: c["market_cap_usd"], reverse=True)
    return clusters


def clusters(force: bool = False) -> list[dict]:
    with _lock:
        if not force and _cache["data"] and time.time() - _cache["ts"] < TTL:
            return _cache["data"]
    data = _assemble()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data


def invalidate() -> None:
    with _lock:
        _cache["data"] = None


def index() -> list[dict]:
    """클러스터 요약(멤버 제외) — 좌측 목록용."""
    return [{k: c[k] for k in ("key", "label", "desc", "count", "kr_count",
                               "foreign_count", "countries", "market_cap_usd",
                               "avg_op_margin", "leader")} for c in clusters()]


def get(key: str) -> dict | None:
    return next((c for c in clusters() if c["key"] == key), None)
