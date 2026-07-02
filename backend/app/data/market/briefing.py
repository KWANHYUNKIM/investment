"""장전 브리핑 (pre-market briefing).

국장/미장이 열리기 전에, 전일(밤사이) 있었던 일들을 쭉 브리핑하고 오늘 어떻게 될지 분석한다.
- 전일 요약: 해외 증시·반도체·VIX·환율·유가·금·비트코인 마감 + 한국 ADR + 주요 뉴스 헤드라인.
- 오늘 전망: 한국장은 개장예측(premarket) 규칙 점수, 미국장은 지수·변동성·아시아 흐름 기반 참고.
- 선택 AI(Claude): 위 데이터를 근거로 아침 브리핑 서술(요약/전망/리스크). 키 없으면 규칙 기반 서술.
캐시 5분.
"""
from __future__ import annotations

import datetime as _dt
import threading
import time

from app.core.config import get_settings
from app.data.macro import crossasset
from app.data.market import premarket
from app.data.news import news

_lock = threading.Lock()
_cache: dict = {}
TTL = 300.0

_TOPICS = {
    "kr": ["미국 증시 마감", "코스피 전망", "반도체 주가", "원달러 환율", "연준 금리"],
    "us": ["미국 증시", "연준 금리", "엔비디아 실적", "아시아 증시", "국제유가"],
}
_SYSTEM = ("너는 증권사 아침 브리핑 담당 애널리스트다. 주어진 전일 시장 데이터와 뉴스 헤드라인만 근거로, "
           "투자자가 개장 전에 읽을 브리핑을 한국어로 쓴다. 과장·단정·투자권유를 피하고 불확실성은 '전망/추정'으로 표시한다. "
           "반드시 JSON만 출력한다.")


def _target_market(m: str) -> str:
    if m in ("kr", "us"):
        return m
    now = _dt.datetime.utcnow() + _dt.timedelta(hours=9)  # KST
    minutes = now.hour * 60 + now.minute
    # 새벽~오후 → 한국장 아침 브리핑, 오후 3시반 이후 → 미국장 브리핑
    return "kr" if minutes < 15 * 60 + 30 else "us"


