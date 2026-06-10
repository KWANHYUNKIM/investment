"""Market-wide daily report (시장 전체 데일리 리포트).

Aggregates the price-factor grid into the day's top movers / most-traded names,
ranks who foreign & institutional investors sold the most among the heavily
traded names, pulls market-level news, and writes a templated summary. Cached
~10 min; opening it on any day yields that day's report.
"""
from __future__ import annotations

import threading
import time

from app.data import investor, news, store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 600.0


def _slim(r: dict) -> dict:
    return {
        "ticker": r["ticker"],
        "name": r["name"],
        "sector": r["sector"],
        "close": r.get("close"),
        "change_pct": r.get("change_pct"),
        "change": r.get("change"),
        "volume": r.get("volume"),
    }


def market_report() -> dict:
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    rows = store.screen_table_prices()
    valid = [r for r in rows if r.get("change_pct") is not None]
    date = rows[0]["date"] if rows else None

    gainers = sorted(valid, key=lambda r: r["change_pct"], reverse=True)[:12]
    losers = sorted(valid, key=lambda r: r["change_pct"])[:12]
    most_traded = sorted(
        [r for r in rows if r.get("volume")], key=lambda r: r["volume"], reverse=True
    )[:25]

    # Investor net-buy among the most heavily traded names (cached per ticker).
    flows: list[dict] = []
    for r in most_traded[:20]:
        try:
            inv = investor.investors(r["ticker"])
            if inv:
                f = inv[0]
                flows.append(
                    {"ticker": r["ticker"], "name": r["name"], "foreign": f["foreign"], "organ": f["organ"]}
                )
        except Exception:
            pass
    foreign_sellers = sorted([x for x in flows if x["foreign"] is not None], key=lambda x: x["foreign"])[:8]
    organ_sellers = sorted([x for x in flows if x["organ"] is not None], key=lambda x: x["organ"])[:8]

    up = sum(1 for r in valid if r["change_pct"] > 0)
    down = sum(1 for r in valid if r["change_pct"] < 0)
    flat = len(valid) - up - down

    market_news: list[dict] = []
    try:
        nw = news.news_for("코스피", limit=8)
        market_news = (nw.get("domestic") or [])[:6]
    except Exception:
        pass

    parts: list[str] = []
    if date:
        parts.append(f"{date} 기준, 상승 {up:,}종목 · 하락 {down:,}종목 · 보합 {flat:,}종목.")
    if gainers:
        g = gainers[0]
        parts.append(f"최고 상승은 {g['name']}({g['change_pct']:+.2f}%), ")
    if losers:
        l = losers[0]
        parts[-1] = parts[-1] + f"최대 하락은 {l['name']}({l['change_pct']:+.2f}%)였습니다." if parts else ""
    if foreign_sellers and foreign_sellers[0]["foreign"] is not None and foreign_sellers[0]["foreign"] < 0:
        fs = foreign_sellers[0]
        parts.append(f"거래 상위 종목 중 외국인은 {fs['name']}을(를) 가장 많이 순매도했습니다.")

    data = {
        "date": date,
        "breadth": {"up": up, "down": down, "flat": flat, "total": len(valid)},
        "gainers": [_slim(r) for r in gainers],
        "losers": [_slim(r) for r in losers],
        "most_traded": [_slim(r) for r in most_traded[:12]],
        "foreign_sellers": foreign_sellers,
        "organ_sellers": organ_sellers,
        "news": market_news,
        "summary": " ".join(p for p in parts if p),
    }

    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
