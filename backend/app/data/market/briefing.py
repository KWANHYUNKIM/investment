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


def _rule_narrative(market: str, signals_by: dict, adrs: list, stories: list, outlook: dict, extras: dict) -> dict:
    def g(k):
        return signals_by.get(k, {}).get("change_pct")

    def f(v):
        return f"{v:+.1f}%" if v is not None else "—"

    sp, ndq, sox, vix, fx, wti = g("sp500"), g("nasdaq"), g("sox"), g("vix"), g("usdkrw"), g("wti")
    gold = (extras.get("gold") or {}).get("change_pct")
    btc = (extras.get("btc") or {}).get("change_pct")
    adr_vals = [a["change_pct"] for a in adrs if a.get("change_pct") is not None]
    adr_avg = sum(adr_vals) / len(adr_vals) if adr_vals else None

    # 위험선호 톤 판정
    if (ndq is not None and ndq > 0.3) and (vix is None or vix < 0):
        tone = "위험 선호(리스크온)"
    elif (ndq is not None and ndq < -0.3) or (vix is not None and vix > 3):
        tone = "위험 회피(리스크오프)"
    else:
        tone = "혼조"

    # --- 전일 요약 ---
    recap = [f"미국 증시는 S&P {f(sp)}, 나스닥 {f(ndq)}로 마감({tone})."]
    if sox is not None:
        semis = "급락" if sox <= -3 else ("약세" if sox < 0 else ("강세" if sox > 1 else "보합권"))
        recap.append(f"필라델피아 반도체지수(SOX) {f(sox)}로 {semis} — 삼성전자·SK하이닉스 등 국내 반도체 대형주에 직접 영향.")
    if vix is not None:
        vtxt = "변동성 확대(경계)" if vix > 3 else ("변동성 진정" if vix < -3 else "변동성 보통")
        recap.append(f"VIX(공포지수) {f(vix)} — {vtxt}.")
    macro = []
    if fx is not None:
        fxt = "원화 약세→외국인 수급 부담" if fx > 0.2 else ("원화 강세→수급 우호" if fx < -0.2 else "환율 안정")
        macro.append(f"원/달러 {f(fx)}({fxt})")
    if wti is not None:
        macro.append(f"WTI {f(wti)}")
    if gold is not None:
        macro.append(f"금 {f(gold)}")
    if btc is not None:
        macro.append(f"비트코인 {f(btc)}")
    if macro:
        recap.append(" · ".join(macro) + ".")
    if adr_avg is not None:
        recap.append(f"한국 ADR 평균 {f(adr_avg)} — 간밤 뉴욕서 거래된 한국물 흐름은 개장 방향의 가장 직접적 신호.")
    if stories:
        recap.append("전일 주요 이슈: " + "; ".join(s["title"] for s in stories[:3]) + ".")

    # --- 오늘 전망(근거 제시) ---
    bias = outlook.get("bias") or "중립"
    reasons = []
    if market == "kr":
        if sox is not None and sox < -2:
            reasons.append("반도체 급락")
        elif sox is not None and sox > 1:
            reasons.append("반도체 강세")
        if adr_avg is not None and adr_avg < -1:
            reasons.append("한국 ADR 약세")
        elif adr_avg is not None and adr_avg > 1:
            reasons.append("한국 ADR 강세")
        if fx is not None and fx > 0.3:
            reasons.append("환율 상승(원화 약세)")
        if vix is not None and vix > 3:
            reasons.append("변동성 확대")
        if ndq is not None and ndq > 0.5:
            reasons.append("미 기술주 강세")
        if not reasons:
            reasons.append("뚜렷한 방향성 재료 부족")
        gap = outlook.get("expected_gap") or {}
        gap_txt = f"예상 시가 갭 {gap.get('low')}%~{gap.get('high')}%. " if gap.get("low") is not None else ""
        outlook_txt = (f"오늘 한국장은 '{bias}' 출발이 예상됩니다. 근거: {', '.join(reasons)}. {gap_txt}"
                       "개장 직후 반도체 대형주 움직임·외국인 수급·원달러 방향을 먼저 확인하세요.")
    else:
        outlook_txt = (f"오늘 미국장은 전일 마감·변동성 흐름상 '{bias}'가 우세합니다. "
                       "장중에는 기술주(나스닥)·반도체와 발표 경제지표·연준 인사 발언에 민감할 수 있습니다. "
                       "(선물·아시아 실시간은 제한적이라 참고용입니다.)")

    risks = ["뉴스·지표는 상관관계일 뿐 인과·미래를 보장하지 않습니다.",
             "지표는 전일 마감 기준으로 장중 실시간과 다를 수 있습니다."]
    if market == "kr" and fx is not None and fx > 0.3:
        risks.append("원화 약세가 이어지면 외국인 매도 압력 확대 주의.")
    if sox is not None and sox < -3:
        risks.append("반도체 투매가 지속되면 지수 하방 압력 확대.")

    key_reasons = ", ".join(reasons[:2]) if market == "kr" else "기술주·지표 주목"
    return {
        "headline": f"{outlook['market']} 장전 브리핑 — {tone}, 오늘 {bias} 예상",
        "recap": recap,
        "outlook": outlook_txt,
        "risks": risks,
        "one_liner": f"전일 {tone}. 오늘 {outlook['market']} {bias} 예상 — {key_reasons}.",
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
    narrative = ai or _rule_narrative(target, signals_by, adrs, stories, outlook, extras)

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
