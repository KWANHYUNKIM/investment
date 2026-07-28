"""통화량 심층분석 — '표시'를 넘어 비교·분석하기 위한 파생지표.

money_supply.py가 통화량 증가율을 나란히 보여준다면, 이 모듈은 그 숫자를 '관계'로
엮어 판단 가능한 형태로 만든다. 세 층:

  Tier 1 — 구조지표(분모를 붙인다)          : World Bank (연, 무키)
    · 마샬케이 M2/GDP   = 광의통화 ÷ 명목GDP   → 경제규모 대비 돈이 과한가
    · 통화유통속도       = 명목GDP ÷ 광의통화   → 돈이 도는가/고이는가
    · 실질 통화량 증가율 = 명목증가율 − 물가     → 진짜 늘어난 구매력인가
    · 민간신용/GDP                              → 돈풀기의 그림자(레버리지)

  Tier 2 — 돈의 행선지(자산가격과 정렬)      : ECOS·FinanceDataReader (무키)
    · 한국 M2 vs KOSPI·집값·금 — 같은 타임라인에 지수화 + 증가율 상관계수

  Tier 3 — 레짐·위기신호                     : ECOS·FRED (무키/ECOS키)
    · 한·미 실질금리(정책금리 − 물가), 미국 경기침체(NBER) 연표

키 없이 받을 수 있는 공개 데이터(World Bank·FRED·fdr)와 ECOS 키를 함께 쓴다.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests

from app.data.macro import ecos

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 12 * 3600.0

_ISO = [("KOR", "한국"), ("USA", "미국"), ("CHN", "중국"), ("JPN", "일본")]

# World Bank 지표 코드
_WB = {
    "m2_level": "FM.LBL.BMNY.CN",     # 광의통화 잔액(자국통화)
    "gdp": "NY.GDP.MKTP.CN",          # 명목 GDP(자국통화)
    "m2_growth": "FM.LBL.BMNY.ZG",    # 광의통화 증가율(%)
    "cpi": "FP.CPI.TOTL.ZG",          # 소비자물가 상승률(%)
    "credit": "FS.AST.PRVT.GD.ZS",    # 민간신용/GDP(%)
}


def _wb_fetch(ind: str) -> dict[str, dict[int, float]]:
    url = (f"https://api.worldbank.org/v2/country/KOR;USA;JPN;CHN/indicator/{ind}"
           f"?format=json&per_page=900&date=1996:2025")
    j = None
    for _ in range(3):
        try:
            j = requests.get(url, timeout=30).json()
            break
        except Exception:
            j = None
    out: dict[str, dict[int, float]] = {}
    if not isinstance(j, list) or len(j) < 2 or not j[1]:
        return out
    for r in j[1]:
        v, iso, yr = r.get("value"), r.get("countryiso3code"), r.get("date")
        if v is None or not iso or not yr:
            continue
        out.setdefault(iso, {})[int(yr)] = float(v)
    return out


def _wb_all() -> dict[str, dict[str, dict[int, float]]]:
    with ThreadPoolExecutor(max_workers=5) as ex:
        res = dict(zip(_WB.keys(), ex.map(_wb_fetch, _WB.values())))
    return res


# ── 작은 통계 헬퍼 ────────────────────────────────────────────────────────────
def _series(d: dict[int, float], start: int = 2000) -> list[dict]:
    return [{"year": y, "v": round(d[y], 1)} for y in sorted(d) if y >= start]


def _avg(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 1) if vals else None


def _trend(d: dict[int, float], latest_year: int) -> str:
    """latest vs 10년 전 비교로 추세 라벨."""
    if latest_year - 10 not in d or latest_year not in d:
        return ""
    cur, past = d[latest_year], d[latest_year - 10]
    diff = cur - past
    if diff > 2:
        return "상승"
    if diff < -2:
        return "하락"
    return "횡보"


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 4 or len(xs) != len(ys):
        return None
    a, b = np.array(xs), np.array(ys)
    if a.std() == 0 or b.std() == 0:
        return None
    return round(float(np.corrcoef(a, b)[0, 1]), 2)


# ── Tier 1: 구조지표 ─────────────────────────────────────────────────────────
def _structural(wb: dict) -> list[dict]:
    m2, gdp = wb.get("m2_level", {}), wb.get("gdp", {})
    grw, cpi = wb.get("m2_growth", {}), wb.get("credit", {})
    infl = wb.get("cpi", {})
    cards = []
    for iso, ko in _ISO:
        M2, GDP = m2.get(iso, {}), gdp.get(iso, {})
        yrs = sorted(set(M2) & set(GDP))
        if not yrs:
            continue
        ly = yrs[-1]
        # 마샬케이 M2/GDP(%)
        mk = {y: M2[y] / GDP[y] * 100 for y in yrs if GDP[y]}
        # 유통속도 GDP/M2
        vel = {y: GDP[y] / M2[y] for y in yrs if M2[y]}
        # 실질 통화량 증가율 = 명목 − 물가
        G, I = grw.get(iso, {}), infl.get(iso, {})
        real = {y: G[y] - I[y] for y in set(G) & set(I)}
        # 신용/GDP
        CR = cpi.get(iso, {})

        mk_avg = _avg([mk[y] for y in mk if y >= 2005])
        cards.append({
            "iso": iso, "name": ko, "latest_year": ly,
            "marshall_k": {
                "latest": round(mk.get(ly, 0), 0), "avg": round(mk_avg, 0) if mk_avg else None,
                "trend": _trend(mk, ly), "max": round(max(mk.values()), 0) if mk else None,
                "series": [{"year": y, "v": round(mk[y], 0)} for y in sorted(mk) if y >= 2000],
            },
            "velocity": {
                "latest": round(vel.get(ly, 0), 2),
                "trend": _trend(vel, ly),
                "series": [{"year": y, "v": round(vel[y], 2)} for y in sorted(vel) if y >= 2000],
            },
            "real_m2": {
                "latest": round(real[ly], 1) if ly in real else (round(real[max(real)], 1) if real else None),
                "latest_year": ly if ly in real else (max(real) if real else None),
                "series": [{"year": y, "v": round(real[y], 1)} for y in sorted(real) if y >= 2000],
            },
            "credit_gdp": {
                "latest": round(CR[max(CR)], 0) if CR else None,
                "latest_year": max(CR) if CR else None,
                "avg": round(_avg([CR[y] for y in CR if y >= 2005]) or 0, 0) if CR else None,
                "series": [{"year": y, "v": round(CR[y], 0)} for y in sorted(CR) if y >= 2000],
            },
        })
    return cards


# ── Tier 2: 돈의 행선지 (한국 M2 vs 자산가격) ────────────────────────────────
def _yearly_last(s) -> dict[int, float]:
    """pandas Series(일/월) → {연도: 연말값}."""
    try:
        y = s.resample("YE").last().dropna()
        return {int(str(i)[:4]): float(v) for i, v in y.items()}
    except Exception:
        return {}


def _index100(d: dict[int, float], years: list[int]) -> list[dict]:
    base = d[years[0]]
    return [{"year": y, "v": round(d[y] / base * 100, 0)} for y in years]


def _asset_link(wb: dict) -> dict | None:
    M2 = wb.get("m2_level", {}).get("KOR", {})
    if not M2:
        return None
    try:
        import FinanceDataReader as fdr

        def _yl(code, col="Close"):
            return _yearly_last(fdr.DataReader(code)[col].dropna())

        with ThreadPoolExecutor(max_workers=3) as ex:
            f_kospi = ex.submit(_yl, "KS11")
            f_gold = ex.submit(_yl, "GC=F")
            f_btc = ex.submit(_yl, "BTC/USD")
            kospi, gold, btc = f_kospi.result(), f_gold.result(), f_btc.result()
    except Exception:
        kospi, gold, btc = {}, {}, {}

    assets_raw = [
        ("kospi", "KOSPI 주가", kospi),
        ("gold", "금(달러)", gold),
        ("btc", "비트코인", btc),
    ]
    # 공통 연도(완성연도만): M2는 WB라 2024까지 → 진행중 당해연도 제외
    last_full = max(M2)
    assets = []
    for key, label, d in assets_raw:
        common = [y for y in sorted(set(M2) & set(d)) if 2008 <= y <= last_full]
        if len(common) < 5:
            continue
        m2g = [(M2[y] / M2[y - 1] - 1) * 100 for y in common if y - 1 in M2]
        ag = [(d[y] / d[y - 1] - 1) * 100 for y in common if y - 1 in d]
        n = min(len(m2g), len(ag))
        corr = _corr(m2g[-n:], ag[-n:]) if n >= 4 else None
        total_ret = round((d[common[-1]] / d[common[0]] - 1) * 100, 0)
        m2_total = round((M2[common[-1]] / M2[common[0]] - 1) * 100, 0)
        assets.append({
            "key": key, "label": label,
            "from": common[0], "to": common[-1],
            "series": _index100(d, common),
            "m2_series": _index100(M2, common),
            "corr": corr,
            "asset_total_ret": total_ret,
            "m2_total_ret": m2_total,
            "outpaced": "asset" if total_ret > m2_total else "m2",
        })
    if not assets:
        return None
    # 내러티브: M2 대비 가장 많이/적게 오른 자산
    best = max(assets, key=lambda a: a["asset_total_ret"])
    base_from = min(a["from"] for a in assets)
    base_to = max(a["to"] for a in assets)
    m2_tot = next((a["m2_total_ret"] for a in assets), None)
    narrative = (
        f"{base_from}~{base_to}년 한국 통화량(M2)이 약 {m2_tot:.0f}% 늘어나는 동안, "
        f"{best['label']}이(가) {best['asset_total_ret']:.0f}%로 가장 크게 반응했다. "
        "통화량 증가율과 자산수익률의 상관계수가 +면 '돈이 풀릴 때 함께 오르는' 자산이다."
    )
    return {"assets": assets, "narrative": narrative, "from": base_from, "to": base_to}


# ── Tier 3: 레짐·위기신호 ────────────────────────────────────────────────────
def _us_series(code: str):
    import FinanceDataReader as fdr
    return fdr.DataReader(code).iloc[:, 0].dropna()


def _regime() -> dict:
    out: dict = {"kr": None, "us": None, "us_recession_now": None, "recessions": [], "narrative": ""}

    # 한국 실질금리 = 기준금리 − 물가상승률(ECOS)
    try:
        br = ecos._base_rate()
        cp = ecos._cpi()
        if br and cp:
            policy = br["series"][-1]["v"]
            infl = cp["yoy"]
            out["kr"] = {"policy": round(policy, 2), "inflation": infl,
                         "real": round(policy - (infl or 0), 2), "period": br["period"]}
    except Exception:
        pass

    # 미국 실질금리 + NBER 침체(USREC)
    try:
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_ff = ex.submit(_us_series, "FRED:FEDFUNDS")
            f_cpi = ex.submit(_us_series, "FRED:CPIAUCSL")
            f_rec = ex.submit(_us_series, "FRED:USREC")
            ff, cpi, rec = f_ff.result(), f_cpi.result(), f_rec.result()
        policy = round(float(ff.iloc[-1]), 2)
        infl = round((float(cpi.iloc[-1]) / float(cpi.iloc[-13]) - 1) * 100, 1) if len(cpi) > 13 else None
        out["us"] = {"policy": policy, "inflation": infl,
                     "real": round(policy - (infl or 0), 2), "period": str(ff.index[-1])[:7]}
        out["us_recession_now"] = bool(float(rec.iloc[-1]) >= 1)
        # USREC → 침체 구간(시작~끝)
        spans, in_rec, start = [], False, None
        for ts, v in rec.items():
            if v >= 1 and not in_rec:
                in_rec, start = True, str(ts)[:7]
            elif v < 1 and in_rec:
                in_rec = False
                spans.append({"start": start, "end": str(ts)[:7]})
        if in_rec:
            spans.append({"start": start, "end": "진행중"})
        out["recessions"] = [s for s in spans if s["start"] >= "1990"]
    except Exception:
        pass

    bits = []
    if out["kr"]:
        s = "긴축적" if out["kr"]["real"] > 0.5 else "완화적" if out["kr"]["real"] < -0.5 else "중립"
        bits.append(f"한국 실질금리 {out['kr']['real']:+.1f}%p({s})")
    if out["us"]:
        s = "긴축적" if out["us"]["real"] > 0.5 else "완화적" if out["us"]["real"] < -0.5 else "중립"
        bits.append(f"미국 실질금리 {out['us']['real']:+.1f}%p({s})")
    if bits:
        out["narrative"] = (" · ".join(bits) +
                            ". 실질금리(정책금리−물가)가 +면 돈줄을 죄는 국면, −면 푸는 국면 — "
                            "통화량 증가율과 함께 보면 유동성 방향이 분명해진다.")
    return out


def snapshot(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    wb = _wb_all()
    if not wb.get("m2_level"):
        return {"available": False,
                "reason": "World Bank 데이터 응답 없음 — 잠시 후 다시 시도하세요.",
                "structural": [], "asset_link": None, "regime": None}

    structural = _structural(wb)
    asset_link = _asset_link(wb)
    regime = _regime()

    data = {
        "available": True,
        "as_of": str(max(wb["gdp"].get("KOR", {2024: 0}))),
        "source": "World Bank(구조지표·연) · ECOS(한국 집값·금리) · FRED/FinanceDataReader(자산·미국금리·NBER)",
        "structural": structural,
        "asset_link": asset_link,
        "regime": regime,
        "note": "마샬케이=M2÷명목GDP(경제규모 대비 통화량), 유통속도=GDP÷M2, 실질통화량=명목증가율−물가, "
                "민간신용/GDP=레버리지. 자산 상관은 연 증가율 기준. World Bank는 연·1년 지연, "
                "한국 현재 금리/물가·집값은 ECOS, 미국 금리·침체는 FRED.",
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
