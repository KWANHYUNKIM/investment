"""실물경제 — 한국(ECOS) & 세계(World Bank). 돈(통화)이 아니라 '실물'이 어떻게 움직이나.

통화량·금리가 '돈의 흐름'이라면, 소비·투자·수출·고용·물가는 그 돈이 실제 경제에서
무엇을 만들어내는지를 보여준다. 한국은 정밀하게(ECOS 국민계정), 세계는 동일 기준으로
견줄 수 있게(World Bank) 둘 다 싣는다.

  한국 (ECOS 200Y108 국내총생산에 대한 지출, 실질·계절조정, 분기; 901Y027 고용):
    · 민간소비 · 설비투자 · 건설투자 · 수출 (실질, 조원)  · 취업자수 (만명)
  세계 (World Bank, 한·미·중·일·독·인도 + 세계집계 WLD, 연):
    · 소비자물가 상승률 · 민간소비 증가율 · 투자(총고정자본형성) 증가율
    · 수출 증가율 · 경상수지(GDP대비) · 실업률

한국 항목은 기존 ECOS 카드(EcosIndicator)와 같은 형태(span·series·kind)로 내보내
프론트의 그래프·클릭 확대 UI를 그대로 재사용한다. 세계 항목은 국가별 시계열을 그대로
실어 멀티라인 그래프로 비교한다.
"""
from __future__ import annotations

import datetime
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from app.data.macro import ecos

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 12 * 3600.0

# 세계 비교 대상 (세계집계 WLD를 맨 앞에)
_ENT = [
    ("WLD", "세계"), ("KOR", "한국"), ("USA", "미국"),
    ("CHN", "중국"), ("JPN", "일본"), ("DEU", "독일"), ("IND", "인도"),
]

# (key, 라벨, WB코드, 단위, kind, 해설)  kind: rate=증감률 / ratio=GDP대비 / level=수준
_WORLD_SPECS = [
    ("cpi", "소비자물가 상승률", "FP.CPI.TOTL.ZG", "%", "rate",
     "물가가 얼마나 빨리 오르나(인플레). 높으면 긴축 압력"),
    ("consumption", "민간소비 증가율", "NE.CON.PRVT.KD.ZG", "%", "rate",
     "가계가 쓰는 돈의 실질 증가율. 내수 경기의 핵심"),
    ("investment", "투자(총고정자본형성) 증가율", "NE.GDI.FTOT.KD.ZG", "%", "rate",
     "설비·건설 등 미래를 위한 지출. 성장 동력"),
    ("exports", "수출 증가율", "NE.EXP.GNFS.KD.ZG", "%", "rate",
     "재화·서비스 수출의 실질 증가율. 대외 경기"),
    ("current_account", "경상수지 (GDP 대비)", "BN.CAB.XOKA.GD.ZS", "%", "ratio",
     "무역·소득 수지 합계. +면 외화 유입(흑자국)"),
    ("unemployment", "실업률", "SL.UEM.TOTL.ZS", "%", "rate",
     "일자리 사정. 낮을수록 고용 호조"),
]


# ── 한국 (ECOS) ─────────────────────────────────────────────────────────────
def _q_end() -> str:
    d = datetime.date.today()
    return f"{d.year}Q4"


