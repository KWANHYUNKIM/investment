"""Finnhub (finnhub.io) 해외 종목 펀더멘털 — 글로벌 경쟁지도의 해외 데이터 소스.

yfinance가 429로 막혀 그 대체로 쓴다. 무료 키(60 calls/min)면 충분하다. 심볼당:
  • /stock/profile2 — 회사명·국가·통화·거래소·업종·상장주식수
  • /quote         — 현재가(c)·당일 등락률(dp)
  • /stock/metric  — 영업이익률(operatingMarginTTM)·순이익률
시가총액은 통화 모호성을 피해 ``상장주식수 × 현재가 × FX`` 로 직접 USD 환산한다.
키가 없으면 모든 함수가 조용히 비활성(빈 결과)으로 동작한다.
"""
from __future__ import annotations

import threading
import time

import pandas as pd
import requests

from app.core.config import get_settings
from app.data import store

_BASE = "https://finnhub.io/api/v1"

# 통화 1단위 = ? USD (FDR 실패 시 폴백; 대략값). FX는 _fx_map()이 갱신 시도.
_FX_FALLBACK = {
    "USD": 1.0, "KRW": 0.00073, "JPY": 0.0064, "EUR": 1.08, "CNY": 0.14,
    "TWD": 0.031, "HKD": 0.128, "GBP": 1.27, "CHF": 1.12, "DKK": 0.145,
    "SEK": 0.095, "SGD": 0.74, "AUD": 0.66, "CAD": 0.73,
}

_lock = threading.Lock()
_fx_cache: dict = {"ts": 0.0, "map": None}
_FX_TTL = 6 * 3600.0


def enabled() -> bool:
    return bool(get_settings().finnhub_api_key)


def _fx_map() -> dict[str, float]:
    """통화→USD 환율. FDR로 주요 통화 시도, 실패분은 폴백값."""
    with _lock:
        if _fx_cache["map"] is not None and time.time() - _fx_cache["ts"] < _FX_TTL:
            return _fx_cache["map"]
    fx = dict(_FX_FALLBACK)
    try:
        import FinanceDataReader as fdr
        # USD/XXX (1 USD = n XXX) → 1 XXX = 1/n USD
        for cur, pair in [("KRW", "USD/KRW"), ("JPY", "USD/JPY"), ("CNY", "USD/CNY"),
                          ("TWD", "USD/TWD"), ("HKD", "USD/HKD")]:
            try:
                df = fdr.DataReader(pair)
                v = float(df["Close"].dropna().iloc[-1])
                if v > 0:
                    fx[cur] = 1.0 / v
            except Exception:
                pass
        # EUR/USD, GBP/USD (1 XXX = n USD)
        for cur, pair in [("EUR", "EUR/USD"), ("GBP", "GBP/USD"), ("CHF", "CHF/USD")]:
            try:
                df = fdr.DataReader(pair)
                v = float(df["Close"].dropna().iloc[-1])
                if v > 0:
                    fx[cur] = v
            except Exception:
                pass
    except Exception:
        pass
    with _lock:
        _fx_cache["ts"] = time.time()
        _fx_cache["map"] = fx
    return fx


def _get(path: str, params: dict) -> dict | None:
    params = {**params, "token": get_settings().finnhub_api_key}
    try:
        r = requests.get(f"{_BASE}{path}", params=params, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def fetch(symbol: str, fx: dict[str, float] | None = None) -> dict | None:
    """One foreign symbol → fundamentals row. None on failure / not found."""
    if not enabled():
        return None
    prof = _get("/stock/profile2", {"symbol": symbol})
    if not prof or not prof.get("name"):
        return None
    fx = fx or _fx_map()
    quote = _get("/quote", {"symbol": symbol}) or {}
    metric = (_get("/stock/metric", {"symbol": symbol, "metric": "all"}) or {}).get("metric", {})

    cur = (prof.get("currency") or "USD").upper()
    price = _num(quote.get("c"))
    shares = _num(prof.get("shareOutstanding"))  # in millions
    mcap_usd = None
    if price and shares:
        mcap_usd = shares * 1e6 * price * fx.get(cur, _FX_FALLBACK.get(cur, 1.0))

    op = _num(metric.get("operatingMarginTTM"))
    if op is None:
        op = _num(metric.get("operatingMarginAnnual"))
    net = _num(metric.get("netProfitMarginTTM"))
    if net is None:
        net = _num(metric.get("netProfitMarginAnnual"))

    return {
        "symbol": symbol,
        "name": prof.get("name"),
        "country": prof.get("country"),
        "exchange": prof.get("exchange"),
        "currency": cur,
        "industry": prof.get("finnhubIndustry"),
        "market_cap_usd": mcap_usd,
        "op_margin": round(op, 2) if op is not None else None,
        "net_margin": round(net, 2) if net is not None else None,
        "price": price,
        "change_pct": _num(quote.get("dp")),
        "updated": time.strftime("%Y-%m-%d %H:%M"),
    }


def refresh_many(symbols: list[str], pause: float = 1.1) -> int:
    """Bulk fetch foreign fundamentals (paced for the 60/min free tier). Persists."""
    if not enabled():
        return 0
    fx = _fx_map()
    rows: list[dict] = []
    n = 0
    for sym in symbols:
        row = fetch(sym, fx)
        if row:
            rows.append(row)
            n += 1
        if len(rows) >= 20:
            try:
                store.upsert_foreign_fin(pd.DataFrame(rows))
            except Exception:
                pass
            rows = []
        if pause:
            time.sleep(pause)
    if rows:
        try:
            store.upsert_foreign_fin(pd.DataFrame(rows))
        except Exception:
            pass
    return n
