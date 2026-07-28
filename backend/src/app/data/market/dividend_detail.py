"""종목 단위 배당 심층 분석.

배당 투자 전 반드시 점검할 것을 한 종목에 대해 모아 준다:
  1) 배당률 = 주당배당금(DPS) ÷ 현재가 × 100 (%)
  2) 투자 전 체크리스트
     - 매출:       돈을 벌고 있는 회사인지
     - 순이익:     실제 주머니에 챙기는 돈이 늘고 있는지
     - 영업현금흐름: 피가 잘 도는 건강한 기업인지
     - 배당연수:   신뢰할 수 있는 기업인지
     - 배당성장률: 주주 친화적인 기업인지
  3) 3대 경제위기(2000 IT버블·2008 리먼·2020 팬데믹) 배당 내역 — 위기 방어력

데이터: 현재가·배당수익률(store), 연간 매출/순이익/DPS(네이버), 영업현금흐름(DART),
위기 배당(dividend_history 큐레이션). 캐시 10분(종목별).
"""
from __future__ import annotations

import threading
import time

from app.data.infra import store
from app.data.loaders import naver
from app.data.loaders import sec_edgar
from app.data.market import dividend_history
from app.data.market import dividend_royalty
from app.data.fundamentals import dart_financials

_lock = threading.Lock()
_cache: dict[str, dict] = {}  # ticker -> {"ts", "data"}
TTL = 600.0


def _num(v):
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


# ── 현재가·이름·섹터 (전 종목 스냅샷 캐시, 60초) ──────────────────────────
_meta_lock = threading.Lock()
_meta_cache: dict = {"ts": 0.0, "map": None}


def _meta_map() -> dict:
    with _meta_lock:
        if _meta_cache["map"] is not None and time.time() - _meta_cache["ts"] < 60:
            return _meta_cache["map"]
    q = store.latest_quotes(market="KR")
    secmap = store.sector_map()
    out: dict = {}
    if q is not None and not q.empty:
        for r in q.to_dict("records"):
            out[r["ticker"]] = {
                "name": r.get("name"),
                "sector": secmap.get(r["ticker"]) or r.get("sector"),
                "close": _num(r.get("close")),
            }
    with _meta_lock:
        _meta_cache["ts"] = time.time()
        _meta_cache["map"] = out
    return out


def _trend(series: dict[int, float]) -> str | None:
    """비추정 연도 시계열의 추세 판정."""
    if not series or len(series) < 2:
        return None
    ys = sorted(series)
    first, last = series[ys[0]], series[ys[-1]]
    if first is None or last is None or first == 0:
        return None
    chg = (last - first) / abs(first)
    if chg > 0.03:
        return "증가"
    if chg < -0.03:
        return "감소"
    return "정체"


def _metric(series_map: dict[int, float], years_meta: list[dict], unit: str) -> dict:
    """연도 시계열 → {series:[{year,value,estimate}], latest, trend, unit}."""
    # 네이버 컨센서스(추정) 컬럼은 값이 손상된 경우가 많아 확정 사업연도만 노출.
    est = {y["year"]: y.get("estimate", False) for y in years_meta}
    actual = {y: v for y, v in series_map.items() if not est.get(y) and v is not None}
    rows = [{"year": y, "value": actual[y], "estimate": False} for y in sorted(actual)]
    latest = None
    if actual:
        latest = {"year": max(actual), "value": actual[max(actual)]}
    return {"series": rows, "latest": latest, "trend": _trend(actual), "unit": unit}


