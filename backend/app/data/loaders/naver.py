"""Naver mobile fundamentals loader.

`m.stock.naver.com/api/stock/{code}/integration` exposes a `totalInfos` list
with PER / PBR / EPS / BPS / 배당수익률 / 외인소진율 / 시총 — the fundamentals
pykrx can't provide in this environment. We normalise them into our store's
fundamentals schema (current snapshot, stamped with today's date).
"""
from __future__ import annotations

import re
import time
from datetime import datetime

import pandas as pd
import requests

MARKET = "KR"
_UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)", "Referer": "https://m.stock.naver.com/"}


def _num(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"-?[\d,]+\.?\d*", s)
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None


def _market_cap(s: str | None) -> float | None:
    """'1,768조 4,993억' -> 176849930000000.0 (KRW)."""
    if not s:
        return None
    total = 0.0
    jo = re.search(r"([\d,]+)\s*조", s)
    eok = re.search(r"([\d,]+)\s*억", s)
    if jo:
        total += float(jo.group(1).replace(",", "")) * 1e12
    if eok:
        total += float(eok.group(1).replace(",", "")) * 1e8
    return total or None


def fetch_fundamentals(ticker: str, on: str | None = None) -> pd.DataFrame:
    url = f"https://m.stock.naver.com/api/stock/{ticker}/integration"
    r = requests.get(url, headers=_UA, timeout=12)
    r.raise_for_status()
    info = {x.get("key"): x.get("value") for x in (r.json().get("totalInfos") or [])}
    if not info:
        return pd.DataFrame()

    per = _num(info.get("PER"))
    pbr = _num(info.get("PBR"))
    eps = _num(info.get("EPS"))
    bps = _num(info.get("BPS"))
    div = _num(info.get("배당수익률"))
    frate = _num(info.get("외인소진율"))
    mcap = _market_cap(info.get("시총"))
    roe = round(100.0 * eps / bps, 2) if (eps and bps) else None

    row = {
        "market": MARKET,
        "ticker": ticker,
        "date": pd.to_datetime(on).date() if on else datetime.now().date(),
        "per": per,
        "pbr": pbr,
        "eps": eps,
        "bps": bps,
        "roe": roe,
        "div_yield": div,
        "market_cap": mcap,
        "foreign_ratio": frate,
    }
    return pd.DataFrame([row])


def pace(seconds: float = 0.05) -> None:
    time.sleep(seconds)
