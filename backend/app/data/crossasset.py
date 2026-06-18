"""크로스에셋 자금 흐름 (cross-asset money-flow snapshot).

"현금이 어디로 흐르는지" — 한국 증시 하나만이 아니라 그 증시에 영향을 주는 모든
판(미국·아시아·유럽 증시), 안전자산(금·국채금리·달러), 위험·원자재(비트코인·
이더리움·유가)의 당일 등락을 한 화면에 모아, 자금이 위험자산으로 유입(Risk-on)
되는지 안전자산·현금으로 빠지는지(Risk-off)를 읽어 준다.

시세는 FinanceDataReader(증시·원자재·암호화폐·환율 단일 소스) 기준, 캐시 10분.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import FinanceDataReader as fdr

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 60.0  # 60s — short so live polling actually refreshes (upstream throttled by cache)

# (key, 라벨, fdr 심볼, 그룹, 종류, 단위)
#   종류: index 증시 / crypto 암호화폐 / commodity 원자재 / safe 안전자산 /
#         yield 금리 / fx 환율
_ASSETS: tuple[tuple[str, str, str, str, str, str], ...] = (
    # 미국 증시
    ("sp500", "S&P 500", "US500", "미국 증시", "index", "pt"),
    ("nasdaq", "나스닥", "IXIC", "미국 증시", "index", "pt"),
    ("dow", "다우존스", "DJI", "미국 증시", "index", "pt"),
    # 아시아·유럽 증시 (우리 증시에 영향을 주는 다른 판들)
    ("kospi", "코스피", "KS11", "아시아·유럽 증시", "index", "pt"),
    ("kosdaq", "코스닥", "KQ11", "아시아·유럽 증시", "index", "pt"),
    ("nikkei", "닛케이225", "N225", "아시아·유럽 증시", "index", "pt"),
    ("shanghai", "상해종합", "SSEC", "아시아·유럽 증시", "index", "pt"),
    ("hangseng", "항셍", "HSI", "아시아·유럽 증시", "index", "pt"),
    ("dax", "독일 DAX", "GDAXI", "아시아·유럽 증시", "index", "pt"),
    ("ftse", "영국 FTSE100", "FTSE", "아시아·유럽 증시", "index", "pt"),
    # 안전자산·현금 (자금이 빠질 때 모이는 곳)
    ("gold", "금", "GC=F", "안전자산·현금", "safe", "usd"),
    ("ust10y", "미국 국채 10년", "US10YT", "안전자산·현금", "yield", "pct"),
    ("usdkrw", "원/달러 환율", "USD/KRW", "안전자산·현금", "fx", "krw"),
    # 위험자산·원자재
    ("btc", "비트코인", "BTC/USD", "위험자산·원자재", "crypto", "usd"),
    ("eth", "이더리움", "ETH/USD", "위험자산·원자재", "crypto", "usd"),
    ("wti", "WTI 유가", "CL=F", "위험자산·원자재", "commodity", "usd"),
)

_GROUP_ORDER = ["미국 증시", "아시아·유럽 증시", "안전자산·현금", "위험자산·원자재"]


def _one(spec: tuple[str, str, str, str, str, str]) -> dict | None:
    key, label, sym, group, kind, unit = spec
    try:
        df = fdr.DataReader(sym)
        if df is None or df.empty or "Close" not in df.columns:
            return None
        df = df.dropna(subset=["Close"])
        if df.empty:
            return None
        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
        chg_pct = ((last - prev) / prev * 100.0) if prev else 0.0
        return {
            "key": key,
            "label": label,
            "group": group,
            "kind": kind,
            "unit": unit,
            "value": round(last, 2),
            "change_pct": round(chg_pct, 2),
            "date": str(df.index[-1])[:10],
        }
    except Exception:
        return None


def _flow_read(assets: list[dict]) -> dict:
    """위험선호 / 위험회피 / 혼조 — 자금 흐름 방향을 한 줄로 읽는다."""
    by = {a["key"]: a for a in assets}

    def avg(keys: list[str]) -> float | None:
        vals = [by[k]["change_pct"] for k in keys if k in by and by[k]["change_pct"] is not None]
        return sum(vals) / len(vals) if vals else None

    equities = avg(["sp500", "nasdaq", "dow", "kospi", "kosdaq", "nikkei", "shanghai", "hangseng", "dax", "ftse"])
    crypto = avg(["btc", "eth"])
    gold = by.get("gold", {}).get("change_pct")
    usdkrw = by.get("usdkrw", {}).get("change_pct")  # +면 달러 강세 = 위험회피

    # Risk-on(+) vs Risk-off(-) 점수: 위험자산 강세 +, 안전자산 강세 -.
    score = 0.0
    if equities is not None:
        score += equities
    if crypto is not None:
        score += crypto * 0.5
    if gold is not None:
        score -= gold * 0.5
    if usdkrw is not None:
        score -= usdkrw * 0.5

    if score > 0.25:
        verdict, tone = "위험선호 (Risk-on)", "긍정"
        desc = "자금이 주식·암호화폐 등 위험자산으로 유입되는 흐름입니다."
    elif score < -0.25:
        verdict, tone = "위험회피 (Risk-off)", "부정"
        desc = "자금이 금·달러 등 안전자산·현금으로 이동하는 흐름입니다."
    else:
        verdict, tone = "혼조 (중립)", "중립"
        desc = "위험·안전자산이 엇갈려 뚜렷한 자금 쏠림은 약합니다."

    parts = []
    if equities is not None:
        parts.append(f"글로벌 증시 평균 {equities:+.2f}%")
    if crypto is not None:
        parts.append(f"암호화폐 {crypto:+.2f}%")
    if gold is not None:
        parts.append(f"금 {gold:+.2f}%")
    if usdkrw is not None:
        parts.append(f"원/달러 {usdkrw:+.2f}%")

    return {
        "verdict": verdict,
        "tone": tone,
        "score": round(score, 2),
        "desc": desc,
        "metrics": {"equities": equities, "crypto": crypto, "gold": gold, "usdkrw": usdkrw},
        "summary": f"자금 흐름: {verdict} — {desc} (" + ", ".join(parts) + ")." if parts else f"자금 흐름: {verdict} — {desc}",
    }


def cross_asset() -> dict:
    """그룹별 자산 시세 + 자금 흐름 판단 (cached ~10분)."""
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    assets: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(_one, _ASSETS):
            if res:
                assets.append(res)

    groups: list[dict] = []
    for g in _GROUP_ORDER:
        items = [a for a in assets if a["group"] == g]
        if items:
            groups.append({"group": g, "assets": items})

    flow = _flow_read(assets)
    now = time.time()
    data = {
        "groups": groups,
        "flow": flow,
        "count": len(assets),
        "ts": now,
        "as_of": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
    }
    with _lock:
        _cache["ts"] = now
        _cache["data"] = data
    return data
