"""한국경제 종합 진단 — "지금 어느 국면인가".

ECOS 실데이터(GDP·CPI·PPI·경상수지·M2·가계신용·기준금리·심리)를 축별로 평가해
상태(좋음/보통/주의)와 한 줄 해석을 내고, 성장×물가로 종합 국면(골디락스/과열/둔화/
스태그 우려)을 판정한다. 규칙 기반(무료·오프라인, AI 불필요). 30분 캐시.
"""
from __future__ import annotations

import threading
import time

from app.data.macro import ecos

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 1800.0

# 상태 → 색/라벨
_STATUS = {
    "good": ("좋음", "#2f9e44"),
    "neutral": ("보통", "#e8890c"),
    "warn": ("주의", "#c0392b"),
    "na": ("자료없음", "#adb5bd"),
}


def _num(v):
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _by_key(inds: list[dict]) -> dict:
    return {i["key"]: i for i in inds}


def _dir(ind: dict | None, lag: int = 12, eps: float = 0.05) -> str | None:
    """시계열 최신값 vs lag 전 값 방향(상승/동결/하락)."""
    if not ind:
        return None
    ser = ind.get("series") or []
    if len(ser) <= lag:
        return None
    cur, prev = _num(ser[-1]["v"]), _num(ser[-1 - lag]["v"])
    if cur is None or prev is None:
        return None
    if cur > prev + eps:
        return "상승"
    if cur < prev - eps:
        return "하락"
    return "동결"


def _axis(key, title, status, headline, detail, metrics):
    label, color = _STATUS[status]
    return {"key": key, "title": title, "status": status, "status_label": label,
            "color": color, "headline": headline, "detail": detail, "metrics": metrics}


def _growth_axis(ind):
    g = ind.get("gdp")
    y = _num(g and g.get("yoy"))
    if y is None:
        return _axis("growth", "성장 (경기)", "na", "GDP 자료 대기", "", [])
    if y >= 3:
        s, h = "good", f"실질 GDP 전년比 +{y}% — 견조한 확장"
    elif y >= 2:
        s, h = "good", f"실질 GDP +{y}% — 잠재성장 수준 성장"
    elif y >= 1:
        s, h = "neutral", f"실질 GDP +{y}% — 성장 둔화 국면"
    elif y >= 0:
        s, h = "warn", f"실질 GDP +{y}% — 저성장·경기 부진"
    else:
        s, h = "warn", f"실질 GDP {y}% — 역성장(경기 위축)"
    return _axis("growth", "성장 (경기)", s, h,
                 "GDP 실질성장률은 경기 확장/위축의 종합 신호입니다.",
                 [{"k": "실질성장률(YoY)", "v": f"{y:+.1f}%"}, {"k": "기준", "v": g.get("period", "")}])


def _price_axis(ind):
    cpi = ind.get("cpi"); ppi = ind.get("ppi")
    c = _num(cpi and cpi.get("yoy")); p = _num(ppi and ppi.get("yoy"))
    if c is None:
        return _axis("price", "물가 (인플레이션)", "na", "CPI 자료 대기", "", [])
    if c < 1.5:
        s, h = "neutral", f"소비자물가 +{c}% — 목표(2%) 하회, 완화 여지"
    elif c <= 2.5:
        s, h = "good", f"소비자물가 +{c}% — 목표 부근 안정"
    elif c <= 3.5:
        s, h = "neutral", f"소비자물가 +{c}% — 목표 상회, 긴축 압력"
    else:
        s, h = "warn", f"소비자물가 +{c}% — 높은 인플레이션"
    m = [{"k": "CPI(YoY)", "v": f"{c:+.1f}%"}]
    if p is not None:
        m.append({"k": "PPI(YoY·선행)", "v": f"{p:+.1f}%"})
    return _axis("price", "물가 (인플레이션)", s, h,
                 "CPI는 통화정책의 핵심 잣대, PPI는 소비자물가의 선행 신호입니다.", m)


def _external_axis(ind):
    ca = ind.get("current_account"); res = ind.get("reserves")
    last = _num(ca and ca.get("span", {}).get("last"))
    if last is None:
        return _axis("external", "대외 (경상·외환)", "na", "경상수지 자료 대기", "", [])
    surplus = last >= 0
    if surplus and last >= 30:
        s, h = "good", f"경상수지 +{last}억달러 — 견조한 흑자"
    elif surplus:
        s, h = "good", f"경상수지 +{last}억달러 — 흑자 유지"
    else:
        s, h = "warn", f"경상수지 {last}억달러 — 적자(대외 취약)"
    m = [{"k": "경상수지(월)", "v": f"{last:+.0f}억$"}]
    rv = _num(res and res.get("span", {}).get("last"))
    if rv is not None:
        m.append({"k": "외환보유액", "v": f"{rv:,.0f}억$"})
    return _axis("external", "대외 (경상·외환)", s, h,
                 "경상 흑자·충분한 외환보유액은 대외 충격 방어력의 핵심입니다.", m)