def _dividend_stats(dps_map: dict[int, float], years_meta: list[dict]) -> dict:
    """배당연수·배당성장률(CAGR) — 비추정 연도의 DPS 기준."""
    est = {y["year"]: y.get("estimate", False) for y in years_meta}
    actual = {y: v for y, v in dps_map.items() if not est.get(y) and v is not None}
    ys = sorted(actual)
    # 배당연수: 최신 연도부터 뒤로, DPS>0 이 연속으로 이어진 햇수
    streak = 0
    for y in reversed(ys):
        if actual[y] and actual[y] > 0:
            streak += 1
        else:
            break
    # 배당성장률(CAGR): 배당 있는 첫 해→마지막 해
    pos_years = [y for y in ys if actual[y] and actual[y] > 0]
    cagr = None
    if len(pos_years) >= 2:
        a, b = actual[pos_years[0]], actual[pos_years[-1]]
        n = pos_years[-1] - pos_years[0]
        if a > 0 and n >= 1:
            cagr = round(((b / a) ** (1 / n) - 1) * 100, 1)
    return {
        "div_years": streak,
        "div_cagr": cagr,
        "window": [ys[0], ys[-1]] if ys else None,
        "dps_series": [{"year": y, "dps": actual[y]} for y in ys],
    }


def detail(ticker: str) -> dict:
    ticker = (ticker or "").strip()
    with _lock:
        c = _cache.get(ticker)
        if c and time.time() - c["ts"] < TTL:
            return c["data"]
    data = _build_us(ticker) if sec_edgar.is_us_ticker(ticker) else _build(ticker)
    with _lock:
        _cache[ticker] = {"ts": time.time(), "data": data}
    return data


def _build(ticker: str) -> dict:
    meta = _meta_map().get(ticker, {})
    name = meta.get("name")
    close = meta.get("close")
    funds = store.fundamentals_latest_map().get(ticker, {})
    div_yield_snap = _num(funds.get("div_yield"))

    # 연간 매출/영업이익/순이익/DPS/ROE (네이버)
    try:
        annual = naver.fetch_annual(ticker)
    except Exception:
        annual = {}
    years_meta = annual.get("years", [])
    series = annual.get("series", {})

    rev = _metric(series.get("매출액", {}), years_meta, "억원")
    net = _metric(series.get("당기순이익", {}), years_meta, "억원")
    roe = _metric(series.get("ROE", {}), years_meta, "%")
    dps_map = series.get("주당배당금", {})
    dstats = _dividend_stats(dps_map, years_meta)

    # 영업활동현금흐름 (DART, 원). 없으면 lazy fetch 후 재조회.
    cf_rows = store.dart_cashflow_operating(ticker)
    if not cf_rows and dart_financials.enabled():
        try:
            dart_financials.get(ticker)
            cf_rows = store.dart_cashflow_operating(ticker)
        except Exception:
            cf_rows = []
    cf_series = {r["year"]: (r["amount"] / 1e8 if r["amount"] is not None else None) for r in cf_rows}
    ocf = _metric(cf_series, [{"year": r["year"], "estimate": False} for r in cf_rows], "억원")
    ocf["available"] = bool(cf_rows)
    if not cf_rows:
        ocf["note"] = ("DART 키 미설정 또는 미수집" if not dart_financials.enabled()
                       else "DART에 해당 종목 현금흐름표 없음")

    # 배당률 = DPS ÷ 현재가 × 100
    est = {y["year"]: y.get("estimate", False) for y in years_meta}
    actual_dps = {y: v for y, v in dps_map.items() if not est.get(y) and v is not None}
    dps_latest = actual_dps[max(actual_dps)] if actual_dps else None
    if dps_latest is None and close and div_yield_snap:
        dps_latest = round(close * div_yield_snap / 100)  # 추정 폴백
        dps_estimated = True
    else:
        dps_estimated = False
    div_yield = None
    if dps_latest is not None and close:
        div_yield = round(dps_latest / close * 100, 2)
    elif div_yield_snap:
        div_yield = round(div_yield_snap, 2)

    crises = dividend_history.crisis_dividends(ticker)

    return {
        "ticker": ticker,
        "name": name,
        "sector": meta.get("sector"),
        "market": "KR",
        "currency": "KRW",
        "close": round(close) if close else None,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dividend": {
            "dps": round(dps_latest) if dps_latest is not None else None,
            "dps_estimated": dps_estimated,
            "div_yield": div_yield,
            "formula": "배당률(%) = 주당배당금 ÷ 현재가 × 100",
        },
        "checklist": {
            "revenue": {**rev, "why": "돈을 벌고 있는 회사인지"},
            "net_income": {**net, "why": "실제 주머니에 챙기는 돈이 늘고 있는지"},
            "op_cash_flow": {**ocf, "why": "피가 잘 도는 건강한 기업인지"},
            "div_years": {"value": dstats["div_years"], "window": dstats["window"],
                          "why": "신뢰할 수 있는 기업인지"},
            "div_growth": {"cagr": dstats["div_cagr"], "series": dstats["dps_series"],
                           "window": dstats["window"], "why": "주주 친화적인 기업인지"},
            "roe": roe,
        },
        "crises": crises,  # None이면 큐레이션 미포함(프론트에서 안내)
        "note": ("매출·순이익·주당배당금은 네이버 최근 3~4개 사업연도, 영업현금흐름은 "
                 "DART(2015~), 3대 위기 배당은 검증된 주요 배당주 큐레이션 실데이터입니다."),
    }


