"""한국은행 ECOS — 국내 돈 흐름 하드데이터 (M2·가계신용·주택매매가격지수).

ETF·뉴스 같은 대용 신호가 아니라 한국은행이 집계하는 실측 거시지표로 "시중에 돈이
느나/주나, 가계 빚이 어디까지 쌓였나, 집값이 어디로 가나"를 보여준다.

검증된 통계표/항목(코드는 ECOS StatisticItemList로 확인):
  - M2(광의통화, 평잔)        161Y006 / BBHA00       월   십억원
  - 가계신용(합계)            151Y001 / 1000000      분기 십억원
  - 주택매매가격지수(전국 종합) 901Y113 / H69A·R70A   월   지수(2025.03=100)

키(ECOS_API_KEY) 없거나 호출 실패 시 available=False로 우아하게 빠진다.
"""
from __future__ import annotations

import datetime
import threading
import time

import requests

from app.core.config import get_settings

_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"
_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 12 * 3600.0  # 12시간 (월·분기 지표라 자주 받을 이유 없음)


def _search(stat: str, cycle: str, start: str, end: str, *items: str) -> list[dict] | None:
    key = get_settings().ecos_api_key
    if not key:
        return None
    url = f"{_BASE}/{key}/json/kr/1/10000/{stat}/{cycle}/{start}/{end}/" + "/".join(items)
    try:
        j = requests.get(url, timeout=15).json()
    except Exception:
        return None
    block = j.get("StatisticSearch")
    if not block or "row" not in block:
        return None
    rows = []
    for r in block["row"]:
        try:
            rows.append({"period": r["TIME"], "value": float(r["DATA_VALUE"]), "unit": r.get("UNIT_NAME", "")})
        except (KeyError, ValueError, TypeError):
            continue
    rows.sort(key=lambda x: x["period"])
    return rows or None


def _months_ago(n: int) -> str:
    d = datetime.date.today()
    y, m = d.year, d.month
    m -= n
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}{m:02d}"


def _trillion(v: float) -> float:
    """십억원 → 조원."""
    return round(v / 1000.0, 1)


def _id(v: float) -> float:
    return v


def _eok_res(v: float) -> float:
    return v / 100000.0  # 천달러 → 억달러


def _eok_ca(v: float) -> float:
    return v / 100.0     # 백만달러 → 억달러


def _span(rows: list[dict], kind: str, conv=_id) -> dict:
    """전체 기간 요약: 언제부터(from)~언제까지(to), 처음(first)→끝(last) 얼마나 변했나.

    kind=level → 누적 변화율(change_pct, %), 그 외(rate/flow/index) → 변화폭(change_delta).
    """
    fv = round(conv(rows[0]["value"]), 2)
    lv = round(conv(rows[-1]["value"]), 2)
    out = {
        "from": _fmt_period(rows[0]["period"]),
        "to": _fmt_period(rows[-1]["period"]),
        "first": fv, "last": lv, "n": len(rows), "kind": kind,
    }
    if kind == "level":
        out["change_pct"] = round((lv / fv - 1.0) * 100.0, 1) if fv else None
    else:
        out["change_delta"] = round(lv - fv, 2)
    return out


def _pack(rows: list[dict], kind: str, conv=_id) -> dict:
    """전체 시계열 + 기간 요약을 한 번에. (그래프가 전 구간을 그릴 수 있도록 series는 전체)"""
    return {
        "kind": kind,
        "span": _span(rows, kind, conv),
        "series": [{"t": _fmt_period(r["period"]), "v": round(conv(r["value"]), 2)} for r in rows],
    }


def _yoy(rows: list[dict], lag: int) -> float | None:
    """최신값 vs lag기간 전 값의 증감률(%)."""
    if len(rows) <= lag:
        return None
    cur, prev = rows[-1]["value"], rows[-1 - lag]["value"]
    return round((cur / prev - 1.0) * 100.0, 1) if prev else None


def _fmt_period(p: str) -> str:
    if "Q" in p:
        return p.replace("Q", " Q")
    return f"{p[:4]}.{p[4:]}" if len(p) == 6 else p


def _m2() -> dict | None:
    rows = _search("161Y006", "M", "200001", _months_ago(0), "BBHA00")
    if not rows:
        return None
    return {
        "key": "m2", "group": "통화·신용", "label": "M2 통화량(광의통화·평잔)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{_trillion(rows[-1]['value']):,}조원",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比",
        "desc": "통화량 증가율↑ = 시중 유동성 확대(돈이 늘어남)",
        **_pack(rows, "level", _trillion),
    }


def _household_credit() -> dict | None:
    d = datetime.date.today()
    cur_q = (d.month - 1) // 3 + 1
    rows = _search("151Y001", "Q", "2000Q1", f"{d.year}Q{cur_q}", "1000000")
    if not rows:
        return None
    return {
        "key": "household", "group": "통화·신용", "label": "가계신용(가계 빚 잔액)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{_trillion(rows[-1]['value']):,}조원",
        "yoy": _yoy(rows, 4), "yoy_label": "전년동기比",
        "desc": "가계 빚 증가율↑ = 부채로 자산 매입(과열) / 둔화 = 디레버리징",
        **_pack(rows, "level", _trillion),
    }


