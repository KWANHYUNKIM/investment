"""급등락 원인 규명 (auto cause-finding).

시장에서 오늘 크게 오르거나 내린 종목·업종을 자동 감지하고, 그 원인을 관련 뉴스(+선택적
Claude 요약)로 규명한다. 스케줄러가 주기적으로 스냅샷을 기록해 '원인 이력'이 쌓인다.

- 급등/급락 종목: 유동성(거래대금) 필터 후 등락률 상위/하위.
- 업종 히트맵: 실제 업종(WICS)별 평균 등락률·상승/하락 종목수.
- 원인: 상위 급등·급락 종목에 대해 뉴스 헤드라인 취합. Claude 키가 있으면 '종합 원인' 1~2문장.
캐시 5분.
"""
from __future__ import annotations

import threading
import time

from app.core.config import get_settings
from app.data.infra import store
from app.data.news import news

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 300.0
_SYSTEM = ("너는 한국 주식시장 애널리스트다. 주어진 급등락 종목·업종과 관련 뉴스 헤드라인만 근거로, "
           "오늘 그 종목/업종이 왜 오르거나 내렸는지 원인을 간결한 한국어로 설명한다. 추측은 '추정'으로 표시하고 "
           "과장·투자권유는 하지 않는다. 반드시 JSON만 출력한다.")


def _num(v):
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _liquid_rows(min_value: float = 1_000_000_000):
    """거래대금(종가×거래량) min_value 이상인 KR 종목 records + 실제 업종."""
    q = store.latest_quotes(market="KR")
    if q is None or q.empty:
        return []
    secmap = store.sector_map()
    rows = []
    for r in q.to_dict("records"):
        close = _num(r.get("close"))
        vol = _num(r.get("volume"))
        prev = _num(r.get("prev_close"))
        if close is None or vol is None or not prev:
            continue
        chg = (close / prev - 1.0) * 100.0
        value = close * vol
        if value < min_value:
            continue
        c1m = _num(r.get("close_1m"))
        rows.append({
            "ticker": r["ticker"], "name": r.get("name"),
            "sector": secmap.get(r["ticker"]) or r.get("sector"),
            "close": close, "change_pct": chg, "value": value,
            "change_1m_pct": ((close / c1m - 1.0) * 100.0) if c1m else None,
        })
    return rows


def _sector_table(rows: list[dict]) -> list[dict]:
    _SKIP = {"KOSPI", "KOSDAQ", "KONEX", "기타", None, ""}
    by: dict[str, list[dict]] = {}
    for r in rows:
        sec = r["sector"]
        if sec in _SKIP:                    # 시장명(WICS 미매핑)은 업종 집계서 제외
            continue
        by.setdefault(sec, []).append(r)
    out = []
    for sector, items in by.items():
        if len(items) < 3:
            continue
        chgs = [i["change_pct"] for i in items]
        avg = sum(chgs) / len(chgs)
        adv = sum(1 for c in chgs if c > 0)
        dec = sum(1 for c in chgs if c < 0)
        leaders = sorted(items, key=lambda i: i["value"], reverse=True)[:3]
        out.append({
            "sector": sector, "avg_change_pct": round(avg, 2), "count": len(items),
            "advancers": adv, "decliners": dec,
            "leaders": [{"name": l["name"], "ticker": l["ticker"], "change_pct": round(l["change_pct"], 2)} for l in leaders],
        })
    out.sort(key=lambda x: x["avg_change_pct"])
    return out


def _news_brief(name: str, limit: int = 5) -> list[dict]:
    try:
        d = news.news_for(name, limit=limit)
    except Exception:
        return []
    arts = (d.get("domestic") or [])[:limit]
    return [{"title": a.get("title"), "source": a.get("source"), "link": a.get("link"), "ts": a.get("ts")} for a in arts]


