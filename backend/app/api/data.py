"""Data / reference endpoints: what's in the store."""
from __future__ import annotations

import math
import time

from fastapi import APIRouter, HTTPException, Query

from app.data import (
    asset_detail,
    crossasset,
    daily_archive,
    dart,
    feed,
    fundamentals_crawler,
    industry,
    industry_research,
    industry_scheduler,
    investor,
    market_report,
    news,
    price_scheduler,
    report,
    report_scheduler,
    store,
)

router = APIRouter(prefix="/api/data", tags=["data"])


def _f(v) -> float | None:
    """JSON-safe float (None for NaN/null)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


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


@router.get("/quotes")
def quotes(market: str | None = Query(default=None)):
    """Latest price + day/month change for every ticker — the market list."""
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


@router.get("/crawler-status")
def crawler_status():
    """Background crawler progress (fundamentals + investor flow)."""
    return fundamentals_crawler.status()


@router.get("/price-scheduler-status")
def price_scheduler_status():
    """Background price scheduler progress (daily OHLCV bars → DuckDB)."""
    return price_scheduler.status()


@router.get("/report-scheduler-status")
def report_scheduler_status():
    """Background daily-report snapshotter progress (one JSON per trading day)."""
    return report_scheduler.status()


@router.get("/investor-flow")
def investor_flow_endpoint(
    ticker: str = Query(..., description="single ticker"),
    days: int = Query(default=60, ge=1, le=400),
):
    """Accumulated daily investor net-buy history (DB) + cumulative sums.

    Grows over time as the background crawler stores new days (dedup by date),
    beyond Naver's ~10-day live window.
    """
    hist = store.investor_flow_history(ticker, days=days)
    rows = []
    cum = {"individual": 0.0, "foreigner": 0.0, "organ": 0.0}
    for r in hist.to_dict("records"):
        ind, frg, org = _f(r.get("individual")), _f(r.get("foreigner")), _f(r.get("organ"))
        cum["individual"] += ind or 0
        cum["foreigner"] += frg or 0
        cum["organ"] += org or 0
        rows.append(
            {
                "date": str(r.get("date"))[:10],
                "individual": ind,
                "foreign": frg,
                "organ": org,
                "foreign_ratio": _f(r.get("foreign_ratio")),
            }
        )
    return {
        "ticker": ticker,
        "days_stored": len(rows),
        "cumulative": {"individual": cum["individual"], "foreign": cum["foreigner"], "organ": cum["organ"]},
        "rows": rows,
    }


@router.get("/fundamentals")
def fundamentals_endpoint(ticker: str = Query(..., description="single ticker")):
    """Latest fundamentals snapshot + change (Δ) vs the previous stored snapshot."""
    hist = store.fundamentals_history(ticker)
    fields = ["per", "pbr", "eps", "bps", "roe", "div_yield", "market_cap", "foreign_ratio"]
    if hist.empty:
        return {"ticker": ticker, "latest": None, "prev": None, "change": None, "history": []}

    def clean(rec: dict) -> dict:
        out = {"date": str(rec.get("date"))[:10]}
        for f in fields:
            out[f] = _f(rec.get(f))
        return out

    recs = [clean(r) for r in hist.to_dict("records")]
    latest = recs[-1]
    prev = recs[-2] if len(recs) >= 2 else None
    change = None
    if prev:
        change = {
            f: round(latest[f] - prev[f], 2) if (latest[f] is not None and prev[f] is not None) else None
            for f in fields
        }
    return {"ticker": ticker, "latest": latest, "prev": prev, "change": change, "history": recs[-30:]}


@router.get("/investors")
def investors_endpoint(ticker: str = Query(..., description="single ticker")):
    """Recent investor net-buy trend (개인/외국인/기관) + foreign holding ratio."""
    return {"ticker": ticker, "rows": investor.investors(ticker)}


@router.get("/holders")
def holders_endpoint(ticker: str = Query(..., description="single ticker")):
    """5%+ major holders by name (via DART 대량보유 공시)."""
    return {"ticker": ticker, **dart.major_holders(ticker)}


@router.get("/cross-asset")
def cross_asset_endpoint():
    """Live cross-asset money-flow snapshot (미국·글로벌 증시 · 금 · 비트코인 · 환율).

    Grouped asset quotes + a risk-on/risk-off read. Cached ~60s so frontend
    polling refreshes without hammering the upstream (FinanceDataReader).
    """
    return crossasset.cross_asset()


@router.get("/asset-detail")
def asset_detail_endpoint(key: str = Query(..., description="cross-asset key, e.g. sp500/nasdaq/kospi/gold/btc")):
    """장 마감 상세: 해당 지수/자산의 OHLC 세션 + 최근 시세 + 52주 고저 (+ 구성종목)."""
    data = asset_detail.asset_detail(key)
    if data is None:
        raise HTTPException(404, f"'{key}' 자산 상세를 불러올 수 없습니다.")
    return data


@router.get("/asset-quotes")
def asset_quotes_endpoint(symbols: str = Query(..., description="comma-separated constituent symbols (max 60)")):
    """Batch quotes (현재가·등락·기간수익률) for index constituents — fills the grid lazily."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    return {"quotes": asset_detail.constituent_quotes(syms)}