def _house_price() -> dict | None:
    # 901Y113은 2021.06 재기준(2025.03=100) 시리즈라 그때부터 전 구간을 받는다.
    rows = _search("901Y113", "M", "202101", _months_ago(0), "H69A", "R70A")
    if not rows:
        return None
    mom = None
    if len(rows) >= 2 and rows[-2]["value"]:
        mom = round((rows[-1]["value"] / rows[-2]["value"] - 1.0) * 100.0, 2)
    return {
        "key": "house_price", "group": "부동산", "label": "주택매매가격지수(전국·종합)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{rows[-1]['value']} ({rows[-1]['unit']})",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比",
        "mom": mom,
        "desc": "집값 지수↑ = 부동산 상승(자금 유입) · ↓ = 조정",
        **_pack(rows, "level"),
    }


def _govbond() -> dict | None:
    """국고채 3년·10년 금리(721Y001 시장금리, 월) + 장단기 스프레드(10Y−3Y)."""
    y3 = _search("721Y001", "M", "199501", _months_ago(0), "5020000")
    y10 = _search("721Y001", "M", "199501", _months_ago(0), "5050000")
    if not y3 or not y10:
        return None
    v3, v10 = round(y3[-1]["value"], 2), round(y10[-1]["value"], 2)
    spread = round(v10 - v3, 2)
    mom = None
    if len(y10) >= 2:
        mom = round(v10 - round(y10[-2]["value"], 2), 2)
    return {
        "key": "govbond", "group": "금리", "label": "국고채 금리 (3년·10년)",
        "period": _fmt_period(y10[-1]["period"]),
        "display": f"3년 {v3}% · 10년 {v10}%",
        "yoy": spread, "yoy_label": "장단기 스프레드(10Y−3Y, %p)",
        "mom": mom,
        "desc": "금리↑=자금조달비용↑·긴축 / 스프레드 축소·역전=경기 둔화 신호",
        **_pack(y10, "rate"),
    }


def _jeonse_price() -> dict | None:
    rows = _search("901Y114", "M", "202101", _months_ago(0), "H69A", "R70A")
    if not rows:
        return None
    mom = None
    if len(rows) >= 2 and rows[-2]["value"]:
        mom = round((rows[-1]["value"] / rows[-2]["value"] - 1.0) * 100.0, 2)
    return {
        "key": "jeonse_price", "group": "부동산", "label": "주택전세가격지수(전국·종합)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{rows[-1]['value']} ({rows[-1]['unit']})",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比",
        "mom": mom,
        "desc": "전세가↑ = 전세수요·자금 유입(매매 선행 신호일 때 많음)",
        **_pack(rows, "level"),
    }


def _msb() -> dict | None:
    """통화안정증권 발행잔액(191Y001 주요 국공채, 통안증권×잔액, 월) — 한은의 시중자금 흡수."""
    rows = _search("191Y001", "M", "199001", _months_ago(0), "0800000", "4")
    if not rows:
        return None
    return {
        "key": "msb", "group": "통화·신용", "label": "통화안정증권 발행잔액",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{_trillion(rows[-1]['value']):,}조원",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比",
        "desc": "한은이 시중 돈을 흡수하려 발행한 채권 잔액↑=유동성 흡수(긴축적)",
        **_pack(rows, "level", _trillion),
    }


def _base_rate() -> dict | None:
    """한국은행 기준금리(722Y001/0101000, 월) — 통화정책 기준."""
    rows = _search("722Y001", "M", "199001", _months_ago(0), "0101000")
    if not rows:
        return None
    chg = round(rows[-1]["value"] - rows[-2]["value"], 2) if len(rows) >= 2 else None
    return {
        "key": "base_rate", "group": "금리", "label": "한국은행 기준금리",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{rows[-1]['value']}%",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比(%p)",
        "mom": chg,
        "desc": "정책금리↓ = 완화(유동성 공급) / ↑ = 긴축",
        **_pack(rows, "rate"),
    }


def _cpi() -> dict | None:
    """소비자물가지수(901Y009/0 총지수, 월) — 전년동월比가 물가상승률."""
    rows = _search("901Y009", "M", "198001", _months_ago(0), "0")
    if not rows:
        return None
    return {
        "key": "cpi", "group": "물가", "label": "소비자물가지수(CPI)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{rows[-1]['value']} ({rows[-1]['unit']})",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比(물가상승률)",
        "desc": "물가상승률↑ = 긴축 압력(금리↑) / 둔화 = 완화 여지",
        **_pack(rows, "level"),
    }


