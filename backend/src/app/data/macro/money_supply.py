"""통화량 장기·국가 비교 — 지금 풀린 돈을 과거 경제위기·해외 주요국과 견준다.

ECOS의 한국 M2는 '지금 얼마나 풀렸나'는 보여주지만 '예전 위기 때와 견주면 어떤가,
다른 나라는 어떤가'는 답하지 못한다. 이 모듈이 그 비교축을 만든다.

  - 한국 M2 현재값·증가율   : 한국은행 ECOS (월, 십억원 → 조원)         키 필요
  - 다국 광의통화(M2) 증가율 : World Bank FM.LBL.BMNY.ZG (연 %, 한·미·일·중) 키 불필요
  - 미국 M2 최신 증가율      : FRED M2SL (월) via FinanceDataReader        키 불필요

World Bank 광의통화 증가율은 국가별 통화·집계 차이를 '증감률(%)'로 정규화해 한 자리에서
견줄 수 있게 해주는 장점이 있고, 1996년부터라 1997 외환위기(IMF)·2008 글로벌 금융위기·
2020 코로나 유동성 폭증의 시그니처를 모두 담는다. 위기 카드의 수치는 이 데이터에서 뽑되,
1929 미국 대공황처럼 데이터 이전 사건은 사료(史料) 기반 맥락으로만 싣는다.
"""
from __future__ import annotations

import datetime
import threading
import time

import requests

from app.data.macro import ecos

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 12 * 3600.0  # 연·월 지표 — 12시간

_WB_URL = (
    "https://api.worldbank.org/v2/country/KOR;USA;JPN;CHN/indicator/"
    "FM.LBL.BMNY.ZG?format=json&per_page=900&date=1996:2025"
)

# 비교에 올릴 나라 (한국 투자자 기준: 한국 + 3대 경제권/통화권)
_COUNTRIES = [
    ("KOR", "한국", "원"),
    ("USA", "미국", "달러"),
    ("CHN", "중국", "위안"),
    ("JPN", "일본", "엔"),
]


def _wb_growth() -> dict[str, list[dict]] | None:
    """World Bank 광의통화 증가율(연 %) → {iso: [{year, growth}, ...]} (연도 오름차순)."""
    j = None
    for _ in range(3):
        try:
            j = requests.get(_WB_URL, timeout=30).json()
            break
        except Exception:
            j = None
    if not isinstance(j, list) or len(j) < 2 or not j[1]:
        return None
    out: dict[str, list[dict]] = {}
    for r in j[1]:
        v = r.get("value")
        iso = r.get("countryiso3code")
        yr = r.get("date")
        if v is None or not iso or not yr:
            continue
        out.setdefault(iso, []).append({"year": int(yr), "growth": round(float(v), 1)})
    for iso in out:
        out[iso].sort(key=lambda x: x["year"])
    return out or None


def _kr_at(series: list[dict], year: int) -> float | None:
    for p in series:
        if p["year"] == year:
            return p["growth"]
    return None


def _ecos_m2_headline() -> dict | None:
    """ECOS 최신 M2(평잔) — 현재 통화량 규모(조원)와 전년동월比."""
    try:
        m = ecos._m2()  # {display: "3,994.0조원", yoy: ..., period: "2025.04", series: [...]}
    except Exception:
        m = None
    if not m:
        return None
    return {"display": m.get("display"), "period": m.get("period"), "yoy": m.get("yoy")}


def _us_m2_yoy() -> float | None:
    """FRED M2SL(미국 M2, 월) 전년동월比 — 최신 월간 글로벌 유동성 체크용."""
    try:
        import FinanceDataReader as fdr

        df = fdr.DataReader("FRED:M2SL")
        s = df.iloc[:, 0].dropna()
        if len(s) < 13:
            return None
        cur, prev = float(s.iloc[-1]), float(s.iloc[-13])
        return round((cur / prev - 1.0) * 100.0, 1) if prev else None
    except Exception:
        return None


def _mean(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 1) if vals else None


def _country_card(iso: str, name_ko: str, ccy: str, series: list[dict]) -> dict | None:
    if not series:
        return None
    recent = [p for p in series if p["year"] >= 2002]  # 2001 계열단절만 피하고 최대한 길게
    growths = [p["growth"] for p in recent]
    latest = recent[-1] if recent else series[-1]
    lo = min(recent, key=lambda x: x["growth"]) if recent else None
    hi = max(recent, key=lambda x: x["growth"]) if recent else None
    avg = _mean(growths)
    cur = latest["growth"]
    if avg is None:
        tone = "neutral"
    elif cur > avg + 1.5:
        tone = "hot"     # 평균 대비 통화량 급증(유동성 확대)
    elif cur < avg - 1.5:
        tone = "cold"    # 둔화/수축
    else:
        tone = "neutral"
    return {
        "iso": iso, "name": name_ko, "currency": ccy,
        "latest_year": latest["year"], "latest": cur,
        "avg": avg, "avg_years": f"{recent[0]['year']}~{recent[-1]['year']}" if recent else "",
        "min": lo["growth"] if lo else None, "min_year": lo["year"] if lo else None,
        "max": hi["growth"] if hi else None, "max_year": hi["year"] if hi else None,
        "tone": tone,
        "series": recent,
    }


