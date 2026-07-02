"""배당·실적 (dividend ranking + earnings momentum).

미래 실적/배당락 '날짜'는 무료·오프라인 데이터로 신뢰성 있게 확보하기 어렵다. 그래서
이미 가진 데이터로 실제 도움이 되는 두 가지를 제공한다:
  - 고배당 종목: 배당수익률 상위 (재무 스냅샷 div_yield)
  - 실적 개선 종목: 최근 사업연도 영업이익 YoY 증가율 상위 (DART 기업실적)
캐시 10분.
"""
from __future__ import annotations

import threading
import time

from app.data.infra import store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 600.0


def _num(v):
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _meta_map() -> dict:
    q = store.latest_quotes(market="KR")
    out: dict = {}
    if q is None or q.empty:
        return out
    secmap = store.sector_map()  # 실제 업종(WICS); securities.sector는 시장명
    for r in q.to_dict("records"):
        out[r["ticker"]] = {"name": r.get("name"), "sector": secmap.get(r["ticker"]) or r.get("sector"),
                            "close": _num(r.get("close")), "volume": _num(r.get("volume"))}
    return out


def _build() -> dict:
    meta = _meta_map()
    funds = store.fundamentals_latest_map()
    fins = store.financials_latest()

    # 유동성 하한(잡주 배제)
    vols = sorted(v["volume"] for v in meta.values() if v.get("volume"))
    vol_floor = vols[int(len(vols) * 0.3)] if vols else 0

    # --- 고배당 ---
    div_rows = []
    for t, f in funds.items():
        dy = _num(f.get("div_yield"))
        m = meta.get(t, {})
        if dy is None or dy <= 0 or dy > 20:  # 20% 초과는 데이터 이상치(특별배당·구주가)로 제외
            continue
        if (m.get("volume") or 0) < vol_floor:
            continue
        div_rows.append({
            "ticker": t, "name": m.get("name"), "sector": m.get("sector"),
            "close": m.get("close"), "div_yield": round(dy, 2),
            "per": _num(f.get("per")), "roe": _num(f.get("roe")),
        })
    div_rows.sort(key=lambda r: -(r["div_yield"] or 0))

    # --- 실적 개선 (영업이익 YoY) ---
    earn_rows = []
    if fins is not None and not fins.empty:
        for r in fins.to_dict("records"):
            t = r.get("ticker")
            yoy = _num(r.get("op_yoy"))
            m = meta.get(t, {})
            if yoy is None:
                continue
            if (m.get("volume") or 0) < vol_floor:
                continue
            earn_rows.append({
                "ticker": t, "name": m.get("name"), "sector": m.get("sector"),
                "close": m.get("close"), "period": str(r.get("period")),
                "op_yoy": yoy, "op_margin": _num(r.get("op_margin")),
                "op_profit": _num(r.get("op_profit")),
            })
        earn_rows.sort(key=lambda r: -(r["op_yoy"] or 0))

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dividends": div_rows[:40],
        "earnings": earn_rows[:40],
        "note": "고배당=재무 스냅샷 배당수익률, 실적개선=최근 사업연도 영업이익 전년比. "
                "미래 배당락·실적발표 '일정'은 데이터 한계로 제공하지 않습니다.",
    }


def board() -> dict:
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]
    out = _build()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = out
    return out