@router.get("/market-report")
def market_report_endpoint():
    """Market-wide daily report: movers, most-traded, investor sellers, news."""
    return market_report.market_report()


@router.get("/daily-archive/dates")
def daily_archive_dates():
    """Archived daily-report dates (newest first) + snapshotter status."""
    return {"dates": daily_archive.list_dates(), "scheduler": report_scheduler.status()}


@router.get("/daily-archive")
def daily_archive_endpoint(
    date: str | None = Query(default=None, description="YYYY-MM-DD; omit for the latest"),
):
    """A persisted daily report (full market + per-stock + macro).

    Falls back to building today's report on the fly if it isn't saved yet, so a
    fresh install still returns something before the first scheduled snapshot.
    """
    if date is None:
        dates = daily_archive.list_dates()
        if dates:
            return daily_archive.load(dates[0])
        return daily_archive.build()
    data = daily_archive.load(date)
    if data is None:
        raise HTTPException(404, f"{date} 데일리 리포트가 저장되어 있지 않습니다.")
    return data


@router.post("/daily-archive/snapshot")
def daily_archive_snapshot(force: bool = Query(default=False)):
    """Build and persist today's report now (manual trigger). `force` rebuilds."""
    return daily_archive.snapshot(force=force)


# --------------------------------------------------------------------------- #
# Industry / competition map
# --------------------------------------------------------------------------- #
@router.get("/industries")
def industries_endpoint(full: bool = Query(default=False)):
    """KOSPI/KOSDAQ companies grouped by KSIC industry (largest cap first).

    `full=false` (default) returns the lightweight index (no members) for the
    left-hand list; `full=true` returns every group with its member companies.
    """
    if full:
        return {"industries": industry.industries()}
    return {
        "industries": industry.industry_names(),
        "scheduler": industry_scheduler.status(),
    }


@router.get("/industry")
def industry_endpoint(name: str = Query(..., description="industry (업종) name")):
    """One industry: member companies (경쟁군) + research feed (기술/M&A/계약/실적/전략)."""
    grp = industry.get_industry(name)
    if grp is None:
        raise HTTPException(404, f"'{name}' 업종을 찾을 수 없습니다.")
    research = industry_research.research_industry(name)
    return {"group": grp, "research": research}


@router.get("/industry-scheduler-status")
def industry_scheduler_status():
    """Background industry map scheduler progress."""
    return industry_scheduler.status()


@router.post("/industry/refresh")
def industry_refresh(snapshot: bool = Query(default=False)):
    """Refresh industry profiles now; optionally also build today's snapshot."""
    n = industry.refresh_profiles()
    out: dict = {"profiles": n}
    if snapshot:
        out["snapshot"] = industry_research.snapshot(force=True)
    return out


@router.get("/report")
def report_endpoint(
    ticker: str = Query(..., description="single ticker"),
    name: str | None = Query(default=None),
):
    """Post-market daily report: price move + investor flow + news + summary."""
    return report.daily_report(ticker, name)


@router.get("/news")
def news_endpoint(
    name: str = Query(..., description="company name to search news for"),
    limit: int = Query(default=15, ge=1, le=30),
):
    """Domestic (KR) + global (EN) news for a stock, newest first. Cached ~5min."""
    return news.news_for(name, limit=limit)


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
