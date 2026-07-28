"""개장 예측 (KR market open forecast).

"어제 미국·유럽이 어떻게 끝났고, 우리와 직결된 지표(반도체·환율·VIX·한국 ADR)가
간밤에 어떻게 움직였는지"를 모아, 오늘 한국장이 열렸을 때 어느 방향으로 출발할지
(강세/중립/약세) 규칙 기반으로 점수화한다. Anthropic 키가 있으면 그 스냅샷을
Claude(Fable 5)에게 넘겨 서술형 시나리오(주목 섹터·리스크)를 덧붙인다.

- 시세: FinanceDataReader(자산·환율 단일 소스), 캐시 5분.
- 방향(direction): +1 = 그 지표가 오르면 우리 장에 우호적, -1 = 우리 장에 부담.
- Claude 층은 완전 선택 — 키가 없거나 호출이 실패해도 규칙 기반 예측은 항상 나온다.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import FinanceDataReader as fdr

from app.core.config import get_settings

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 300.0  # 5분 — 개장 전 지표는 자주 바뀌지 않는다.

# (key, 라벨, fdr 심볼, 그룹, 단위, 가중치, 방향)
#   방향 +1: 오르면 한국장에 우호 / -1: 오르면 부담
_SIGNALS: tuple[tuple[str, str, str, str, str, float, int], ...] = (
    # 간밤 미국 증시 마감 — 우리 장의 기준선
    ("sp500", "S&P 500", "US500", "미국 증시", "pt", 1.0, +1),
    ("nasdaq", "나스닥", "IXIC", "미국 증시", "pt", 1.2, +1),
    ("dow", "다우존스", "DJI", "미국 증시", "pt", 0.6, +1),
    # 우리 증시에 가장 직결되는 지표들
    ("sox", "필라델피아 반도체(SOXX)", "SOXX", "핵심 연동", "pt", 1.6, +1),  # 삼성·하이닉스 직결
    ("vix", "VIX 공포지수", "VIX", "핵심 연동", "pt", 1.2, -1),
    ("ust10y", "미 국채 10년 금리", "US10YT", "핵심 연동", "pct", 0.5, -1),
    ("usdkrw", "원/달러 환율", "USD/KRW", "핵심 연동", "krw", 1.0, -1),  # 원화 약세 = 외국인 부담
    # 원자재·아시아 (참고)
    ("wti", "WTI 유가", "CL=F", "원자재·아시아", "usd", 0.3, -1),
    ("nikkei", "닛케이225", "N225", "원자재·아시아", "pt", 0.5, +1),
    ("hangseng", "항셍", "HSI", "원자재·아시아", "pt", 0.4, +1),
)

# 미국에 상장된 한국 기업 ADR — 간밤에 실제로 거래된 '한국 주식'이라
# 오늘 개장 방향의 가장 직접적인 힌트가 된다.
_ADRS: tuple[tuple[str, str], ...] = (
    ("CPNG", "쿠팡"),
    ("PKX", "포스코홀딩스"),
    ("KB", "KB금융"),
    ("SHG", "신한지주"),
    ("WF", "우리금융"),
    ("SKM", "SK텔레콤"),
    ("KEP", "한국전력"),
    ("LPL", "LG디스플레이"),
    ("GRVY", "그라비티"),
)
_ADR_WEIGHT = 1.6  # ADR 평균은 개장 방향의 가장 직접적 신호 → 큰 가중치


def _quote(symbol: str) -> dict | None:
    """단일 심볼의 최근 종가·전일 대비 등락(%)."""
    try:
        df = fdr.DataReader(symbol)
        if df is None or df.empty or "Close" not in df.columns:
            return None
        df = df.dropna(subset=["Close"])
        if len(df) < 2:
            return None
        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2])
        if not prev:
            return None
        return {
            "value": round(last, 2),
            "change_pct": round((last - prev) / prev * 100.0, 2),
            "date": str(df.index[-1])[:10],
        }
    except Exception:
        return None


def _gather() -> tuple[list[dict], list[dict]]:
    """지표 신호 + 한국 ADR을 동시에 취합한다."""
    signals: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(_quote, spec[2]): spec for spec in _SIGNALS}
        adr_futs = {ex.submit(_quote, t): (t, name) for t, name in _ADRS}

        for fut, spec in futs.items():
            q = fut.result()
            if not q:
                continue
            key, label, _sym, group, unit, weight, direction = spec
            signals.append({
                "key": key, "label": label, "group": group, "unit": unit,
                "weight": weight, "direction": direction,
                "value": q["value"], "change_pct": q["change_pct"], "date": q["date"],
                # 우리 장 방향으로 환산한 기여도(부호 정렬)
                "impact_pct": round(q["change_pct"] * direction, 2),
            })

        adrs: list[dict] = []
        for fut, (ticker, name) in adr_futs.items():
            q = fut.result()
            if not q:
                continue
            adrs.append({
                "ticker": ticker, "name": name,
                "value": q["value"], "change_pct": q["change_pct"], "date": q["date"],
            })

    signals.sort(key=lambda s: -abs(s["impact_pct"]))
    adrs.sort(key=lambda a: -abs(a["change_pct"]))
    return signals, adrs


_INDICES: tuple[tuple[str, str, str], ...] = (
    ("kospi", "코스피", "KS11"),
    ("kosdaq", "코스닥", "KQ11"),
)


def _one_index(spec: tuple[str, str, str]) -> dict | None:
    """지수 하나의 추세 요약 + 최근 종가 시계열(스파크라인용)."""
    key, label, sym = spec
    try:
        df = fdr.DataReader(sym)
        if df is None or df.empty or "Close" not in df.columns:
            return None
        df = df.dropna(subset=["Close"]).tail(60)
        closes = [float(c) for c in df["Close"].tolist()]
        if len(closes) < 5:
            return None
        last = closes[-1]
        prev = closes[-2]

        def chg(n: int) -> float | None:
            if len(closes) <= n:
                return None
            base = closes[-1 - n]
            return round((last - base) / base * 100.0, 2) if base else None

        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / len(closes[-20:])
        # 추세: 20일선 위/아래 + 5일선 기울기
        slope5 = closes[-1] - closes[-5]
        if last > ma20 and slope5 > 0:
            trend = "상승추세"
        elif last < ma20 and slope5 < 0:
            trend = "하락추세"
        else:
            trend = "횡보"

        dates = [str(d)[:10] for d in df.index.tolist()]
        return {
            "key": key, "label": label,
            "close": round(last, 2),
            "change_pct": round((last - prev) / prev * 100.0, 2) if prev else None,
            "change_5d": chg(5), "change_20d": chg(20),
            "ma20": round(ma20, 2),
            "vs_ma20_pct": round((last - ma20) / ma20 * 100.0, 2) if ma20 else None,
            "trend": trend,
            "series": [{"date": d, "close": round(c, 2)} for d, c in zip(dates[-30:], closes[-30:])],
        }
    except Exception:
        return None


def _index_trend() -> list[dict]:
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        for res in ex.map(_one_index, _INDICES):
            if res:
                out.append(res)
    return out


def _score(signals: list[dict], adrs: list[dict]) -> dict:
    """가중 평균으로 개장 방향 스코어·예상 갭·근거를 만든다."""
    contribs = [(s["label"], s["impact_pct"], s["weight"]) for s in signals]
    total_w = sum(w for _, _, w in contribs)
    weighted_sum = sum(imp * w for _, imp, w in contribs)

    adr_avg = None
    if adrs:
        adr_avg = round(sum(a["change_pct"] for a in adrs) / len(adrs), 2)
        weighted_sum += adr_avg * _ADR_WEIGHT
        total_w += _ADR_WEIGHT

    # weighted = 우리 장 방향으로 정렬한 '가중 평균 등락(%)'
    weighted = round(weighted_sum / total_w, 3) if total_w else 0.0

    if weighted >= 0.35:
        bias, tone = "강세", "긍정"
    elif weighted <= -0.35:
        bias, tone = "약세", "부정"
    else:
        bias, tone = "중립", "중립"

    # 예상 개장 갭 범위(코스피 기준, 대략치). 간밤 신호를 0.7배 반영 + 불확실 밴드.
    center = weighted * 0.7
    gap = {"low": round(center - 0.2, 2), "high": round(center + 0.2, 2)}

    # 게이지용 스코어 -100..100
    gauge = max(-100.0, min(100.0, round(weighted / 1.5 * 100.0, 1)))

    # 근거: 우리 장에 영향이 큰 순서 상위 4개
    drivers: list[str] = []
    if adr_avg is not None:
        d = "우호적" if adr_avg > 0 else "부담" if adr_avg < 0 else "중립"
        drivers.append(f"한국 ADR 평균 {adr_avg:+.2f}% — 간밤 거래된 한국물이 {d}")
    for label, imp, _w in contribs[:3]:
        d = "우호적" if imp > 0 else "부담" if imp < 0 else "중립"
        drivers.append(f"{label} {imp:+.2f}%(우리 장 방향 환산) — {d}")

    return {
        "bias": bias, "tone": tone,
        "weighted_pct": weighted, "gauge": gauge,
        "expected_gap": gap, "adr_avg": adr_avg,
        "drivers": drivers,
    }


# --- Claude(Fable 5) 서술형 예측 층 (선택) --------------------------------------

_SYSTEM = (
    "너는 한국 주식시장 개장 전략가다. 간밤 글로벌 증시 마감과 한국과 직결된 지표"
    "(필라델피아 반도체·원/달러·VIX·미국 상장 한국 ADR)의 움직임을 근거로, 오늘 한국"
    "증시(코스피·코스닥)가 개장했을 때의 방향을 냉정하게 판단한다. 확정적 예언이 아니라"
    "확률적 시나리오로 말하고, 반드시 주어진 데이터에 근거해 설명한다. 한국어로 답한다."
)


def _ai_layer(signals: list[dict], adrs: list[dict], base: dict, indices: list[dict] | None = None) -> dict | None:
    """Anthropic 키가 있으면 Claude로 서술형 시나리오를 만든다. 실패 시 None."""
    key = (get_settings().anthropic_api_key or "").strip()
    if not key:
        return None

    try:
        import anthropic
    except Exception:
        return {"error": "anthropic 패키지가 설치되어 있지 않습니다. (pip install anthropic)"}

    sig_lines = "\n".join(
        f"- {s['label']}: {s['change_pct']:+.2f}% (우리 장 방향 환산 {s['impact_pct']:+.2f}%)"
        for s in signals
    )
    adr_lines = "\n".join(f"- {a['name']}({a['ticker']}): {a['change_pct']:+.2f}%" for a in adrs)
    idx_lines = "\n".join(
        f"- {i['label']}: {i['close']} ({i['trend']}, 1일 {i['change_pct']:+.2f}%, "
        f"5일 {i.get('change_5d')}%, 20일 {i.get('change_20d')}%, 20일선대비 {i.get('vs_ma20_pct')}%)"
        for i in (indices or [])
    )
    prompt = (
        "다음은 오늘 한국장 개장 직전의 간밤 지표 스냅샷이다.\n\n"
        f"[코스피·코스닥 최근 추세]\n{idx_lines or '(수집 실패)'}\n\n"
        f"[간밤 글로벌·연동 지표]\n{sig_lines}\n\n"
        f"[미국 상장 한국 ADR — 간밤 거래된 한국물]\n{adr_lines or '(수집 실패)'}\n\n"
        f"[규칙 기반 1차 판단]\n"
        f"- 가중 평균(우리 장 방향) {base['weighted_pct']:+.3f}% → {base['bias']}\n"
        f"- 예상 개장 갭 대략 {base['expected_gap']['low']:+.2f}% ~ {base['expected_gap']['high']:+.2f}%\n\n"
        "이 데이터만 근거로, 오늘 코스피/코스닥 개장 시나리오를 판단하라. "
        "설명이나 서론 없이 아래 JSON 객체 하나만 출력한다:\n"
        '{\n'
        '  "bias": "강세|중립|약세",\n'
        '  "one_liner": "한 줄 요약(개장 방향)",\n'
        '  "narrative": "3~5문장 근거 서술",\n'
        '  "sectors": [{"name": "섹터/테마", "view": "왜 강할/약할지 한 줄"}],\n'
        '  "risks": ["개장 후 뒤집을 수 있는 리스크 1~3개"],\n'
        '  "confidence": "높음|보통|낮음"\n'
        "}"
    )

    client = anthropic.Anthropic(api_key=key)
    last_err = "알 수 없음"
    for model in ("claude-fable-5", "claude-opus-4-8"):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=1500,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            if getattr(msg, "stop_reason", None) == "refusal":
                last_err = f"{model} 응답 거부(refusal)"
                continue
            text = "".join(
                getattr(b, "text", "") for b in msg.content
                if getattr(b, "type", None) == "text"
            ).strip()
            data = _extract_json(text)
            if data:
                data["model"] = model
                return data
            last_err = f"{model} 응답에서 JSON을 찾지 못함"
        except Exception as e:  # noqa: BLE001 — AI 층은 완전 선택, 어떤 실패든 흡수
            last_err = str(e)
            continue
    return {"error": f"Claude 호출 실패: {last_err}"}


def _extract_json(text: str) -> dict | None:
    """모델 응답에서 첫 JSON 객체를 관대하게 파싱한다."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def forecast() -> dict:
    """오늘 한국장 개장 예측 스냅샷 (규칙 기반 + 선택적 Claude 서술). 캐시 5분."""
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    signals, adrs = _gather()
    indices = _index_trend()
    base = _score(signals, adrs)
    ai = _ai_layer(signals, adrs, base, indices)

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "signals": signals,
        "adrs": adrs,
        "indices": indices,
        **base,
        "ai": ai if (ai and "error" not in ai) else None,
        "ai_error": ai["error"] if (ai and "error" in ai) else None,
        "ai_enabled": bool((get_settings().anthropic_api_key or "").strip()),
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = out
    return out