def _crises(kr: list[dict], us: list[dict]) -> list[dict]:
    """과거 경제위기별 — 그때 통화량(광의통화)이 어떻게 움직였나 + 교훈."""
    def kg(y):  # Korea growth at year
        return _kr_at(kr, y)

    def ug(y):
        return _kr_at(us, y)

    out: list[dict] = []

    # 1929 미국 대공황 — 데이터 이전. 사료 기반 맥락(통화량 수축이 공황을 키웠다는 교훈).
    out.append({
        "key": "great_depression", "name": "미국 대공황", "period": "1929–1933",
        "scope": "미국 (부동산·주식 버블 붕괴)", "tone": "cold",
        "kr_growth": None, "us_growth": None,
        "headline": "통화량 약 −30% 대수축",
        "narrative": "주식·부동산 버블이 꺼지자 은행이 줄도산하며 시중 통화량(M2)이 1929~33년 "
                     "약 3분의 1 줄었다. 프리드먼은 '연준이 돈을 풀지 않아 불황을 키웠다'고 봤다.",
        "lesson": "통화량이 줄면(디플레) 자산가격·실물이 함께 무너진다 — 이후 위기마다 중앙은행이 "
                  "돈을 푸는 근거가 됐다.",
        "data_note": "한국 데이터 이전 사건 — 사료 기반 맥락",
    })

    # 1997-98 아시아 외환위기 / IMF
    out.append({
        "key": "imf", "name": "아시아 외환위기 (IMF)", "period": "1997–1998",
        "scope": "한국·아시아 (외환·금융 위기)", "tone": "mixed",
        "kr_growth": [{"year": y, "growth": kg(y)} for y in (1997, 1998, 1999) if kg(y) is not None],
        "us_growth": None,
        "headline": f"한국 광의통화 '98 {_sign(kg(1998))} · '99 {_sign(kg(1999))}",
        "narrative": "외환보유액이 바닥나 IMF 구제금융을 받았다. 초기엔 환율·금리가 폭등(긴축)하고 "
                     "기업·은행이 무더기 도산했지만, 구조조정 뒤 원화 약세와 유동성 공급이 겹치며 "
                     "광의통화 증가율은 오히려 20%대로 튀었다.",
        "lesson": "외화가 마르면 통화량 통제권을 잃는다 — 이후 한국은 외환보유액을 위기 전 "
                  "수백억 달러에서 4천억 달러대로 쌓아 같은 사태를 막아왔다.",
        "data_note": None,
    })

    # 2008-09 글로벌 금융위기
    out.append({
        "key": "gfc", "name": "글로벌 금융위기", "period": "2008–2009",
        "scope": "미국발 (서브프라임 부동산 버블)", "tone": "mixed",
        "kr_growth": [{"year": y, "growth": kg(y)} for y in (2008, 2009) if kg(y) is not None],
        "us_growth": [{"year": y, "growth": ug(y)} for y in (2008, 2009) if ug(y) is not None],
        "headline": f"한국 '08 {_sign(kg(2008))} · 미국 양적완화(QE) 개시",
        "narrative": "미국 부동산 버블과 파생상품이 한꺼번에 무너지자 연준은 사상 처음 양적완화(QE)로 "
                     "달러를 대량 공급했다. 한국도 한·미 통화스와프와 금리 인하로 유동성을 풀어 "
                     "광의통화 증가율을 두 자릿수 가까이 유지했다.",
        "lesson": "버블의 진원은 '값이 오르는데 빚으로 산 자산'(그땐 미국 집) — 통화량·가계부채가 "
                  "함께 급증하는 구간을 경계 신호로 본다.",
        "data_note": None,
    })

    # 2020-21 코로나
    out.append({
        "key": "covid", "name": "코로나19 유동성", "period": "2020–2021",
        "scope": "전 세계 (팬데믹 대응 돈풀기)", "tone": "hot",
        "kr_growth": [{"year": y, "growth": kg(y)} for y in (2020, 2021) if kg(y) is not None],
        "us_growth": [{"year": y, "growth": ug(y)} for y in (2020, 2021) if ug(y) is not None],
        "headline": f"미국 '20 {_sign(ug(2020))} 역대급 · 한국 '21 {_sign(kg(2021))}",
        "narrative": "각국이 동시에 금리를 0으로 내리고 재난지원금을 뿌리며 통화량이 폭증했다. "
                     "미국 M2는 한 해 20%대로 사상 최대폭 늘었고, 그 돈이 주식·부동산·코인으로 "
                     "흘러 자산가격을 끌어올렸다.",
        "lesson": "통화량이 급증하면 시차를 두고 물가·자산가격이 오른다 — 2022년 인플레와 "
                  "긴축은 이 돈풀기의 청구서였다.",
        "data_note": None,
    })

    # 2022-23 글로벌 긴축
    out.append({
        "key": "tightening", "name": "인플레·긴축", "period": "2022–2023",
        "scope": "전 세계 (금리 급등·돈줄 죄기)", "tone": "cold",
        "kr_growth": [{"year": y, "growth": kg(y)} for y in (2022, 2023) if kg(y) is not None],
        "us_growth": [{"year": y, "growth": ug(y)} for y in (2022, 2023) if ug(y) is not None],
        "headline": f"미국 M2 사상 첫 감소 · 한국 '22 {_sign(kg(2022))}로 둔화",
        "narrative": "코로나 돈풀기가 40년 만의 인플레로 돌아오자 연준·한은이 금리를 가파르게 올렸다. "
                     "미국 M2는 통계 이래 처음으로 전년보다 줄었고, 한국 광의통화 증가율도 4%대로 "
                     "급격히 식었다.",
        "lesson": "통화량 증가율이 꺾이면 위험자산(주식·부동산·코인)에서 돈이 빠진다 — 2022년 "
                  "동반 하락이 그 결과였다.",
        "data_note": None,
    })

    return out


