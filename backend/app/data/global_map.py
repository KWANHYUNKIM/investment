"""글로벌 경쟁지도 조립 — 한국(WICS+재무) + 해외(Finnhub)를 기술 클러스터로 합친다.

각 클러스터는 한국 종목(``industry`` 그룹에서 해당 WICS 업종을 끌어옴)과 해외 대표
경쟁사(``global_universe`` + ``foreign_fin``)를 하나로 묶어, 시총(USD 환산)·영업이익률·
등락률로 한 줄에 비교한다. '얼마나 남는지'(영업이익률) 기준으로 정렬·집계도 제공.
"""
from __future__ import annotations

import threading
import time

from app.data import industry, store, finnhub, financials, global_universe, global_intel

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


def _eok_to_usd(v, krw: float):
    """억원 → USD."""
    n = _num(v)
    return n * 1e8 * krw if n is not None else None


def _unify_kr(m: dict, krw: float, fmap: dict, fund: dict, bs: dict) -> dict:
    cap = _num(m.get("market_cap"))
    tk = m.get("ticker")
    f = fmap.get(tk, {})
    fu = fund.get(tk, {})
    b = bs.get(tk, {})
    sales = _num(f.get("sales"))
    op = _num(f.get("op_profit"))
    ni = _num(f.get("net_income"))
    net_margin = round(ni / sales * 100, 2) if (sales and ni is not None) else None
    debt, equity = _num(b.get("부채총계")), _num(b.get("자본총계"))
    de = round(debt / equity * 100, 1) if (debt is not None and equity) else None
    # 투자효율 — DART 자산총계(원) 기준. 매출/이익은 억원이라 자산도 억원으로 환산.
    assets_eok = (lambda a: a / 1e8 if a else None)(_num(b.get("자산총계")))
    roa = round(ni / assets_eok * 100, 1) if (ni is not None and assets_eok) else None
    asset_turn = round(sales / assets_eok, 2) if (sales is not None and assets_eok) else None
    # ROIC 근사: 세후영업이익(법인세 22% 가정) / 총자산. (무료 데이터로 순차입금 분리 불가 → 총자산 기준 근사)
    roic = round(op * 0.78 / assets_eok * 100, 1) if (op is not None and assets_eok) else None
    return {
        "market": "KR", "code": tk, "name": m.get("name"), "country": "KR",
        "market_cap_usd": (cap * krw) if cap else None,
        "revenue_usd": _eok_to_usd(sales, krw),
        "op_profit_usd": _eok_to_usd(op, krw),
        "net_income_usd": _eok_to_usd(ni, krw),
        "op_margin": _num(f.get("op_margin")), "net_margin": net_margin,
        "gross_margin": None,
        "roe": _num(fu.get("roe")), "debt_equity": de,
        "pe": _num(fu.get("per")), "pb": _num(fu.get("pbr")),
        "div_yield": _num(fu.get("div_yield")),
        "roic": roic, "roa": roa, "asset_turnover": asset_turn,
        "ev_ebitda": None, "rev_growth": None, "eps_growth": None,
        "rev_cagr5y": None, "interest_cov": None,
        "op_yoy": _num(f.get("yoy")),
        "fy": f.get("period"),
        "change_pct": _num(m.get("change_pct")),
        "note": m.get("products"),
        "profile": global_intel.profile_for(m.get("name")),
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
        "revenue_usd": _num(f.get("revenue_usd")),
        "op_profit_usd": _num(f.get("op_profit_usd")),
        "net_income_usd": _num(f.get("net_income_usd")),
        "op_margin": _num(f.get("op_margin")), "net_margin": _num(f.get("net_margin")),
        "gross_margin": _num(f.get("gross_margin")),
        "roe": _num(f.get("roe")),
        # Finnhub totalDebt/totalEquity는 배수 → 한국 부채비율(%)과 단위 맞추려 ×100.
        "debt_equity": (lambda x: round(x * 100, 1) if x is not None else None)(_num(f.get("debt_equity"))),
        "pe": _num(f.get("pe")), "pb": _num(f.get("pb")),
        "div_yield": _num(f.get("div_yield")),
        "roic": _num(f.get("roic")), "roa": _num(f.get("roa")),
        "asset_turnover": _num(f.get("asset_turnover")),
        "ev_ebitda": _num(f.get("ev_ebitda")),
        "rev_growth": _num(f.get("rev_growth")), "eps_growth": _num(f.get("eps_growth")),
        "rev_cagr5y": _num(f.get("rev_cagr5y")), "interest_cov": _num(f.get("interest_cov")),
        "op_yoy": None,
        "fy": None,
        "change_pct": _num(f.get("change_pct")),
        "note": _clean_str(f.get("industry")),
        "profile": global_intel.profile_for(label) or global_intel.profile_for(_clean_str(f.get("name"))),
    }


def _assemble() -> list[dict]:
    krw = _krw_usd()
    kr_by_wics = _kr_members_by_wics()
    fmap = store.foreign_fin_map()
    kr_fin = financials.latest_op_map()        # ticker -> 매출/영업이익/순이익
    kr_fund = store.fundamentals_latest_map()  # ticker -> per/pbr/roe/div_yield
    kr_bs = store.dart_latest_bs_map()         # ticker -> 부채총계/자본총계

    clusters: list[dict] = []
    for c in global_universe.CLUSTERS:
        members: list[dict] = []
        # 한국 멤버
        for wics in c["kr_wics"]:
            for m in kr_by_wics.get(wics, []):
                members.append(_unify_kr(m, krw, kr_fin, kr_fund, kr_bs))
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
            "tech": global_intel.is_tech(c["key"]),
            "battlegrounds": global_intel.battlegrounds(c["key"]),
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
                               "avg_op_margin", "leader", "tech")}
            | {"battleground_count": len(c.get("battlegrounds") or [])}
            for c in clusters()]


def get(key: str) -> dict | None:
    return next((c for c in clusters() if c["key"] == key), None)