def _ai_cause(gainers: list[dict], losers: list[dict], sectors_up: list[dict], sectors_down: list[dict]) -> dict | None:
    key = (get_settings().anthropic_api_key or "").strip()
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    def _fmt(items):
        lines = []
        for it in items:
            heads = "; ".join(h["title"] for h in it.get("news", [])[:4] if h.get("title"))
            lines.append(f"- {it['name']} ({it['change_pct']:+.1f}%): {heads or '관련 뉴스 없음'}")
        return "\n".join(lines) or "(없음)"

    prompt = (
        "오늘 한국 시장 급등락과 관련 뉴스다. 각 그룹의 '원인'을 뉴스 근거로 1~2문장씩, 그리고 시장 전체 흐름을 "
        "1~2문장으로 요약해줘.\n\n"
        f"[급락 종목]\n{_fmt(losers)}\n\n[급등 종목]\n{_fmt(gainers)}\n\n"
        f"[하락 업종] {', '.join(f'{s['sector']}({s['avg_change_pct']:+.1f}%)' for s in sectors_down[:5])}\n"
        f"[상승 업종] {', '.join(f'{s['sector']}({s['avg_change_pct']:+.1f}%)' for s in sectors_up[:5])}\n\n"
        '반드시 이 JSON 형식으로만: {"overall":"...","losers_cause":"...","gainers_cause":"...","drivers":["...","..."]}'
    )
    client = anthropic.Anthropic(api_key=key)
    for model in ("claude-fable-5", "claude-opus-4-8"):
        try:
            msg = client.messages.create(model=model, max_tokens=900, system=_SYSTEM,
                                         messages=[{"role": "user", "content": prompt}])
            if getattr(msg, "stop_reason", None) == "refusal":
                continue
            text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text").strip()
            data = _extract_json(text)
            if data:
                data["model"] = model
                return data
        except Exception:
            continue
    return None


def _extract_json(text: str) -> dict | None:
    import json
    if not text:
        return None
    s = text.find("{")
    e = text.rfind("}")
    if s < 0 or e <= s:
        return None
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


def _build() -> dict:
    s = get_settings()
    rows = _liquid_rows()
    if not rows:
        return {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "count": 0,
                "gainers": [], "losers": [], "sectors_up": [], "sectors_down": [],
                "ai": None, "ai_enabled": bool((s.anthropic_api_key or "").strip()),
                "note": "가격 데이터가 아직 없습니다. 가격 스케줄러가 첫 스냅샷을 적재하면 표시됩니다."}

    thr = s.movers_threshold
    n = s.movers_top_n
    ranked = sorted(rows, key=lambda r: r["change_pct"], reverse=True)
    gainers = [r for r in ranked if r["change_pct"] >= thr][:n]
    losers = [r for r in reversed(ranked) if r["change_pct"] <= -thr][:n]
    # 급등락 종목이 임계 미만이면 그냥 상·하위로 채운다
    if not gainers:
        gainers = ranked[:min(3, len(ranked))]
    if not losers:
        losers = list(reversed(ranked))[:min(3, len(ranked))]

    # 원인 뉴스 취합 (상위 급등·급락 종목)
    for it in gainers + losers:
        it["news"] = _news_brief(it["name"]) if it["name"] else []

    sectors = _sector_table(rows)
    sectors_down = sectors[:5]
    sectors_up = list(reversed(sectors))[:5]

    breadth_adv = sum(1 for r in rows if r["change_pct"] > 0)
    breadth_dec = sum(1 for r in rows if r["change_pct"] < 0)

    ai = _ai_cause(gainers, losers, sectors_up, sectors_down)

    def _slim(it):
        return {"ticker": it["ticker"], "name": it["name"], "sector": it["sector"],
                "close": round(it["close"]), "change_pct": round(it["change_pct"], 2),
                "value": round(it["value"]), "news": it.get("news", [])}

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(rows),
        "breadth": {"advancers": breadth_adv, "decliners": breadth_dec},
        "threshold": thr,
        "gainers": [_slim(x) for x in gainers],
        "losers": [_slim(x) for x in losers],
        "sectors_up": sectors_up,
        "sectors_down": sectors_down,
        "ai": ai,
        "ai_enabled": bool((s.anthropic_api_key or "").strip()),
        "note": "급등락=거래대금 10억↑ 종목 중 등락률 상·하위. 원인은 관련 뉴스 헤드라인 기반이며 상관관계일 뿐 "
                "인과를 보장하지 않습니다. AI 요약은 선택(키 설정 시).",
    }


def snapshot(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]
    out = _build()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = out
    return out