def _liquidity_axis(ind):
    m2 = ind.get("m2"); hh = ind.get("household")
    y = _num(m2 and m2.get("yoy"))
    if y is None:
        return _axis("liquidity", "유동성 (통화·신용)", "na", "M2 자료 대기", "", [])
    if y >= 8:
        s, h = "neutral", f"M2 +{y}% — 유동성 빠른 확장(자산가격 압력)"
    elif y >= 4:
        s, h = "good", f"M2 +{y}% — 완만한 유동성 증가"
    elif y >= 0:
        s, h = "neutral", f"M2 +{y}% — 유동성 둔화"
    else:
        s, h = "warn", f"M2 {y}% — 유동성 수축"
    m = [{"k": "M2(YoY)", "v": f"{y:+.1f}%"}]
    hy = _num(hh and hh.get("yoy"))
    if hy is not None:
        m.append({"k": "가계신용(YoY)", "v": f"{hy:+.1f}%"})
    return _axis("liquidity", "유동성 (통화·신용)", s, h,
                 "M2는 시중 유동성, 가계신용은 부채 부담을 나타냅니다.", m)


def _rate_axis(ind):
    br = ind.get("base_rate")
    last = _num(br and br.get("span", {}).get("last"))
    if last is None:
        return _axis("rate", "금리 (통화정책)", "na", "기준금리 자료 대기", "", [])
    d = _dir(br, 12, 0.1)
    cycle = {"상승": "긴축(인상 사이클)", "하락": "완화(인하 사이클)", "동결": "관망(동결 기조)"}.get(d, "")
    s = "neutral" if d == "상승" else "good"
    gov = ind.get("govbond")
    m = [{"k": "기준금리", "v": f"{last:.2f}%"}]
    gv = _num(gov and gov.get("span", {}).get("last"))
    if gv is not None:
        m.append({"k": "국고채(장기)", "v": f"{gv:.2f}%"})
    mr = ind.get("mortgage_rate")
    mv = _num(mr and mr.get("span", {}).get("last"))
    if mv is not None:
        m.append({"k": "주담대 금리", "v": f"{mv:.2f}%"})
    return _axis("rate", "금리 (통화정책)", s, f"기준금리 {last:.2f}% · {cycle or '방향 판단 보류'}",
                 "금리 사이클은 자산시장·대출부담의 방향타입니다.", m)


def _sentiment_axis(ind):
    ccsi = ind.get("ccsi"); esi = ind.get("esi")
    c = _num(ccsi and ccsi.get("span", {}).get("last"))
    if c is None:
        return _axis("sentiment", "심리 (기대)", "na", "심리지수 자료 대기", "", [])
    if c >= 100:
        s, h = "good", f"소비자심리 {c:.0f} — 낙관 우위(기준 100 상회)"
    elif c >= 95:
        s, h = "neutral", f"소비자심리 {c:.0f} — 중립"
    else:
        s, h = "warn", f"소비자심리 {c:.0f} — 비관 우위(기준 100 하회)"
    m = [{"k": "소비자심리(CCSI)", "v": f"{c:.1f}"}]
    ev = _num(esi and esi.get("span", {}).get("last"))
    if ev is not None:
        m.append({"k": "경제심리(ESI)", "v": f"{ev:.1f}"})
    return _axis("sentiment", "심리 (기대)", s, h,
                 "심리지수(100 기준)는 소비·투자의 선행 신호입니다.", m)


def _regime(growth, price):
    """성장×물가 2x2 국면 판정."""
    g = growth["status"]; p_head = price["headline"]
    hot_price = "높은" in p_head or "상회" in p_head
    weak_growth = growth["status"] == "warn" or "둔화" in growth["headline"]
    if not weak_growth and not hot_price:
        return "골디락스 (안정 성장·안정 물가)", "#2f9e44"
    if not weak_growth and hot_price:
        return "확장·물가상승 (경기 양호·인플레 부담)", "#e8890c"
    if weak_growth and hot_price:
        return "스태그플레이션 우려 (저성장·고물가)", "#c0392b"
    return "경기 둔화·완화 국면 (성장 둔화·물가 안정)", "#1c6fd6"


def _build() -> dict:
    macro = ecos.snapshot()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if not macro.get("available"):
        return {"available": False, "reason": macro.get("reason", "ECOS 미연동"),
                "axes": [], "generated_at": ts}
    ind = _by_key(macro["indicators"])

    growth = _growth_axis(ind)
    price = _price_axis(ind)
    external = _external_axis(ind)
    liquidity = _liquidity_axis(ind)
    rate = _rate_axis(ind)
    sentiment = _sentiment_axis(ind)
    axes = [growth, price, external, liquidity, rate, sentiment]

    regime, regime_color = _regime(growth, price)
    scored = [a for a in axes if a["status"] != "na"]
    good = sum(1 for a in scored if a["status"] == "good")
    warn = sum(1 for a in scored if a["status"] == "warn")
    score = round(100 * (good + 0.5 * (len(scored) - good - warn)) / len(scored)) if scored else None

    parts = [f"현재 한국경제는 **{regime}** 국면입니다."]
    parts.append(growth["headline"] + ".")
    parts.append(price["headline"] + ".")
    parts.append(rate["headline"] + ".")
    if external["status"] == "good":
        parts.append("대외건전성은 " + external["headline"] + ".")
    narrative = " ".join(parts)

    return {
        "available": True,
        "generated_at": ts,
        "regime": regime,
        "regime_color": regime_color,
        "score": score,
        "score_label": ("양호" if score and score >= 66 else "중립" if score and score >= 40 else "주의") if score is not None else "—",
        "narrative": narrative,
        "axes": axes,
        "source": "한국은행 ECOS (실측) · 규칙 기반 종합 진단",
        "note": "각 축은 최신 실측 지표로 자동 평가됩니다. 국면 판정은 성장×물가 조합에 근거한 참고용 해석입니다.",
    }


def diagnosis() -> dict:
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]
    out = _build()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = out
    return out