# ── 미국 종목 (SEC EDGAR + FDR 현재가 + 배당왕/귀족) ───────────────────────
def _us_price(ticker: str) -> float | None:
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(ticker.upper())
        if df is None or df.empty:
            return None
        return _num(df.iloc[-1].get("Close"))
    except Exception:
        return None


def _us_metric(series_map: dict[int, float], unit: str, scale: float = 1.0) -> dict:
    rows = [{"year": y, "value": series_map[y] / scale, "estimate": False} for y in sorted(series_map)]
    scaled = {y: v / scale for y, v in series_map.items()}
    latest = None
    if scaled:
        latest = {"year": max(scaled), "value": scaled[max(scaled)]}
    return {"series": rows, "latest": latest, "trend": _trend(scaled), "unit": unit}


def _us_crises(dps: dict[int, float], royalty: dict | None) -> dict:
    """미국 3대 위기 배당 — SEC DPS(2009~) + 배당왕/귀족 연속증액 근거."""
    tier = (royalty or {}).get("tier")
    yrs = (royalty or {}).get("years")
    out = []
    for c in dividend_history.CRISES:
        rows, prev, have = [], None, False
        for y in c["years"]:
            v = dps.get(y)
            if v is not None:
                v = round(v, 4)
                have = True
            rows.append({"year": y, "dps": v, "verdict": dividend_history._verdict(prev, v)})
            if v is not None:
                prev = v
        # 요약: 실제 삭감 여부 우선, 없으면 배당왕/귀족 연속증액 근거
        cut = any(r["verdict"] in ("삭감", "중단") for r in rows)
        if have and cut:
            summary = "위기 중 배당 삭감 이력 있음"
        elif have:
            summary = "위기에도 배당 유지/증가"
        elif tier == "king":
            summary = "배당왕 기록상 이 시기에도 배당 증액(50년+ 연속)"
        elif tier == "aristocrat" and (yrs or 0) >= (2025 - c["years"][0]):
            summary = "배당귀족 기록상 배당 증액 지속(25년+ 연속)"
        else:
            summary = "해당 시기 SEC 배당 데이터 없음(2009년 이후만 제공)"
        out.append({"key": c["key"], "label": c["label"], "rows": rows, "summary": summary})
    sources = ["SEC EDGAR (data.sec.gov)"]
    notes = ("미국 배당은 SEC XBRL(2009년~) 주당배당금입니다. 2009년 이전(2000·2008 일부)은 "
             "SEC 데이터가 없어, 배당왕/귀족 연속 증액 기록으로 위기 방어력을 표기합니다.")
    if royalty:
        notes = f"{royalty.get('tier_label','')} · 연속 증액 {yrs}년. " + notes
    return {"available": True, "name": (royalty or {}).get("name"),
            "notes": notes, "sources": sources, "crises": out}