def _sign(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else ''}{v}%"


def _verdict(kr_series: list[dict], kr_headline: dict | None) -> dict:
    """현재 한국 통화량 증가율을 장기평균·위기 수준과 견준 한 줄 판정."""
    recent = [p for p in kr_series if p["year"] >= 2002]
    avg = _mean([p["growth"] for p in recent])
    latest = recent[-1] if recent else None
    # 최신 증가율: ECOS 월간 YoY가 있으면 그걸(더 최신), 없으면 World Bank 최신 연도값.
    cur = None
    cur_label = ""
    if kr_headline and kr_headline.get("yoy") is not None:
        cur = kr_headline["yoy"]
        cur_label = f"{kr_headline.get('period', '')} 전년동월比"
    elif latest:
        cur = latest["growth"]
        cur_label = f"{latest['year']}년"
    if cur is None or avg is None:
        text = "통화량 증가율 데이터를 충분히 받지 못했습니다."
        stance = "중립"
    else:
        if cur > avg + 2:
            stance, why = "유동성 확대", "장기평균보다 빠르게 늘어 자산시장에 우호적"
        elif cur < avg - 2:
            stance, why = "유동성 둔화", "장기평균보다 느려 돈줄이 죄어드는 국면"
        else:
            stance, why = "평탄", "장기평균 수준의 완만한 증가"
        text = (f"현재 한국 통화량 증가율은 {_sign(cur)}({cur_label})로, 2002년 이후 평균 "
                f"{_sign(avg)} 대비 '{stance}' 국면입니다 — {why}.")
    return {"stance": stance, "current": cur, "current_label": cur_label,
            "avg_20y": avg, "narrative": text}


def snapshot(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    wb = _wb_growth()
    if not wb:
        return {"available": False,
                "reason": "World Bank 통화량 데이터 응답 없음 — 잠시 후 다시 시도하세요.",
                "crises": [], "countries": []}

    kr_series = wb.get("KOR", [])
    us_series = wb.get("USA", [])
    kr_headline = _ecos_m2_headline()
    us_yoy = _us_m2_yoy()

    countries = [c for c in (_country_card(iso, ko, ccy, wb.get(iso, []))
                             for iso, ko, ccy in _COUNTRIES) if c]

    data = {
        "available": True,
        "as_of": str(kr_series[-1]["year"]) if kr_series else None,
        "source": "World Bank(광의통화 증가율, 연) · 한국은행 ECOS(한국 M2, 월) · FRED(미국 M2, 월)",
        "headline": {
            "kr_m2_display": kr_headline.get("display") if kr_headline else None,
            "kr_m2_period": kr_headline.get("period") if kr_headline else None,
            "kr_m2_yoy": kr_headline.get("yoy") if kr_headline else None,
            "us_m2_yoy": us_yoy,
        },
        "verdict": _verdict(kr_series, kr_headline),
        "crises": _crises(kr_series, us_series),
        "countries": countries,
        "note": "광의통화(M2 등 broad money) 증가율은 나라마다 다른 통화 단위를 증감률(%)로 "
                "정규화해 한 자리에서 비교한다. 위기 카드 수치는 World Bank 연간, 한국 현재값은 "
                "한국은행 ECOS 월간 기준. (World Bank 2001년 한국 계열단절은 비교에서 제외)",
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
