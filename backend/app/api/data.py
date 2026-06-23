"""Data / reference endpoints: what's in the store."""
from __future__ import annotations

import math
import threading
import time

from fastapi import APIRouter, HTTPException, Query

from app.data import (
    asset_detail,
    crossasset,
    daily_archive,
    dart,
    dart_financials,
    feed,
    financials,
    futuretheme,
    growth_scheduler,
    institutional,
    livepulse,
    moneyflow,
    finnhub,
    fundamentals_crawler,
    global_map,
    global_universe,
    industry,
    industry_research,
    industry_scheduler,
    investor,
    korea_flow,
    money_analysis,
    money_supply,
    realeconomy,
    realestate,
    rent,
    ecos,
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
    # 부채비율(총부채/자기자본 %) — 위기 때 취약성. 펀더멘털 스냅샷엔 없으므로
    # DART 재무상태표 최신연도 부채총계/자본총계로 파생해 latest에 붙인다.
    bs = store.dart_latest_bs(ticker)
    debt, equity = _f(bs.get("부채총계")), _f(bs.get("자본총계"))
    latest["debt_ratio"] = round(debt / equity * 100, 1) if (debt is not None and equity) else None
    return {"ticker": ticker, "latest": latest, "prev": prev, "change": change, "history": recs[-30:]}


@router.get("/financials")
def financials_endpoint(ticker: str = Query(..., description="single ticker")):
    """기업실적분석 — 연도별 매출/영업이익/당기순이익/영업이익률 (coinfo 표)."""
    df = store.financials_series(ticker)
    if df.empty:
        financials.get(ticker)  # lazy scrape + persist on first view
        df = store.financials_series(ticker)
    rows = [
        {
            "period": str(r.get("period")),
            "sales": _f(r.get("sales")),
            "op_profit": _f(r.get("op_profit")),
            "net_income": _f(r.get("net_income")),
            "op_margin": _f(r.get("op_margin")),
        }
        for r in df.to_dict("records")
    ]
    return {"ticker": ticker, "rows": rows}


@router.post("/financials/refresh")
def financials_refresh(limit: int = Query(default=0, ge=0, le=4000)):
    """Bulk-scrape 기업실적분석 for the whole board (또는 limit개) into DuckDB."""
    prof = store.company_profiles()
    tickers = [str(t) for t in prof["ticker"].tolist()]
    if limit:
        tickers = tickers[:limit]
    n = financials.refresh_many(tickers)
    industry.invalidate()  # so 영업이익 합계가 즉시 반영
    return {"requested": len(tickers), "stored": n, "total": store.financials_count()}


_SJ_LABEL = {
    "BS": "재무상태표", "IS": "손익계산서", "CIS": "포괄손익계산서",
    "CF": "현금흐름표", "SCE": "자본변동표",
}
_SJ_ORDER = ["BS", "IS", "CIS", "CF", "SCE"]


@router.get("/dart-financials")
def dart_financials_endpoint(ticker: str = Query(..., description="single ticker")):
    """DART 전 계정 재무제표 — 재무상태표/손익계산서/현금흐름표 전체, 연도별(원).

    표(statement)별로 계정을 보고서 순서대로, 각 계정은 연도→금액 맵으로 돌려준다.
    저장돼 있지 않으면 처음 볼 때 DART에서 즉석으로 받아 적재한다.
    """
    df = store.dart_financials(ticker)
    if df.empty:
        dart_financials.get(ticker)  # lazy fetch + persist
        df = store.dart_financials(ticker)
    if df.empty:
        return {"ticker": ticker, "years": [], "statements": [], "available": dart.enabled()}

    years = sorted({int(y) for y in df["year"].tolist()}, reverse=True)
    by_sj: dict[str, dict] = {}
    for rec in df.to_dict("records"):
        sj = rec["sj_div"]
        acc = rec["account_nm"]
        st = by_sj.setdefault(sj, {})
        node = st.setdefault(acc, {"account_nm": acc, "ord": rec.get("ord") or 0, "by_year": {}})
        node["by_year"][str(int(rec["year"]))] = _f(rec.get("amount"))

    statements = []
    for sj in sorted(by_sj.keys(), key=lambda s: _SJ_ORDER.index(s) if s in _SJ_ORDER else 99):
        accounts = sorted(by_sj[sj].values(), key=lambda a: (a["ord"], a["account_nm"]))
        statements.append({"sj_div": sj, "label": _SJ_LABEL.get(sj, sj), "accounts": accounts})

    return {"ticker": ticker, "years": [str(y) for y in years], "statements": statements,
            "available": True}


@router.post("/dart-financials/refresh")
def dart_financials_refresh(limit: int = Query(default=0, ge=0, le=4000),
                            skip_existing: bool = Query(default=True)):
    """Bulk-fetch DART 전체 재무제표 for the board (또는 limit개) into DuckDB."""
    if not dart.enabled():
        raise HTTPException(status_code=400, detail="DART_API_KEY 미설정")
    prof = store.company_profiles()
    tickers = [str(t) for t in prof["ticker"].tolist()]
    if limit:
        tickers = tickers[:limit]
    n = dart_financials.refresh_many(tickers, skip_existing=skip_existing)
    return {"requested": len(tickers), "stored": n, "total": store.dart_financials_count()}


@router.get("/global-clusters")
def global_clusters_endpoint():
    """글로벌 경쟁지도 — 기술/산업 클러스터 요약(한국+해외 합산 시총·평균 영업이익률)."""
    return {"clusters": global_map.index(), "finnhub": finnhub.enabled(),
            "foreign_loaded": store.foreign_fin_count()}


@router.get("/global-cluster")
def global_cluster_endpoint(key: str = Query(..., description="cluster key")):
    """한 클러스터의 전체 경쟁사(한국+해외) — 시총(USD)·영업이익률·등락률 비교."""
    c = global_map.get(key)
    if not c:
        raise HTTPException(status_code=404, detail="해당 클러스터 없음")
    return c


@router.post("/global-clusters/refresh")
def global_clusters_refresh():
    """해외 경쟁사 펀더멘털(Finnhub)을 일괄 갱신 → 클러스터 캐시 무효화."""
    if not finnhub.enabled():
        raise HTTPException(status_code=400, detail="FINNHUB_API_KEY 미설정")
    n = finnhub.refresh_many(global_universe.all_foreign_symbols())
    global_map.invalidate()
    return {"fetched": n, "foreign_loaded": store.foreign_fin_count()}


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
def asset_detail_endpoint(
    key: str = Query(..., description="cross-asset key, e.g. sp500/nasdaq/kospi/gold/btc"),
    date: str | None = Query(default=None, description="YYYY-MM-DD; 과거 날짜면 그날 장 마감으로 고정"),
):
    """장 마감 상세: 해당 지수/자산의 OHLC 세션 + 최근 시세 + 52주 고저 (+ 구성종목).

    ``date``를 주면 그 날짜까지로 시세를 잘라 그날 마감 시점으로 고정한다.
    """
    data = asset_detail.asset_detail(key, as_of=date)
    if data is None:
        raise HTTPException(404, f"'{key}' 자산 상세를 불러올 수 없습니다.")
    return data


@router.get("/asset-quotes")
def asset_quotes_endpoint(
    symbols: str = Query(..., description="comma-separated constituent symbols (max 60)"),
    date: str | None = Query(default=None, description="YYYY-MM-DD; 과거 날짜면 그날 종가로 고정"),
):
    """Batch quotes (현재가·등락·기간수익률) for index constituents — fills the grid lazily."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    return {"quotes": asset_detail.constituent_quotes(syms, as_of=date)}


@router.get("/market-report")
def market_report_endpoint():
    """Market-wide daily report: movers, most-traded, investor sellers, news."""
    return market_report.market_report()


@router.get("/live-pulse")
def live_pulse_endpoint():
    """실시간 시황 펄스 — 시황·전망·분석 글 취합 → 분위기·드라이버·시간순 흐름. 60초 캐시."""
    return livepulse.pulse()


@router.get("/institutional")
def institutional_endpoint():
    """기관 수급 추적 — 기관이 언제 담고 던졌나(매집/이탈 상위) + 왜 팔았을지 추정."""
    return institutional.track()


@router.get("/money-flow")
def money_flow_endpoint():
    """글로벌 자금 흐름 — 유동성 레짐(완화/긴축)·한국 외국인 vs 국내 수급·크로스에셋·자산군별 자금 뉴스."""
    return moneyflow.pulse()


@router.get("/korea-flow")
def korea_flow_endpoint():
    """한국 경제 흐름 — 부동산/리츠 ETF·국채 ETF 자금 신호 + 부동산·국채 뉴스 동향. 키 불필요."""
    return korea_flow.snapshot()


@router.get("/realestate-trades")
def realestate_trades_endpoint():
    """부동산 실거래 — 서울 25개구 아파트 매매 월별 거래량·거래대금 + 지역별 분포(국토부 RTMS)."""
    return realestate.snapshot()


@router.get("/realestate-rent")
def realestate_rent_endpoint():
    """부동산 전월세 실거래 — 전국 아파트 월별 거래량·전세/월세 비중·평균 전세보증금(국토부 RTMS)."""
    return rent.snapshot()


@router.get("/ecos-macro")
def ecos_macro_endpoint():
    """국내 거시지표 — M2 통화량·가계신용·주택매매가격지수 추이 + 증가율(한국은행 ECOS)."""
    return ecos.snapshot()


@router.get("/money-supply")
def money_supply_endpoint():
    """통화량 장기·국가 비교 — 한국 M2를 과거 위기(IMF·금융위기·코로나)·해외 주요국과 견줌."""
    return money_supply.snapshot()


@router.get("/money-analysis")
def money_analysis_endpoint():
    """통화량 심층분석 — 마샬케이·유통속도·실질통화량·신용/GDP + 돈의 행선지(자산 상관) + 실질금리·NBER 침체."""
    return money_analysis.snapshot()


@router.get("/real-economy")
def real_economy_endpoint():
    """실물경제 — 한국 국민계정(민간소비·설비/건설투자·수출·취업자수) + 세계 비교(물가·소비·투자·수출·경상수지·실업률)."""
    return realeconomy.snapshot()


@router.get("/future-themes")
def future_themes_endpoint():
    """미래 성장테마 요약(좌측 목록) — 메가트렌드별 모멘텀·종목수·하락후보수."""
    return {"themes": futuretheme.index()}


@router.get("/future-theme")
def future_theme_endpoint(key: str = Query(..., description="theme key")):
    """한 테마 상세 — 뉴스 동향(무엇이 구축되나) + 매핑 종목(미래가치 후보 강조)."""
    t = futuretheme.get(key)
    if not t:
        raise HTTPException(404, "해당 테마 없음")
    return t


@router.get("/future-themes/status")
def future_themes_status():
    """미래 성장테마 백그라운드 스케줄러 상태 + 저장된 스냅샷 날짜."""
    return growth_scheduler.status()


@router.get("/future-themes/dates")
def future_themes_dates():
    """누적 저장된 미래 성장테마 스냅샷 날짜(최신순)."""
    return {"dates": futuretheme.list_dates()}


@router.post("/future-themes/refresh")
def future_themes_refresh():
    """미래 성장테마를 지금 즉시 재크롤(뉴스+매핑)하고 스냅샷 저장."""
    futuretheme.themes(force=True)
    return futuretheme.snapshot(force=True)


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