def _build_us(ticker: str) -> dict:
    ticker = ticker.strip().upper()
    fund = sec_edgar.fundamentals(ticker)
    royalty = dividend_royalty.lookup(ticker)
    if not fund:
        # SEC에 없으면 최소 정보(배당왕/귀족 등재분)라도
        name = (royalty or {}).get("name") or ticker
        return {"ticker": ticker, "name": name, "sector": (royalty or {}).get("sector"),
                "market": "US", "currency": "USD", "close": _us_price(ticker),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "dividend": {"dps": None, "dps_estimated": False, "div_yield": (royalty or {}).get("yield"),
                             "formula": "배당률(%) = 주당배당금 ÷ 현재가 × 100"},
                "checklist": None, "crises": None,
                "note": "SEC EDGAR에서 이 종목의 재무데이터를 찾지 못했습니다(ETF·신규상장 등)."}

    close = _us_price(ticker)
    rev = fund["revenue"]; net = fund["net_income"]; ocf = fund["op_cash_flow"]; dps = fund["dps"]

    # 매출/순이익/영업현금흐름 — 백만$ 단위
    m_rev = {**_us_metric(rev, "백만$", 1e6), "why": "돈을 벌고 있는 회사인지"}
    m_net = {**_us_metric(net, "백만$", 1e6), "why": "실제 주머니에 챙기는 돈이 늘고 있는지"}
    m_ocf = {**_us_metric(ocf, "백만$", 1e6), "why": "피가 잘 도는 건강한 기업인지", "available": bool(ocf)}

    # 배당연수/성장률: 배당왕/귀족 등재값 우선, 없으면 SEC DPS로 계산
    ys = sorted(dps)
    streak = 0
    for y in reversed(ys):
        if dps[y] and dps[y] > 0:
            streak += 1
        else:
            break
    div_years = (royalty or {}).get("years") or streak
    cagr = None
    pos = [y for y in ys if dps[y] and dps[y] > 0]
    if len(pos) >= 2:
        a, b, n = dps[pos[0]], dps[pos[-1]], pos[-1] - pos[0]
        if a > 0 and n >= 1:
            cagr = round(((b / a) ** (1 / n) - 1) * 100, 1)

    dps_latest = dps[max(pos)] if pos else None
    div_yield = None
    if dps_latest is not None and close:
        div_yield = round(dps_latest / close * 100, 2)
    elif (royalty or {}).get("yield"):
        div_yield = royalty["yield"]

    return {
        "ticker": ticker,
        "name": fund.get("name") or (royalty or {}).get("name") or ticker,
        "sector": (royalty or {}).get("sector"),
        "market": "US",
        "currency": "USD",
        "close": round(close, 2) if close else None,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "royalty": ({"tier": royalty["tier"], "tier_label": royalty["tier_label"],
                     "years": royalty.get("years")} if royalty else None),
        "dividend": {
            "dps": round(dps_latest, 4) if dps_latest is not None else None,
            "dps_estimated": False,
            "div_yield": div_yield,
            "formula": "배당률(%) = 주당배당금 ÷ 현재가 × 100",
        },
        "checklist": {
            "revenue": m_rev,
            "net_income": m_net,
            "op_cash_flow": m_ocf,
            "div_years": {"value": div_years, "window": ([pos[0], pos[-1]] if pos else None),
                          "why": "신뢰할 수 있는 기업인지"},
            "div_growth": {"cagr": cagr, "series": [{"year": y, "dps": round(dps[y], 4)} for y in pos],
                           "window": ([pos[0], pos[-1]] if pos else None), "why": "주주 친화적인 기업인지"},
            "roe": {"series": [], "latest": None, "trend": None, "unit": "%"},
        },
        "crises": _us_crises(dps, royalty),
        "note": ("미국 종목: 매출·순이익·영업현금흐름·주당배당금은 SEC EDGAR(XBRL, 2009년~), "
                 "현재가는 FinanceDataReader, 배당연수는 배당왕/귀족 기록 기준입니다."),
    }
