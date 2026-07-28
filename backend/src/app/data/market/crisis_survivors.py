"""위기를 이겨내고 우상향한 배당주.

2000 IT버블·2008 리먼·2020 팬데믹 — 세 번의 위기를 겪고도 장기 우상향하며 그 와중에
배당까지 계속 늘려온 미국 대표 배당주들을 보여준다. 각 종목마다:
  • 2000년~현재 월간 주가 지수(시작=100 정규화) — 우상향 궤적
  • 총 상승배수·연평균수익률(CAGR)
  • 세 위기 구간의 최대 낙폭(peak→trough)과 배당 방어(배당왕/귀족 연속 증액)

주가는 FinanceDataReader(장기 이력)로 받는다. 전 종목 취합이 무거워 하루 캐시.
"""
from __future__ import annotations

import threading
import time

from app.data.market import dividend_royalty

# 우상향 + 3대 위기 모두 배당 증액한 대표 배당주 (전부 배당왕/귀족)
SURVIVORS = ["JNJ", "PG", "KO", "PEP", "MCD", "WMT", "ABT", "LOW", "ADP", "ITW"]
BENCHMARK = "SPY"  # S&P500 지수 ETF (비교 기준)

# 위기 구간(주가 낙폭 계산용 실제 날짜 범위)
CRISIS_WINDOWS = [
    {"key": "it_2000", "label": "2000 IT버블", "start": "2000-03-01", "end": "2002-10-31"},
    {"key": "lehman_2008", "label": "2008 리먼", "start": "2007-10-01", "end": "2009-03-31"},
    {"key": "covid_2020", "label": "2020 팬데믹", "start": "2020-02-01", "end": "2020-04-30"},
]

_START = "2000-01-01"
_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 86400.0  # 하루


def _series(ticker: str):
    import FinanceDataReader as fdr
    df = fdr.DataReader(ticker, _START)
    if df is None or df.empty or "Close" not in df.columns:
        return None
    return df["Close"].dropna()


def _drawdown(close, start: str, end: str) -> float | None:
    """구간 내 고점 대비 최대 낙폭(%) — 음수."""
    import pandas as pd
    seg = close[(close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))]
    if len(seg) < 2:
        return None
    peak = seg.cummax()
    dd = (seg / peak - 1.0).min()
    return round(float(dd) * 100, 1)


def _one(ticker: str) -> dict | None:
    close = _series(ticker)
    if close is None or len(close) < 50:
        return None
    monthly = close.resample("ME").last().dropna()
    if monthly.empty:
        return None
    base = float(monthly.iloc[0])
    index = [{"date": d.strftime("%Y-%m"), "v": round(float(v) / base * 100, 1)}
             for d, v in monthly.items()]
    first, last = float(monthly.iloc[0]), float(monthly.iloc[-1])
    yrs = (monthly.index[-1] - monthly.index[0]).days / 365.25
    mult = last / first if first else None
    cagr = round(((last / first) ** (1 / yrs) - 1) * 100, 1) if (first and yrs > 1) else None
    roy = dividend_royalty.lookup(ticker)
    crises = []
    for w in CRISIS_WINDOWS:
        dd = _drawdown(close, w["start"], w["end"])
        # 배당왕/귀족은 연속 증액이므로 위기에도 '증액'
        div = "증액" if roy else "—"
        crises.append({"key": w["key"], "label": w["label"], "drawdown": dd, "dividend": div})
    return {
        "ticker": ticker,
        "name": (roy or {}).get("name") or ticker,
        "sector": (roy or {}).get("sector"),
        "tier_label": (roy or {}).get("tier_label"),
        "years": (roy or {}).get("years"),
        "multiple": round(mult, 1) if mult else None,
        "cagr": cagr,
        "index": index,
        "crises": crises,
    }


def _build() -> dict:
    rows = []
    for tk in SURVIVORS:
        try:
            r = _one(tk)
            if r:
                rows.append(r)
        except Exception:
            continue
    bench = None
    try:
        bench = _one(BENCHMARK)
    except Exception:
        bench = None
    rows.sort(key=lambda r: -(r["multiple"] or 0))
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start": _START,
        "benchmark": bench,
        "survivors": rows,
        "crises": [{"key": w["key"], "label": w["label"]} for w in CRISIS_WINDOWS],
        "note": ("2000년 초를 100으로 정규화한 월간 주가 궤적입니다. 낙폭은 각 위기 구간 "
                 "고점 대비 최대 하락률이며, 이들은 위기 때도 배당을 계속 늘린 배당왕·귀족입니다. "
                 "주가: FinanceDataReader, 배당 지위: 배당왕/귀족 기록."),
    }


def board() -> dict:
    with _lock:
        if _cache["data"] and time.time() - _cache["ts"] < TTL:
            return _cache["data"]
    out = _build()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = out
    return out
