"""경쟁사(동일 업종) 원가·주가변동성·뉴스 비교.

'제품 원가분해'(unit_economics)의 업종 분류를 그대로 '경쟁군'으로 재사용한다
(업종은 지식베이스 ``fundamentals/products/`` 의 모듈이 곧 정의다).
한 제품을 고르면 같은 섹터의 다른 제품(=경쟁사 제품)들을 모아
① 원가구조, ② 주가 변동성, ③ 뉴스를 나란히 비교한다.

하루하루 원자재·주가·뉴스가 달라지므로, 선택 즉시 최신 스냅샷을 보여주되
비싼 계산(DART 원가분해·RSS 뉴스)은 TTL 캐시로 흡수한다.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from app.data.fundamentals import unit_economics
from app.data.fundamentals import commodities
from app.data.fundamentals import finnhub
from app.data.infra import store
from app.data.infra import global_universe
from app.data.news import news
from app.quant import metrics

_MAX_PEERS = 8            # 한 화면에 비교할 경쟁 제품 상한
_PRICE_DAYS = 126         # 주가 비교 창(≈ 최근 6개월 거래일)
_COST_TTL = 900.0         # 원가·주가 15분 캐시
_NEWS_TTL = 300.0         # 뉴스 5분 캐시

_cost_cache: dict[str, tuple[float, dict]] = {}
_news_cache: dict[str, tuple[float, dict]] = {}
_global_cache: dict[str, tuple[float, dict]] = {}
_GLOBAL_TTL = 1800.0      # 글로벌 시총 비교 30분 캐시

# 원가분해 업종 → 글로벌 경쟁 클러스터(global_universe.CLUSTERS[*].key)
_SECTOR_CLUSTER: dict[str, str] = {
    "음식료·음료": "food_beverage",
    "화장품": "consumer",
    "제약·바이오": "pharma_bio",
    "유통·리테일": "retail",
    "반도체·전자·디스플레이": "semiconductor",
    "자동차·부품·타이어": "auto",
    "철강·비철·소재": "steel",
    "화학·정유·에너지": "oil_energy",
    "2차전지·소재": "battery",
    "운송·물류·렌탈": "transport",
    "IT·게임·엔터·미디어·통신": "bigtech_sw",
    "건설·건자재": "construction",
    "조선·방산·기계": "defense",
    "의류·패션": "apparel",
    "금융": "bank_fin",
}


def _krw_usd() -> float:
    """원 → USD 환율. Finnhub FX가 있으면 사용, 없으면 근사 폴백."""
    try:
        r = finnhub._fx_map().get("KRW")
        if r:
            return float(r)
    except Exception:
        pass
    return 0.00073


# ── 경쟁군 해석 ─────────────────────────────────────────────────────────
def _peers(product_id: str) -> tuple[str, list[dict]]:
    """(섹터명, [제품 dict...]) — 같은 섹터의 제품들. 선택 제품을 맨 앞에."""
    products = unit_economics.list_products()
    by_id = {p["id"]: p for p in products}
    base = by_id.get(product_id)
    if not base:
        raise KeyError(product_id)
    sector = base["sector"]
    peers = [p for p in products if p["sector"] == sector]
    # 선택 제품이 항상 index 0 → 잘라도 살아남는다. 그 외엔 회사명순.
    peers.sort(key=lambda p: (p["id"] != product_id, p["company"], p["product"]))
    return sector, peers[:_MAX_PEERS]


# ── ① 원가 비교 ─────────────────────────────────────────────────────────
def _cost_row(p: dict, base_id: str) -> dict | None:
    """제품 하나의 원가분해에서 비교용 핵심 지표만 추린다."""
    try:
        t = unit_economics.teardown(p["id"])
    except Exception:
        return None
    s = t["summary"]
    retail = s.get("retail_price") or 0
    material_won = sum(w["won"] for w in t["waterfall"] if w.get("kind") == "material")
    process_won = sum(w["won"] for w in t["waterfall"] if w.get("kind") == "process")
    mats = t.get("materials") or []
    return {
        "id": p["id"],
        "ticker": p["ticker"],
        "company": p["company"],
        "product": p["product"],
        "unit": t["product"].get("unit"),
        "is_base": p["id"] == base_id,
        "retail_price": s.get("retail_price"),
        "factory_price": s.get("factory_price"),
        "cogs_ratio": s.get("cogs_ratio"),
        "sga_ratio": s.get("sga_ratio"),
        "op_margin": s.get("op_margin"),
        "profit_per_unit": s.get("profit_per_unit"),
        "material_pct": round(material_won / retail, 3) if retail else None,
        "process_pct": round(process_won / retail, 3) if retail else None,
        "basis_source": t.get("basis", {}).get("source"),
        # 원가를 흔드는 핵심 원자재 top2 (지금 어디가 오르내리는지)
        "top_materials": [
            {"item": m["item"], "commodity": m.get("commodity"),
             "chg_1y": m.get("chg_1y"), "direction": m.get("direction")}
            for m in mats[:2]
        ],
    }


# ── ② 주가·변동성 비교 ──────────────────────────────────────────────────
def _price_vol(peers: list[dict]) -> dict:
    """경쟁 종목들의 종가를 한 번에 불러 100 기준 리베이스 + 연율 변동성."""
    tickers = list(dict.fromkeys(p["ticker"] for p in peers))
    wide = store.load_prices(tickers=tickers, field="close")
    if wide.empty:
        return {"dates": [], "series": {}, "vol": {}, "ret_pct": {}}
    wide = wide.tail(_PRICE_DAYS)
    dates = [d.strftime("%Y-%m-%d") for d in wide.index]
    series: dict[str, list] = {}
    vol: dict[str, float | None] = {}
    ret_pct: dict[str, float | None] = {}
    for tk in wide.columns:
        col = wide[tk].astype(float)
        valid = col.dropna()
        base = float(valid.iloc[0]) if not valid.empty else None
        # 창 시작=100 으로 리베이스 → 서로 다른 가격대의 종목을 한 축에서 비교
        series[tk] = [
            None if (v != v or not base) else round(v / base * 100.0, 2)
            for v in col
        ]
        rets = col.pct_change().dropna()
        vol[tk] = round(float(metrics.annual_volatility(rets)), 4) if rets.size > 5 else None
        # 창 구간 수익률(%)
        if base and not valid.empty:
            ret_pct[tk] = round((float(valid.iloc[-1]) / base - 1.0) * 100.0, 1)
        else:
            ret_pct[tk] = None
    return {"dates": dates, "series": series, "vol": vol, "ret_pct": ret_pct}


def compare(product_id: str) -> dict:
    """원가 + 주가 변동성 (빠른 파트). 15분 캐시."""
    now = time.time()
    hit = _cost_cache.get(product_id)
    if hit and now - hit[0] < _COST_TTL:
        return hit[1]
    sector, peers = _peers(product_id)
    rows = [r for p in peers if (r := _cost_row(p, product_id))]
    pv = _price_vol(peers)
    for r in rows:  # 편의상 변동성·수익률을 원가 행에도 병합
        r["annual_vol"] = pv["vol"].get(r["ticker"])
        r["ret_pct"] = pv["ret_pct"].get(r["ticker"])
    meta = {p["ticker"]: {"company": p["company"], "product": p["product"],
                          "is_base": p["id"] == product_id}
            for p in peers}
    out = {
        "product": product_id,
        "sector": sector,
        "as_of": commodities.AS_OF,
        "window_days": _PRICE_DAYS,
        "peers": rows,
        "price": {**pv, "meta": meta},
    }
    _cost_cache[product_id] = (now, out)
    return out


# ── ③ 경쟁사 뉴스 취합 ──────────────────────────────────────────────────
def news_compare(product_id: str, per: int = 6) -> dict:
    """경쟁군 회사들의 뉴스를 한데 모아 최신순 병합. 5분 캐시."""
    now = time.time()
    ck = f"{product_id}|{per}"
    hit = _news_cache.get(ck)
    if hit and now - hit[0] < _NEWS_TTL:
        return hit[1]
    sector, peers = _peers(product_id)
    # 같은 회사(티커) 중복 제거 — 한 회사가 여러 제품을 가질 수 있음
    companies: list[dict] = []
    seen: set[str] = set()
    for p in peers:
        if p["ticker"] in seen:
            continue
        seen.add(p["ticker"])
        companies.append({"company": p["company"], "ticker": p["ticker"]})

    def _fetch(c: dict) -> list[dict]:
        try:
            r = news.news_for(c["company"], limit=per)
        except Exception:
            return []
        out = []
        for scope in ("domestic", "global"):
            for it in r.get(scope, []):
                out.append({
                    "company": c["company"], "ticker": c["ticker"], "scope": scope,
                    "title": it.get("title"), "link": it.get("link"),
                    "source": it.get("source"), "ts": it.get("ts"),
                })
        return out

    with ThreadPoolExecutor(max_workers=min(6, len(companies) or 1)) as ex:
        items = [it for sub in ex.map(_fetch, companies) for it in sub]
    items.sort(key=lambda x: x.get("ts") or 0, reverse=True)
    out = {
        "product": product_id,
        "sector": sector,
        "companies": companies,
        "items": items[:80],
    }
    _news_cache[ck] = (now, out)
    return out


# ── ④ 글로벌 시장 규모(시가총액) 비교 ───────────────────────────────────
def global_compare(product_id: str) -> dict:
    """같은 제품군의 국내 경쟁사 + 글로벌 리더를 시가총액(USD)으로 줄세운다.

    "이 회사가 리더(예: 음료의 코카콜라)만큼 크면 몇 배 여력인지"를 보여준다.
    국내 시총은 company_profile(원)→USD, 해외 시총은 foreign_fin(Finnhub, USD).
    """
    now = time.time()
    hit = _global_cache.get(product_id)
    if hit and now - hit[0] < _GLOBAL_TTL:
        return hit[1]

    sector, peers = _peers(product_id)
    base_ticker = next((p["ticker"] for p in peers if p["id"] == product_id), None)
    cluster_key = _SECTOR_CLUSTER.get(sector)
    cluster = global_universe.cluster(cluster_key) if cluster_key else None

    krw = _krw_usd()
    prof = store.company_profiles()
    cap_by_ticker: dict[str, float] = {}
    name_by_ticker: dict[str, str] = {}
    for r in prof.to_dict("records"):
        tk = str(r.get("ticker"))
        mc = r.get("market_cap")
        name_by_ticker[tk] = r.get("name") or tk
        if mc == mc and mc is not None:  # not NaN
            cap_by_ticker[tk] = float(mc)

    members: list[dict] = []
    # 국내 경쟁사(원가분해 경쟁군, 티커 중복 제거)
    seen_tk: set[str] = set()
    for p in peers:
        if p["ticker"] in seen_tk:
            continue
        seen_tk.add(p["ticker"])
        cap_krw = cap_by_ticker.get(p["ticker"])
        members.append({
            "name": p["company"],
            "code": p["ticker"],
            "market": "KR",
            "country": "KR",
            "market_cap_usd": round(cap_krw * krw) if cap_krw else None,
            "op_margin": None,
            "change_pct": None,
            "is_base": p["ticker"] == base_ticker,
        })

    # 글로벌 리더(Finnhub 캐시). 키/캐시 없으면 이름만, 시총 None.
    foreign_enabled = finnhub.enabled()
    foreign_missing = 0
    if cluster:
        fmap = store.foreign_fin_map()
        seen_names = {m["name"] for m in members}
        for sym, label, country in cluster["foreign"]:
            f = fmap.get(sym)
            cap = None
            op = None
            chg = None
            if f:
                v = f.get("market_cap_usd")
                cap = round(float(v)) if (v is not None and v == v) else None
                op = f.get("op_margin")
                op = float(op) if (op is not None and op == op) else None
                chg = f.get("change_pct")
                chg = float(chg) if (chg is not None and chg == chg) else None
            nm = (f.get("name") if f else None) or label
            if nm in seen_names:
                continue
            seen_names.add(nm)
            if cap is None:
                foreign_missing += 1
            members.append({
                "name": nm, "code": sym, "market": "GLOBAL", "country": country,
                "market_cap_usd": cap, "op_margin": op, "change_pct": chg, "is_base": False,
            })

    # 시총순 정렬(값 있는 것 먼저), 리더 표시
    members.sort(key=lambda m: (m["market_cap_usd"] is None, -(m["market_cap_usd"] or 0)))
    leader = next((m for m in members if m["market_cap_usd"]), None)
    if leader:
        leader["is_leader"] = True
    base = next((m for m in members if m["is_base"]), None)
    headroom_x = None
    if base and base["market_cap_usd"] and leader and leader["market_cap_usd"] and base is not leader:
        headroom_x = round(leader["market_cap_usd"] / base["market_cap_usd"], 1)

    out = {
        "product": product_id,
        "sector": sector,
        "cluster": {"key": cluster_key, "label": cluster["label"] if cluster else None} if cluster else None,
        "krw_usd": krw,
        "members": members,
        "base": {"name": base["name"], "market_cap_usd": base["market_cap_usd"]} if base else None,
        "leader": {"name": leader["name"], "market_cap_usd": leader["market_cap_usd"]} if leader else None,
        "headroom_x": headroom_x,
        "foreign_enabled": foreign_enabled,
        "foreign_missing": foreign_missing,
    }
    _global_cache[product_id] = (now, out)
    return out
