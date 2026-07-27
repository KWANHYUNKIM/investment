"""Fundamentals / financial statements / investor endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data.fundamentals import dart
from app.data.fundamentals import dart_financials
from app.data.fundamentals import financials
from app.data.intel import industry
from app.data.market import investor
from app.data.infra import store

from ._common import _SJ_LABEL, _SJ_ORDER, _f

router = APIRouter()


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


@router.get("/investors")
def investors_endpoint(ticker: str = Query(..., description="single ticker")):
    """Recent investor net-buy trend (개인/외국인/기관) + foreign holding ratio."""
    return {"ticker": ticker, "rows": investor.investors(ticker)}


@router.get("/holders")
def holders_endpoint(ticker: str = Query(..., description="single ticker")):
    """5%+ major holders by name (via DART 대량보유 공시)."""
    return {"ticker": ticker, **dart.major_holders(ticker)}