def _reserves() -> dict | None:
    """외환보유액(732Y001/99 합계, 월; 천달러 → 억달러)."""
    rows = _search("732Y001", "M", "198001", _months_ago(0), "99")
    if not rows:
        return None
    return {
        "key": "reserves", "group": "대외", "label": "외환보유액",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{_eok_res(rows[-1]['value']):,.0f}억$",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比",
        "desc": "대외지급능력·환율 방어력. 감소 = 외화 유출 압력",
        **_pack(rows, "level", _eok_res),
    }


def _current_account() -> dict | None:
    """경상수지(301Y017/SA000 계절조정, 월; 백만달러 → 억달러)."""
    rows = _search("301Y017", "M", "198001", _months_ago(0), "SA000")
    if not rows:
        return None
    return {
        "key": "current_account", "group": "대외", "label": "경상수지(월·계절조정)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{_eok_ca(rows[-1]['value']):+,.1f}억$",
        "yoy": None, "yoy_label": "흑자(+)/적자(−)",
        "desc": "흑자 = 무역으로 외화 유입(원화 강세 요인)",
        **_pack(rows, "flow", _eok_ca),
    }


def _mortgage_rate() -> dict | None:
    """예금은행 주택담보대출 금리(121Y006/BECBLA0302, 신규취급액 기준, 월)."""
    rows = _search("121Y006", "M", "200101", _months_ago(0), "BECBLA0302")
    if not rows:
        return None
    chg = round(rows[-1]["value"] - rows[-2]["value"], 2) if len(rows) >= 2 else None
    return {
        "key": "mortgage_rate", "group": "금리", "label": "주택담보대출 금리",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{rows[-1]['value']}%",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比(%p)",
        "mom": chg,
        "desc": "주담대 금리↑ = 부동산 구매 비용↑(수요 둔화 압력)",
        **_pack(rows, "rate"),
    }


def _ppi() -> dict | None:
    """생산자물가지수(404Y014/*AA 총지수, 월) — 전년동월比가 PPI 상승률(CPI 선행)."""
    rows = _search("404Y014", "M", "198001", _months_ago(0), "*AA")
    if not rows:
        return None
    return {
        "key": "ppi", "group": "물가", "label": "생산자물가지수(PPI)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{rows[-1]['value']} ({rows[-1]['unit']})",
        "yoy": _yoy(rows, 12), "yoy_label": "전년동월比(PPI 상승률)",
        "desc": "생산자물가는 소비자물가(CPI)에 선행 — 인플레 방향의 선행 신호",
        **_pack(rows, "level"),
    }


def _esi() -> dict | None:
    """경제심리지수 ESI(513Y001/E1000 원계열, 월) — 기업+소비자 종합 심리(100 기준)."""
    rows = _search("513Y001", "M", "200301", _months_ago(0), "E1000")
    if not rows:
        return None
    chg = round(rows[-1]["value"] - rows[-2]["value"], 1) if len(rows) >= 2 else None
    return {
        "key": "esi", "group": "심리", "label": "경제심리지수(ESI)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{rows[-1]['value']}",
        "yoy": chg, "yoy_label": "전월比(p, 100=중립)",
        "desc": "기업+소비자 종합 심리. 100 위 = 경기 낙관(돈 돌기 쉬움)",
        **_pack(rows, "index"),
    }


def _ccsi() -> dict | None:
    """소비자심리지수 CCSI(511Y002/FME, 월) — 100 위면 소비심리 낙관."""
    rows = _search("511Y002", "M", "200807", _months_ago(0), "FME")
    if not rows:
        return None
    chg = round(rows[-1]["value"] - rows[-2]["value"], 1) if len(rows) >= 2 else None
    return {
        "key": "ccsi", "group": "심리", "label": "소비자심리지수(CCSI)",
        "period": _fmt_period(rows[-1]["period"]),
        "display": f"{rows[-1]['value']}",
        "yoy": chg, "yoy_label": "전월比(p, 100=중립)",
        "desc": "100 위 = 소비심리 낙관 / 아래 = 위축(지갑 닫음)",
        **_pack(rows, "index"),
    }


def snapshot(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    if not get_settings().ecos_api_key:
        return {"available": False,
                "reason": "ECOS_API_KEY 미설정 — backend/.env에 키를 넣으면 활성화됩니다.",
                "indicators": []}

    builders = [_m2, _household_credit, _msb, _base_rate, _govbond, _mortgage_rate,
                _cpi, _ppi, _reserves, _current_account, _esi, _ccsi,
                _house_price, _jeonse_price]
    indicators = []
    for b in builders:
        try:
            r = b()
        except Exception:
            r = None
        if r:
            indicators.append(r)

    if not indicators:
        return {"available": False,
                "reason": "ECOS API 응답 없음 — 키 활성화 지연 또는 통계 점검일 수 있습니다.",
                "indicators": []}

    data = {
        "available": True,
        "source": "한국은행 경제통계시스템(ECOS)",
        "indicators": indicators,
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
