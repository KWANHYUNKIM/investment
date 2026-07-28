"""Market-wide daily report (시장 전체 데일리 리포트).

Centerpiece: for the day's most actively traded names, infer — without any LLM —
*why each investor type (외국인 / 개인 / 기관) was likely buying or selling*, by
combining net-buy direction, foreign-ratio change, price momentum, valuation, and
the themes read out of each stock's news headlines (see `insight.build`). Each
card also carries that stock's top headlines. Market breadth and mover tables are
kept as supporting context. Cached ~10 min; opening it on any day yields that
day's report.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.data.market import brokers
from app.data.intel import insight
from app.data.market import investor
from app.data.news import news
from app.data.infra import store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 600.0
N_INSIGHTS = 8  # how many most-traded names to analyse in depth


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


def _stock_insight(row: dict) -> dict | None:
    """Heavy per-stock work (investor flow + news) — run in a thread pool."""
    ticker, name = row["ticker"], row["name"]
    try:
        inv = investor.investors(ticker)
    except Exception:
        inv = []
    if not inv:
        return None
    f = inv[0]
    prev = inv[1] if len(inv) > 1 else {}
    fr = f.get("foreign_ratio")
    fr_prev = prev.get("foreign_ratio")
    fr_delta = (fr - fr_prev) if (fr is not None and fr_prev is not None) else None

    arts: list[dict] = []
    arts_global: list[dict] = []
    try:
        nw = news.news_for(name or ticker, limit=6)
        arts = (nw.get("domestic") or [])[:3]
        arts_global = (nw.get("global") or [])[:3]  # 해외(영문) 뉴스도 함께 보관
    except Exception:
        pass

    # 거래원(어느 증권사 창구가 매수/매도 상위였는지 + 외국계 추정 순매수)
    try:
        brk = brokers.brokers(ticker)
    except Exception:
        brk = {"sell": [], "buy": [], "foreign": None}

    sig = {
        "individual": f.get("individual"),
        "foreign": f.get("foreign"),
        "organ": f.get("organ"),
        "foreign_ratio": fr,
        "foreign_ratio_delta": fr_delta,
        "change_pct": row.get("change_pct"),
        "ret_1m": row.get("ret_1m"),
        "pct_from_high": row.get("pct_from_high"),
        "per": row.get("per"),
        "pbr": row.get("pbr"),
        "roe": row.get("roe"),
        "div_yield": row.get("div_yield"),
    }
    titles = [a.get("title", "") for a in arts]

    return {
        "ticker": ticker,
        "name": name,
        "sector": row.get("sector"),
        "close": row.get("close"),
        "change": row.get("change"),
        "change_pct": row.get("change_pct"),
        "volume": row.get("volume"),
        "foreign_ratio": fr,
        "foreign_ratio_delta": round(fr_delta, 2) if fr_delta is not None else None,
        "investors": insight.build(sig, titles),
        "news": [{"title": a.get("title"), "link": a.get("link"), "source": a.get("source")} for a in arts],
        "news_global": [{"title": a.get("title"), "link": a.get("link"), "source": a.get("source")} for a in arts_global],
        "brokers": brk,
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

    # --- per-stock investor reasoning for the most-traded names (parallel) ---
    insights: list[dict] = []
    targets = most_traded[:N_INSIGHTS]
    if targets:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(_stock_insight, r): r for r in targets}
            by_ticker: dict[str, dict] = {}
            for fut in as_completed(futs):
                try:
                    res = fut.result()
                except Exception:
                    res = None
                if res:
                    by_ticker[res["ticker"]] = res
        # preserve most-traded ordering
        insights = [by_ticker[r["ticker"]] for r in targets if r["ticker"] in by_ticker]

    # --- seller tables (reuse the flow we already pulled) ---
    flows: list[dict] = []
    for ins in insights:
        fv = next((iv["qty"] for iv in ins["investors"] if iv["key"] == "foreign"), None)
        ov = next((iv["qty"] for iv in ins["investors"] if iv["key"] == "organ"), None)
        flows.append({"ticker": ins["ticker"], "name": ins["name"], "foreign": fv, "organ": ov})
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

    # --- market-level summary, including who was net buying overall ---
    parts: list[str] = []
    if date:
        parts.append(f"{date} 기준, 상승 {up:,}종목 · 하락 {down:,}종목 · 보합 {flat:,}종목.")
    if gainers:
        parts.append(f"최고 상승 {gainers[0]['name']}({gainers[0]['change_pct']:+.2f}%), "
                     f"최대 하락 {losers[0]['name']}({losers[0]['change_pct']:+.2f}%).")

    def _net_dir(key: str) -> tuple[int, int]:
        buy = sum(1 for ins in insights for iv in ins["investors"] if iv["key"] == key and (iv["qty"] or 0) > 0)
        sell = sum(1 for ins in insights for iv in ins["investors"] if iv["key"] == key and (iv["qty"] or 0) < 0)
        return buy, sell

    if insights:
        fb, fs = _net_dir("foreign")
        ib, is_ = _net_dir("individual")
        f_word = "순매수 우위" if fb > fs else "순매도 우위" if fs > fb else "혼조"
        i_word = "순매수 우위" if ib > is_ else "순매도 우위" if is_ > ib else "혼조"
        parts.append(f"거래 상위 {len(insights)}종목 기준 외국인은 {f_word}, 개인은 {i_word}였습니다.")

    data = {
        "date": date,
        "breadth": {"up": up, "down": down, "flat": flat, "total": len(valid)},
        "insights": insights,
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