def _news_stories(market: str, per: int = 4, total: int = 14) -> list[dict]:
    seen = set()
    out = []
    for topic in _TOPICS.get(market, _TOPICS["kr"]):
        try:
            arts = (news.news_for(topic, limit=per).get("domestic") or [])[:per]
        except Exception:
            arts = []
        for a in arts:
            title = (a.get("title") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            out.append({"topic": topic, "title": title, "source": a.get("source"),
                        "link": a.get("link"), "ts": a.get("ts")})
    out.sort(key=lambda x: x.get("ts") or 0, reverse=True)
    return out[:total]


def _pick_assets(cross: dict) -> dict:
    """crossasset 그룹에서 금·비트코인 등 보조 자산을 뽑는다."""
    extras = {}
    for g in cross.get("groups", []):
        for a in g.get("assets", []):
            nm = (a.get("name") or "") + (a.get("key") or "")
            if any(k in nm for k in ("금", "Gold", "gold", "XAU")) and "gold" not in extras:
                extras["gold"] = a
            if any(k in nm for k in ("비트", "Bitcoin", "BTC", "btc")) and "btc" not in extras:
                extras["btc"] = a
    return extras


def _outlook(market: str, fc: dict, signals_by: dict) -> dict:
    if market == "kr":
        gap = fc.get("expected_gap") or {}
        return {
            "market": "한국(코스피·코스닥)",
            "bias": fc.get("bias"),
            "gauge": fc.get("gauge"),
            "expected_gap": gap,
            "drivers": fc.get("drivers", []),
            "basis": "개장예측 규칙점수(해외 마감·반도체·환율·VIX·한국 ADR 가중)",
        }
    # 미국장: 전일 마감 + 변동성 기반 간단 판단
    sox = signals_by.get("sox", {}).get("change_pct")
    vix = signals_by.get("vix", {}).get("change_pct")
    ndq = signals_by.get("nasdaq", {}).get("change_pct")
    score = 0.0
    if ndq is not None:
        score += ndq
    if sox is not None:
        score += sox * 0.5
    if vix is not None:
        score -= vix * 0.2
    bias = "강세 우위" if score > 0.6 else ("약세 우위" if score < -0.6 else "중립")
    return {
        "market": "미국(S&P·나스닥)",
        "bias": bias,
        "gauge": None,
        "expected_gap": {},
        "drivers": [d for d in [
            f"전일 나스닥 {ndq:+.1f}%" if ndq is not None else None,
            f"반도체(SOX) {sox:+.1f}%" if sox is not None else None,
            f"VIX {vix:+.1f}%" if vix is not None else None,
        ] if d],
        "basis": "전일 미국 마감·반도체·변동성 추세 기반 참고(선물·아시아 실시간은 제한적).",
    }


def _rule_narrative(market: str, signals_by: dict, adrs: list, stories: list, outlook: dict) -> dict:
    def mv(k):
        v = signals_by.get(k, {}).get("change_pct")
        return f"{v:+.1f}%" if v is not None else "—"
    recap = [
        f"미국 증시: S&P {mv('sp500')} · 나스닥 {mv('nasdaq')} · 반도체(SOX) {mv('sox')}.",
        f"변동성·환율·유가: VIX {mv('vix')} · 원달러 {mv('usdkrw')} · WTI {mv('wti')}.",
    ]
    if adrs:
        top = adrs[0]
        recap.append(f"한국 ADR: 평균 흐름 참고 (예: {top.get('name')} {top.get('change_pct'):+.1f}%).")
    if stories:
        recap.append(f"주요 뉴스: {stories[0]['title']}")
    lead = outlook.get("bias") or "중립"
    return {
        "headline": f"{outlook['market']} 개장 전 브리핑 — 전일 흐름 요약",
        "recap": recap,
        "outlook": f"오늘 {outlook['market']}은 '{lead}'로 출발할 가능성. {outlook.get('basis','')}",
        "risks": ["뉴스는 상관관계일 뿐 인과를 보장하지 않습니다.", "지표는 전일 마감 기준이라 장중 변동될 수 있습니다."],
        "one_liner": f"전일 흐름상 {outlook['market']} {lead} 예상(참고).",
        "source": "rule",
    }


def _ai_narrative(market: str, signals_by: dict, adrs: list, stories: list, outlook: dict) -> dict | None:
    key = (get_settings().anthropic_api_key or "").strip()
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    def mv(k):
        v = signals_by.get(k, {}).get("change_pct")
        return f"{v:+.2f}%" if v is not None else "N/A"
    heads = "\n".join(f"- [{s['topic']}] {s['title']} ({s.get('source') or ''})" for s in stories[:12])
    adr_txt = ", ".join(f"{a.get('name')} {a.get('change_pct'):+.1f}%" for a in adrs[:6]) or "N/A"
    prompt = (
        f"[대상 시장] {outlook['market']} 개장 전 브리핑\n"
        f"[전일 지표] S&P {mv('sp500')}, 나스닥 {mv('nasdaq')}, 반도체SOX {mv('sox')}, "
        f"VIX {mv('vix')}, 원달러 {mv('usdkrw')}, WTI {mv('wti')}\n"
        f"[한국 ADR] {adr_txt}\n"
        f"[규칙 전망] {outlook.get('bias')} / 드라이버: {', '.join(outlook.get('drivers', []))}\n"
        f"[전일 주요 뉴스]\n{heads}\n\n"
        "위를 근거로 개장 전 브리핑을 작성해줘. 반드시 이 JSON만: "
        '{"headline":"한 줄 제목","recap":["전일 있었던 핵심 이야기 4~6개(불릿)"],'
        '"outlook":"오늘 어떻게 될지 2~3문장 전망","risks":["주의/리스크 2~3개"],"one_liner":"한 줄 요약"}'
    )
    client = anthropic.Anthropic(api_key=key)
    for model in ("claude-fable-5", "claude-opus-4-8"):
        try:
            msg = client.messages.create(model=model, max_tokens=1200, system=_SYSTEM,
                                         messages=[{"role": "user", "content": prompt}])
            if getattr(msg, "stop_reason", None) == "refusal":
                continue
            text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text").strip()
            data = _extract_json(text)
            if data:
                data["source"] = model
                return data
        except Exception:
            continue
    return None


def _extract_json(text: str) -> dict | None:
    import json
    if not text:
        return None
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e <= s:
        return None
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


def briefing(market: str = "auto") -> dict:
    target = _target_market(market)
    ckey = f"brief:{target}"
    with _lock:
        hit = _cache.get(ckey)
        if hit and (time.time() - hit[0] < TTL):
            return hit[1]

    fc = premarket.forecast()
    signals = fc.get("signals", [])
    signals_by = {s.get("key"): s for s in signals}
    adrs = fc.get("adrs", [])
    try:
        cross = crossasset.cross_asset()
    except Exception:
        cross = {"groups": [], "flow": {}}
    extras = _pick_assets(cross)
    stories = _news_stories(target)
    outlook = _outlook(target, fc, signals_by)

    ai = _ai_narrative(target, signals_by, adrs, stories, outlook)
    narrative = ai or _rule_narrative(target, signals_by, adrs, stories, outlook)

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "market": target,
        "market_label": outlook["market"],
        "signals": signals,
        "adrs": adrs[:8],
        "extras": extras,
        "flow": cross.get("flow"),
        "stories": stories,
        "outlook": outlook,
        "narrative": narrative,
        "ai_enabled": bool((get_settings().anthropic_api_key or "").strip()),
        "note": "전일 지표·뉴스 기반 브리핑입니다. 뉴스는 상관관계일 뿐 인과를 보장하지 않으며, 지표는 전일 마감 기준이라 "
                "장중 실시간과 다를 수 있습니다. 투자 판단·손실 책임은 본인에게 있습니다.",
    }
    with _lock:
        _cache[ckey] = (time.time(), out)
    return out