def _kr() -> list[dict]:
    out: list[dict] = []
    # 국민계정 지출항목 (실질·계절조정, 십억원 → 조원)
    specs = [
        ("priv_consumption", "민간소비 (실질)", "1010110",
         "가계가 실제로 쓴 돈(실질). 증가율↑ = 내수 회복"),
        ("facilities_invest", "설비투자 (실질)", "1020112",
         "기업의 기계·설비 투자. 제조업 경기·미래 성장의 선행 지표"),
        ("construction_invest", "건설투자 (실질)", "1020111",
         "건물·토목 건설 투자. 부동산·SOC 경기와 직결"),
        ("exports_real", "수출 (재화·서비스, 실질)", "10301",
         "한국 경제의 엔진. 실질 수출 증가율↑ = 대외 호조"),
    ]
    end = _q_end()
    for key, label, item, desc in specs:
        try:
            rows = ecos._search("200Y108", "Q", "2000Q1", end, item)
        except Exception:
            rows = None
        if not rows:
            continue
        out.append({
            "key": key, "group": "실물경제", "label": label,
            "period": ecos._fmt_period(rows[-1]["period"]),
            "display": f"{ecos._trillion(rows[-1]['value']):,}조원",
            "yoy": ecos._yoy(rows, 4), "yoy_label": "전년동기比(실질)",
            "desc": desc,
            **ecos._pack(rows, "level", ecos._trillion),
        })
    # 취업자수 (901Y027 / I61BA, 천명 → 만명)
    try:
        emp = ecos._search("901Y027", "Q", "2000Q1", end, "I61BA")
    except Exception:
        emp = None
    if emp:
        man = lambda v: round(v / 10.0, 1)  # 천명 → 만명
        out.append({
            "key": "employed", "group": "실물경제", "label": "취업자 수",
            "period": ecos._fmt_period(emp[-1]["period"]),
            "display": f"{man(emp[-1]['value']):,}만명",
            "yoy": ecos._yoy(emp, 4), "yoy_label": "전년동기比",
            "desc": "실제 일하는 사람 수. 증가율↑ = 고용 확대(소득·소비 기반)",
            **ecos._pack(emp, "level", man),
        })
    return out


# ── 세계 (World Bank) ───────────────────────────────────────────────────────
def _wb(ind: str) -> dict[str, dict[int, float]]:
    ents = ";".join(e[0] for e in _ENT)
    url = (f"https://api.worldbank.org/v2/country/{ents}/indicator/{ind}"
           f"?format=json&per_page=900&date=2000:2025")
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
        out.setdefault(iso, {})[int(yr)] = round(float(v), 1)
    return out


def _world_indicator(spec, raw: dict[str, dict[int, float]]) -> dict | None:
    key, label, _code, unit, kind, desc = spec
    entities = []
    for iso, name in _ENT:
        d = raw.get(iso)
        if not d:
            continue
        years = sorted(d)
        ly = years[-1]
        entities.append({
            "iso": iso, "name": name,
            "latest": d[ly], "latest_year": ly,
            "first_year": years[0],
            "series": [{"year": y, "v": d[y]} for y in years],
        })
    if not entities:
        return None
    world = next((e for e in entities if e["iso"] == "WLD"), None)
    return {
        "key": key, "label": label, "unit": unit, "kind": kind, "desc": desc,
        "world_latest": world["latest"] if world else None,
        "world_year": world["latest_year"] if world else None,
        "entities": entities,
    }


def _world() -> list[dict]:
    with ThreadPoolExecutor(max_workers=6) as ex:
        raws = list(ex.map(lambda s: _wb(s[2]), _WORLD_SPECS))
    out = []
    for spec, raw in zip(_WORLD_SPECS, raws):
        card = _world_indicator(spec, raw)
        if card:
            out.append(card)
    return out


def snapshot(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_kr = ex.submit(_kr)
        f_world = ex.submit(_world)
        korea, world = f_kr.result(), f_world.result()

    if not korea and not world:
        return {"available": False,
                "reason": "실물경제 데이터를 불러오지 못했습니다 — 잠시 후 다시 시도하세요.",
                "korea": [], "world": []}

    data = {
        "available": True,
        "as_of": world[0]["entities"][0]["latest_year"] if world else None,
        "source": "한국은행 ECOS(한국 국민계정·고용, 분기) · World Bank(세계 비교, 연)",
        "korea": korea,
        "world": world,
        "note": "한국은 실질·계절조정 분기 수준(조원)과 전년동기比, 세계는 World Bank 연간 "
                "증감률/GDP대비. 세계집계(WLD)는 일부 지표만 제공된다. 한국 카드도 클릭하면 "
                "전 구간 그래프가 크게 보인다.",
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
