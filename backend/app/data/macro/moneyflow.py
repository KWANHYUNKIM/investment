"""글로벌 자금 흐름(유동성) — 세계가 돈을 푸나·쓰나·모으나 + 어디로 흐르나.

주식 수급만이 아니라 '돈 그 자체'의 흐름을 실시간 뉴스 + 보유 데이터로 유추한다:
  1. 유동성 레짐  — 중앙은행이 돈을 푸는가(완화·QE) 조이는가(긴축·QT),
  2. 한국 자금    — 외국인 vs 국내(개인+기관) 주식 순매수 + 원/달러(외국자본 유입 신호),
  3. 크로스에셋   — 현금이 증시·코인으로 가나 금·달러·채권으로 가나(risk-on/off),
  4. 자산군별 흐름 — 정책·외국인자금·부동산·채권·현금/안전자산·원자재·외환·펀드플로우
     각각의 뉴스 동향(자금 우호/경계),
종합해 "지금 글로벌 유동성 완화/긴축, 외국 자본 한국 유입/이탈, 위험선호 on/off"로 판정.

뉴스는 키 없는 Google News RSS, 수급은 investor_flow, 시세는 crossasset 재사용.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.data.macro import crossasset
from app.data.macro import macro
from app.data.news import news
from app.data.macro import rates
from app.data.infra import store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 600.0  # 10분 (실시간 폴링 + 스케줄러 워밍)

# ── 유동성 레짐: 돈을 푸나(완화) 조이나(긴축) ──
_EASE = (
    "인하", "금리인하", "완화", "양적완화", "부양", "유동성 공급", "유동성 확대", "돈풀기", "돈 풀기",
    "rate cut", "cut rates", "easing", "ease", "stimulus", "qe", "quantitative easing",
    "liquidity injection", "dovish", "accommodative", "lower rates", "pivot",
)
_TIGHT = (
    "인상", "금리인상", "긴축", "양적긴축", "유동성 흡수", "돈줄", "테이퍼링",
    "rate hike", "hike", "tightening", "tighten", "hawkish", "qt", "quantitative tightening",
    "balance sheet reduction", "tapering", "higher for longer",
)

_LIQ_QUERIES = (
    ("기준금리 통화정책 유동성", "ko", "KR", "KR:ko"),
    ("양적완화 긴축 유동성 공급", "ko", "KR", "KR:ko"),
    ("Federal Reserve monetary policy liquidity", "en-US", "US", "US:en"),
    ("central bank rate cut hike QE QT", "en-US", "US", "US:en"),
    ("global liquidity money supply M2", "en-US", "US", "US:en"),
    ("fiscal stimulus government spending debt", "en-US", "US", "US:en"),
)

# 지역별 중앙은행 스탠스 — 누가 돈을 푸나/조이나. (region, label, flag, query)
_REGION_CB = (
    ("미국", "Fed", "🇺🇸", "Federal Reserve interest rate policy decision"),
    ("유럽", "ECB", "🇪🇺", "European Central Bank ECB rate policy"),
    ("일본", "BOJ", "🇯🇵", "Bank of Japan BOJ policy rate yen"),
    ("중국", "PBOC", "🇨🇳", "China PBOC stimulus rate cut monetary easing"),
    ("한국", "한국은행", "🇰🇷", "한국은행 기준금리 통화정책"),
)

# ── 자산군별 자금 흐름(돈이 어디로) ──  (key, label, icon, [queries])
_CATEGORIES = [
    ("policy", "정책·중앙은행", "🏛️", [
        ("연준 한국은행 통화정책 금리", "ko", "KR", "KR:ko"),
        ("Fed ECB BOJ policy rates decision", "en-US", "US", "US:en"),
    ]),
    ("foreign_kr", "외국인 자금 (한국)", "🌏", [
        ("외국인 자금 유입 이탈 코스피", "ko", "KR", "KR:ko"),
        ("foreign investors Korea stocks fund flow", "en-US", "US", "US:en"),
    ]),
    ("real_estate", "부동산", "🏠", [
        ("부동산 시장 집값 자금", "ko", "KR", "KR:ko"),
        ("real estate housing market money", "en-US", "US", "US:en"),
    ]),
    ("bonds", "채권·국채", "📜", [
        ("국채 채권 시장 자금 금리", "ko", "KR", "KR:ko"),
        ("bond market treasury yields flows", "en-US", "US", "US:en"),
    ]),
    ("cash_safe", "현금·안전자산", "💵", [
        ("현금 예금 MMF 머니마켓 자금", "ko", "KR", "KR:ko"),
        ("cash money market fund safe haven", "en-US", "US", "US:en"),
    ]),
    ("commodities", "원자재·금", "🪙", [
        ("금값 유가 원자재 자금", "ko", "KR", "KR:ko"),
        ("gold oil commodities money flow", "en-US", "US", "US:en"),
    ]),
    ("fx", "외환·달러", "💱", [
        ("달러 환율 외환보유고 원화", "ko", "KR", "KR:ko"),
        ("US dollar forex reserves currency", "en-US", "US", "US:en"),
    ]),
    ("fund_flow", "글로벌 펀드플로우", "🌊", [
        ("글로벌 자금 이동 신흥국 펀드", "ko", "KR", "KR:ko"),
        ("global fund flows EPFR emerging markets", "en-US", "US", "US:en"),
    ]),
    ("crypto", "가상자산 자금", "₿", [
        ("비트코인 가상자산 자금 유입 ETF", "ko", "KR", "KR:ko"),
        ("bitcoin crypto inflows ETF institutional", "en-US", "US", "US:en"),
    ]),
    ("em_flows", "신흥국 자금", "🌐", [
        ("신흥국 증시 자금 유입 이탈", "ko", "KR", "KR:ko"),
        ("emerging markets capital flows equities", "en-US", "US", "US:en"),
    ]),
    ("sovereign_pension", "국부펀드·연기금", "🏦", [
        ("국민연금 연기금 국부펀드 운용 자금", "ko", "KR", "KR:ko"),
        ("sovereign wealth fund pension allocation", "en-US", "US", "US:en"),
    ]),
    ("buyback_dividend", "자사주·배당", "💰", [
        ("자사주 매입 배당 주주환원", "ko", "KR", "KR:ko"),
        ("stock buyback dividend shareholder return", "en-US", "US", "US:en"),
    ]),
    ("ipo", "IPO·공모 자금", "📈", [
        ("IPO 공모주 청약 상장 자금", "ko", "KR", "KR:ko"),
        ("IPO listing capital raise market", "en-US", "US", "US:en"),
    ]),
    ("household_credit", "가계부채·신용", "🏚️", [
        ("가계부채 대출 신용 자금", "ko", "KR", "KR:ko"),
        ("household debt consumer credit lending", "en-US", "US", "US:en"),
    ]),
]


def _is_article(a: dict) -> bool:
    return bool(
        (a.get("title") or "").strip()
        and (a.get("source") or "").strip()
        and (a.get("link") or "").startswith("http")
    )


def _fetch(q) -> list[dict]:
    try:
        arts = news._fetch(q[0], q[1], q[2], q[3], 8)
    except Exception:
        return []
    return [a for a in arts if _is_article(a)]


def _pool(queries) -> list[dict]:
    pool: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for arts in ex.map(_fetch, queries):
            for a in arts:
                t = a.get("title", "").strip()
                if t and t not in seen:
                    seen.add(t)
                    pool.append(a)
    pool.sort(key=lambda a: a.get("ts") or 0, reverse=True)
    return pool


def _liq_lean(text: str) -> str:
    t = text.lower()
    e = sum(1 for w in _EASE if w in t)
    g = sum(1 for w in _TIGHT if w in t)
    if e > g:
        return "완화"
    if g > e:
        return "긴축"
    return "중립"


def _digest(pool: list[dict], n: int = 5) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for a in pool[:6]:
        for line in a.get("cluster", []):
            k = line.strip()
            if k and k not in seen:
                seen.add(k)
                out.append(line)
            if len(out) >= n:
                break
        if len(out) >= n:
            break
    return out


def _headlines(pool: list[dict], n: int = 6) -> list[dict]:
    return [{"title": a["title"], "link": a["link"], "source": a["source"]} for a in pool[:n]]


def _liquidity() -> dict:
    pool = _pool(_LIQ_QUERIES)
    ease = sum(1 for a in pool if _liq_lean(a["title"]) == "완화")
    tight = sum(1 for a in pool if _liq_lean(a["title"]) == "긴축")
    regime = "완화 (돈 푼다)" if ease > tight * 1.15 else "긴축 (돈 조인다)" if tight > ease * 1.15 else "중립 (관망)"
    tone = "완화" if ease > tight else "긴축" if tight > ease else "중립"
    return {
        "regime": regime, "tone": tone, "ease": ease, "tight": tight,
        "count": len(pool), "headlines": _headlines(pool, 6), "digest": _digest(pool),
    }


def _fdr_last(sym: str) -> tuple[float | None, float | None]:
    """fdr 종가 (최신, 전일대비). 실패 시 (None, None)."""
    try:
        import FinanceDataReader as fdr
        s = fdr.DataReader(sym)["Close"].dropna()
        if len(s) < 2:
            return (float(s.iloc[-1]), None) if len(s) else (None, None)
        last = float(s.iloc[-1])
        return last, last - float(s.iloc[-2])
    except Exception:
        return None, None


def _crypto_fng() -> tuple[int | None, str | None]:
    """가상자산 공포·탐욕 지수(alternative.me, 무료·키없음). (0~100, 분류). 1회 재시도."""
    for _ in range(2):
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=20,
                             headers={"User-Agent": "Mozilla/5.0"})
            d = (r.json() or {}).get("data") or []
            if d:
                return int(d[0]["value"]), d[0].get("value_classification")
        except Exception:
            time.sleep(0.5)
    return None, None


def _indicators() -> list[dict]:
    """실측 하드데이터(무료·키없음) — VIX·미10년금리·가상자산 공포탐욕 등."""
    out: list[dict] = []
    vix, vchg = _fdr_last("VIX")
    if vix is not None:
        sig = "공포" if vix >= 25 else "경계" if vix >= 20 else "안정"
        out.append({"key": "vix", "label": "VIX 공포지수", "value": round(vix, 2),
                    "unit": "pt", "change": round(vchg, 2) if vchg is not None else None,
                    "signal": sig, "desc": "변동성↑ = 위험회피(현금·안전자산)"})
    y10, ychg = _fdr_last("US10YT")
    if y10 is not None:
        sig = "상승(긴축압력)" if (ychg or 0) > 0 else "하락(완화)" if (ychg or 0) < 0 else "보합"
        out.append({"key": "us10y", "label": "미 10년 국채금리", "value": round(y10, 2),
                    "unit": "%", "change": round(ychg, 3) if ychg is not None else None,
                    "signal": sig, "desc": "금리↑ = 유동성 긴축·자금조달비용↑"})
    fng, cls = _crypto_fng()
    if fng is not None:
        ko = {"Extreme Fear": "극단적 공포", "Fear": "공포", "Neutral": "중립",
              "Greed": "탐욕", "Extreme Greed": "극단적 탐욕"}.get(cls or "", cls or "")
        out.append({"key": "crypto_fng", "label": "가상자산 공포·탐욕", "value": fng,
                    "unit": "/100", "change": None, "signal": ko,
                    "desc": "0=공포(자금이탈) · 100=탐욕(자금유입)"})
    return out


def _region_stance(item) -> dict:
    """지역 중앙은행 스탠스 — 완화(돈 푼다)/긴축(조인다)/중립 + 대표 헤드라인."""
    region, label, flag, query = item
    pool = _pool([(query, "en-US", "US", "US:en")] if region != "한국" else [(query, "ko", "KR", "KR:ko")])
    ease = sum(1 for a in pool if _liq_lean(a["title"]) == "완화")
    tight = sum(1 for a in pool if _liq_lean(a["title"]) == "긴축")
    stance = "완화" if ease > tight else "긴축" if tight > ease else "중립"
    return {
        "region": region, "label": label, "flag": flag, "stance": stance,
        "ease": ease, "tight": tight, "count": len(pool),
        "headlines": _headlines(pool, 3),
    }


def _category(cat) -> dict:
    key, label, icon, queries = cat
    pool = _pool(queries)
    pos = sum(1 for a in pool if macro._lean(a["title"]) == "긍정")
    neg = sum(1 for a in pool if macro._lean(a["title"]) == "부정")
    direction = "우호" if pos > neg else "경계" if neg > pos else "중립"
    return {
        "key": key, "label": label, "icon": icon,
        "direction": direction, "pos": pos, "neg": neg, "count": len(pool),
        "headlines": _headlines(pool, 5), "digest": _digest(pool, 3),
    }


def _kr_capital() -> dict:
    """외국인 vs 국내(개인+기관) 주식 순매수 흐름 + 원/달러."""
    try:
        rows = store.market_investor_daily(days=7)
    except Exception:
        rows = []
    series = [
        {
            "date": r["date"],
            "foreign": r.get("foreign"),
            "domestic": round((r.get("individual") or 0) + (r.get("organ") or 0), 1),
            "individual": r.get("individual"),
            "organ": r.get("organ"),
        }
        for r in rows
    ]
    latest = series[0] if series else None
    direction = "중립"
    if latest and latest["foreign"] is not None:
        direction = "유입" if latest["foreign"] > 0 else "이탈" if latest["foreign"] < 0 else "중립"
    return {"series": series, "latest": latest, "foreign_direction": direction}


def _usdkrw_from(ca: dict) -> dict | None:
    for g in ca.get("groups", []):
        for a in g.get("assets", []):
            if a.get("key") == "usdkrw":
                return {"value": a.get("value"), "change_pct": a.get("change_pct")}
    return None


def pulse(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    liquidity = _liquidity()
    kr = _kr_capital()
    try:
        ca = crossasset.cross_asset()
    except Exception:
        ca = {"flow": {}, "groups": []}
    with ThreadPoolExecutor(max_workers=10) as ex:
        categories = list(ex.map(_category, _CATEGORIES))
        regions = list(ex.map(_region_stance, _REGION_CB))
        ind_future = ex.submit(_indicators)  # fdr+http는 별도로
        indicators = ind_future.result()
    # 금리 결정 일정(다음 발표·D-day) — rates 모듈 재사용.
    try:
        rc = rates.rate_calendar()
        rate_schedule = rc.get("schedule", [])
    except Exception:
        rate_schedule = []

    usdkrw = _usdkrw_from(ca)
    ca_flow = ca.get("flow", {}) or {}
    risk = ca_flow.get("tone") or "중립"  # 긍정=위험선호, 부정=위험회피

    # 종합 판정.
    foreign_dir = kr["foreign_direction"]
    risk_word = "위험선호(Risk-on)" if risk == "긍정" else "위험회피(Risk-off)" if risk == "부정" else "혼조"
    won = ""
    if usdkrw and usdkrw.get("change_pct") is not None:
        won = "원화 강세(외국자본 우호)" if usdkrw["change_pct"] < 0 else "원화 약세(자본 유출 압력)"
    narrative = (
        f"글로벌 유동성은 {liquidity['regime']} 분위기"
        f"(완화 {liquidity['ease']} · 긴축 {liquidity['tight']}). "
        f"한국 주식은 외국인 {foreign_dir}"
        + (f", {won}" if won else "")
        + f". 글로벌 자금은 {risk_word}."
    )

    data = {
        "as_of": time.strftime("%Y-%m-%d %H:%M:%S"),
        "verdict": {
            "liquidity": liquidity["tone"],
            "liquidity_label": liquidity["regime"],
            "foreign_kr": foreign_dir,
            "risk": risk_word,
            "narrative": narrative,
        },
        "liquidity": liquidity,
        "indicators": indicators,
        "regions": regions,
        "rate_schedule": rate_schedule,
        "kr_capital": kr,
        "usdkrw": usdkrw,
        "cross_asset": {
            "verdict": ca_flow.get("verdict"),
            "tone": ca_flow.get("tone"),
            "desc": ca_flow.get("desc"),
            "metrics": ca_flow.get("metrics"),
            "as_of": ca.get("as_of"),
        },
        "categories": categories,
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
