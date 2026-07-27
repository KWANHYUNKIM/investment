"""전체 코스피(+코스닥) 기업 실적 — 매출·영업이익·순이익·영업이익률·전년比 + 밸류에이션.

DART 재무(financials 테이블, 최근 사업연도)와 시세·펀더멘털을 합쳐 전 종목 실적 테이블을
한 번에 반환한다. 프론트에서 정렬·검색·필터. 10분 캐시.
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
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _meta_map() -> dict:
    q = store.latest_quotes(market="KR")
    out: dict = {}
    if q is None or q.empty:
        return out
    secmap = store.sector_map()
    for r in q.to_dict("records"):
        out[r["ticker"]] = {"name": r.get("name"), "sector": secmap.get(r["ticker"]) or r.get("sector"),
                            "close": _num(r.get("close")), "volume": _num(r.get("volume"))}
    return out


def _build() -> dict:
    meta = _meta_map()
    funds = store.fundamentals_rich_map()
    fins = store.financials_latest()

    rows = []
    if fins is not None and not fins.empty:
        for r in fins.to_dict("records"):
            t = r.get("ticker")
            m = meta.get(t)
            if not m or not m.get("name"):
                continue
            f = funds.get(t, {})
            rows.append({
                "ticker": t, "name": m.get("name"), "sector": m.get("sector"),
                "period": str(r.get("period")),
                "sales": _num(r.get("sales")),               # 매출액 (억원)
                "op_profit": _num(r.get("op_profit")),       # 영업이익 (억원)
                "net_income": _num(r.get("net_income")),     # 순이익 (억원)
                "op_margin": _num(r.get("op_margin")),       # 영업이익률 (%)
                "op_yoy": _num(r.get("op_yoy")),             # 영업이익 전년比 (%)
                "per": _num(f.get("per")), "pbr": _num(f.get("pbr")), "roe": _num(f.get("roe")),
                "market_cap": _num(f.get("market_cap")),     # 시가총액 (억원)
                "close": m.get("close"),
            })

    # 기본 정렬: 시가총액 큰 순 (없으면 매출 순)
    rows.sort(key=lambda x: (x["market_cap"] or 0, x["sales"] or 0), reverse=True)

    n = len(rows)
    prof = sum(1 for r in rows if (r["op_profit"] or 0) > 0)
    improving = sum(1 for r in rows if (r["op_yoy"] or 0) > 0)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": n,
        "summary": {
            "companies": n,
            "profitable": prof,
            "profitable_pct": round(100 * prof / n) if n else None,
            "improving": improving,
            "improving_pct": round(100 * improving / n) if n else None,
        },
        "companies": rows,
        "note": "실적=DART 최근 사업연도(연결/별도 혼재 가능). 금액 단위 억원. "
                "영업이익 전년比는 직전 사업연도 대비. PER·PBR·ROE·시총은 최신 펀더멘털 스냅샷.",
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
