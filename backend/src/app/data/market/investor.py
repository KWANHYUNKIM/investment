"""Per-stock investor trading trend (개인 / 외국인 / 기관) via Naver mobile API.

`https://m.stock.naver.com/api/stock/{code}/trend` returns the last ~10 trading
days of net-buy quantities by investor type plus the foreign holding ratio — no
key, no login. This is the only working source for 투자자별 매매동향 here
(pykrx's investor endpoints and KRX/data.krx are broken/blocked).
"""
from __future__ import annotations

import threading
import time

import requests

_UA = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    "Referer": "https://m.stock.naver.com/",
}
_lock = threading.Lock()
_cache: dict[str, tuple[float, list[dict]]] = {}
TTL = 60.0


def _int(s) -> int | None:
    if s is None:
        return None
    try:
        return int(str(s).replace(",", "").replace("+", "").strip())
    except ValueError:
        return None


def _pct(s) -> float | None:
    if s is None:
        return None
    try:
        return float(str(s).replace("%", "").replace(",", "").strip())
    except ValueError:
        return None


def investors(ticker: str) -> list[dict]:
    """Recent daily net-buy by investor type for a ticker (cached ~60s)."""
    with _lock:
        hit = _cache.get(ticker)
        if hit and (time.time() - hit[0] < TTL):
            return hit[1]

    url = f"https://m.stock.naver.com/api/stock/{ticker}/trend"
    rows: list[dict] = []
    try:
        r = requests.get(url, headers=_UA, timeout=12)
        r.raise_for_status()
        for d in r.json():
            bd = str(d.get("bizdate", ""))
            date = f"{bd[0:4]}-{bd[4:6]}-{bd[6:8]}" if len(bd) == 8 else bd
            rows.append(
                {
                    "date": date,
                    "individual": _int(d.get("individualPureBuyQuant")),
                    "foreign": _int(d.get("foreignerPureBuyQuant")),
                    "organ": _int(d.get("organPureBuyQuant")),
                    "foreign_ratio": _pct(d.get("foreignerHoldRatio")),
                    "close": _int(d.get("closePrice")),
                }
            )
    except Exception:
        if _cache.get(ticker):
            return _cache[ticker][1]
        raise

    with _lock:
        _cache[ticker] = (time.time(), rows)
    return rows
