"""종목별 목표주가 (target price / 적정주가).

이미 수집된 재무 스냅샷(EPS·BPS·ROE·PER·PBR)과 현재가로 밸류에이션 기반 적정주가를
계산하고, 강세/기준/약세 세 시나리오의 목표주가·상승여력을 산출한다. Anthropic 키가
있으면 Claude(Fable 5)로 시나리오별 목표가 경로와 근거를 덧붙인다(선택).

밸류에이션 두 축(가능한 것만 사용해 평균):
  - 정당PBR(ROE 기반): 적정 = BPS × (ROE / 요구수익률). 잔여이익 모형의 단축형.
  - EPS × 목표PER: 목표PER = 해당 종목 과거 PER 중앙값(없으면 시장 기본 10배).
시나리오는 요구수익률(r)과 목표PER 배수를 함께 흔들어 만든다.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.data.infra import store

_R_BASE = 0.08          # 기준 요구수익률 8%
_DEFAULT_PER = 10.0     # 과거 PER을 못 구할 때 시장 기본 목표PER
_SCENARIOS = (
    # 이름, 요구수익률 r, 목표PER 배수
    ("강세", 0.07, 1.15),
    ("기준", 0.08, 1.00),
    ("약세", 0.10, 0.85),
)


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _latest_fundamentals(ticker: str):
    hist = store.fundamentals_history(ticker)
    if hist is None or hist.empty:
        return None, None
    recs = hist.to_dict("records")
    latest = recs[-1]
    fund = {k: _num(latest.get(k)) for k in ("per", "pbr", "eps", "bps", "roe")}
    # 과거 PER 중앙값(양수만) — 목표PER 앵커
    pers = sorted(v for r in recs if (v := _num(r.get("per"))) is not None and v > 0)
    per_median = pers[len(pers) // 2] if pers else None
    return fund, per_median


def _close(ticker: str) -> float | None:
    df = store.load_prices(tickers=[ticker])
    if df is None or df.empty or ticker not in df.columns:
        return None
    s = df[ticker].dropna()
    return float(s.iloc[-1]) if len(s) else None


def _methods(fund: dict, per_median: float | None, r: float, per_mult: float) -> dict:
    """이 시나리오에서 사용 가능한 밸류에이션 방법별 적정주가."""
    out: dict[str, float] = {}
    eps, bps, roe = fund.get("eps"), fund.get("bps"), fund.get("roe")

    if bps and roe is not None:
        roe_f = roe / 100.0  # 재무 ROE는 %로 저장 → 소수로
        justified_pbr = max(0.2, roe_f / r)  # 적자/저ROE는 하한 0.2배
        out["정당PBR(ROE기반)"] = round(bps * justified_pbr, 1)

    if eps and eps > 0:
        target_per = (per_median or _DEFAULT_PER) * per_mult
        out["EPS×목표PER"] = round(eps * target_per, 1)

    return out


def _scenario(fund: dict, per_median: float | None, close: float | None,
              name: str, r: float, per_mult: float) -> dict:
    methods = _methods(fund, per_median, r, per_mult)
    fair = round(sum(methods.values()) / len(methods), 1) if methods else None
    upside = round((fair - close) / close * 100.0, 1) if (fair and close) else None
    return {"name": name, "r": r, "per_mult": per_mult, "target": fair,
            "upside_pct": upside, "methods": methods}


def target_price(ticker: str) -> dict:
    fund, per_median = _latest_fundamentals(ticker)
    close = _close(ticker)
    if not fund or all(v is None for v in fund.values()):
        return {
            "ticker": ticker, "close": close, "fundamentals": fund or {},
            "base": None, "scenarios": [],
            "note": "재무 스냅샷(EPS·BPS·ROE)이 아직 없어 목표주가를 계산할 수 없습니다. "
                    "종목 상세를 한번 열면 재무가 수집됩니다.",
            "ai": None, "ai_error": None,
            "ai_enabled": bool((get_settings().anthropic_api_key or "").strip()),
        }

    scenarios = [_scenario(fund, per_median, close, *sc) for sc in _SCENARIOS]
    base = next((s for s in scenarios if s["name"] == "기준"), None)
    base_target = base["target"] if base else None
    base_upside = base["upside_pct"] if base else None

    ai = _ai_layer(ticker, fund, per_median, close, scenarios)

    return {
        "ticker": ticker,
        "close": round(close, 1) if close else None,
        "fundamentals": fund,
        "per_median": round(per_median, 2) if per_median else None,
        "target_per_used": round((per_median or _DEFAULT_PER), 2),
        "base": base_target,
        "base_upside_pct": base_upside,
        "scenarios": scenarios,
        "note": "적정주가 = 정당PBR(ROE기반)·EPS×목표PER 평균. 확정 목표가가 아닌 밸류에이션 추정치.",
        "ai": ai if (ai and "error" not in ai) else None,
        "ai_error": ai["error"] if (ai and "error" in ai) else None,
        "ai_enabled": bool((get_settings().anthropic_api_key or "").strip()),
    }


# --- Claude(Fable 5) 시나리오 목표가 층 (선택) ---------------------------------

_SYSTEM = (
    "너는 한국 주식 밸류에이션 애널리스트다. 주어진 재무지표와 현재가만 근거로 "
    "강세/기준/약세 3개 시나리오의 12개월 목표주가와 근거를 제시한다. 과장 없이 "
    "숫자에 근거해 보수적으로 판단하고, 한국어로 답한다."
)


def _ai_layer(ticker, fund, per_median, close, scenarios) -> dict | None:
    key = (get_settings().anthropic_api_key or "").strip()
    if not key:
        return None
    try:
        import anthropic
    except Exception:
        return {"error": "anthropic 패키지가 설치되어 있지 않습니다. (pip install anthropic)"}

    f = fund
    rule_lines = "\n".join(
        f"- {s['name']}: {s['target']}원 (상승여력 {s['upside_pct']}%)" for s in scenarios if s["target"]
    )
    prompt = (
        f"종목코드 {ticker}의 밸류에이션 스냅샷이다.\n\n"
        f"- 현재가: {close}원\n"
        f"- EPS: {f.get('eps')} / BPS: {f.get('bps')} / ROE: {f.get('roe')}%\n"
        f"- 현재 PER: {f.get('per')} / PBR: {f.get('pbr')} / 과거 PER 중앙값: {per_median}\n\n"
        f"[규칙 기반 1차 목표가]\n{rule_lines or '(계산불가)'}\n\n"
        "이 데이터만 근거로 12개월 목표주가를 판단하라. 설명·서론 없이 아래 JSON 객체 하나만 출력:\n"
        '{\n'
        '  "fair_value": 숫자(적정주가·원),\n'
        '  "targets": {"강세": 숫자, "기준": 숫자, "약세": 숫자},\n'
        '  "rationale": "3~4문장 근거",\n'
        '  "key_drivers": ["목표가를 움직일 핵심 변수 1~3개"],\n'
        '  "confidence": "높음|보통|낮음"\n'
        "}"
    )

    client = anthropic.Anthropic(api_key=key)
    last_err = "알 수 없음"
    for model in ("claude-fable-5", "claude-opus-4-8"):
        try:
            msg = client.messages.create(
                model=model, max_tokens=1200, system=_SYSTEM,
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
        except Exception as e:  # noqa: BLE001 — AI 층은 선택
            last_err = str(e)
            continue
    return {"error": f"Claude 호출 실패: {last_err}"}


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    import json
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None
