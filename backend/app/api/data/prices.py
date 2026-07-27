"""Prices / quotes / OHLC endpoints."""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, HTTPException, Query

from app.data.infra import store
from app.data.news import feed

from ._common import _f

router = APIRouter()


@router.get("/coverage")
def coverage():
    """Per-market summary of stored price data — feeds the dashboard."""
    return store.coverage().to_dict(orient="records")


@router.get("/securities")
def securities(market: str | None = Query(default=None)):
    df = store.list_securities(market=market)
    return df.to_dict(orient="records")


@router.get("/prices")
def prices(
    tickers: str = Query(..., description="comma-separated tickers"),
    market: str | None = None,
    start: str | None = None,
    end: str | None = None,
    field: str = "close",
):
    tk = [t.strip() for t in tickers.split(",") if t.strip()]
    wide = store.load_prices(tickers=tk, market=market, start=start, end=end, field=field)
    if wide.empty:
        return {"dates": [], "series": {}}
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in wide.index],
        "series": {col: [None if v != v else round(float(v), 4) for v in wide[col]]
                   for col in wide.columns},
    }


# /quotes recomputes a full-board price scan; the underlying EOD/settled data
# only moves on the price scheduler's cadence, so a short TTL cache absorbs
# frontend polling without serving stale numbers.
_quotes_lock = threading.Lock()
_quotes_cache: dict[str | None, tuple[float, list]] = {}
_QUOTES_TTL = 30.0


@router.get("/quotes")
def quotes(market: str | None = Query(default=None)):
    """Latest price + day/month change for every ticker — the market list."""
    with _quotes_lock:
        hit = _quotes_cache.get(market)
        if hit and (time.time() - hit[0] < _QUOTES_TTL):
            return hit[1]

    df = store.latest_quotes(market=market)
    out = []
    for r in df.itertuples(index=False):
        close = _f(r.close)
        prev = _f(r.prev_close)
        m1 = _f(r.close_1m)
        change = (close - prev) if (close is not None and prev) else None
        change_pct = (change / prev * 100.0) if (change is not None and prev) else None
        change_1m = ((close - m1) / m1 * 100.0) if (close is not None and m1) else None
        out.append(
            {
                "ticker": r.ticker,
                "name": r.name,
                "sector": r.sector,
                "date": r.date.strftime("%Y-%m-%d") if r.date is not None else None,
                "close": close,
                "volume": _f(r.volume),
                "change": change,
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "change_1m_pct": round(change_1m, 2) if change_1m is not None else None,
            }
        )
    with _quotes_lock:
        _quotes_cache[market] = (time.time(), out)
    return out


@router.get("/live")
def live(market: str | None = Query(default=None), force: bool = Query(default=False)):
    """Current market snapshot (price/change/volume) for every ticker, polled live.

    Sourced from FinanceDataReader and cached ~10s. Delayed/EOD data — not
    tick-level streaming (that needs a brokerage API).
    """
    try:
        ts, rows = feed.live_quotes(force=force)
    except Exception as e:  # upstream unreachable and no cache
        raise HTTPException(503, f"라이브 시세 소스에 연결할 수 없습니다: {e}")
    if market:
        rows = [r for r in rows if r["sector"] == market]
    return {
        "ts": ts,
        "as_of": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
        "stale_sec": round(time.time() - ts, 1),
        "count": len(rows),
        "quotes": rows,
    }


@router.get("/screen-table")
def screen_table():
    """Spreadsheet grid: price-derived factors for every ticker (cached)."""
    return store.screen_table_prices()


@router.get("/ohlc")
def ohlc(
    ticker: str = Query(..., description="single ticker"),
    start: str | None = None,
    end: str | None = None,
):
    """OHLCV history for one ticker — feeds the candlestick + volume chart."""
    df = store.ohlc(ticker, start=start, end=end)
    if df.empty:
        return {"ticker": ticker, "dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
    return {
        "ticker": ticker,
        "dates": [d.strftime("%Y-%m-%d") for d in df["date"]],
        "open": [_f(v) for v in df["open"]],
        "high": [_f(v) for v in df["high"]],
        "low": [_f(v) for v in df["low"]],
        "close": [_f(v) for v in df["close"]],
        "volume": [_f(v) for v in df["volume"]],
    }
