"""Industry / competitor grouping — the "공통분모" for the competition map.

KRX-DESC (``fdr.StockListing('KRX-DESC')``) is the one source here that carries a
real **industry** classification (KSIC) plus each company's **주요 제품/사업**
(Products) — exactly the axis we group competitors on. We enrich it with market
cap + today's move from the board listings, persist it to DuckDB, and expose it
grouped by industry (largest first), so every KOSPI/KOSDAQ name lands next to its
peers.
"""
from __future__ import annotations

import threading
import time

import pandas as pd
import FinanceDataReader as fdr

from app.data import store
from app.data import naver_sector

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 1800.0  # 30 min for the grouped view


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _marcap_map() -> dict[str, float]:
    """ticker -> market cap (KRW), from the KOSPI + KOSDAQ board listings."""
    out: dict[str, float] = {}
    for board in ("KOSPI", "KOSDAQ"):
        try:
            df = fdr.StockListing(board)
        except Exception:
            continue
        for r in df.itertuples(index=False):
            code = getattr(r, "Code", None)
            mc = _num(getattr(r, "Marcap", None))
            if code and mc:
                out[str(code)] = mc
    return out


def refresh_profiles() -> int:
    """Fetch KRX-DESC industry/products, enrich with marcap + WICS 업종, upsert."""
    desc = fdr.StockListing("KRX-DESC")
    marcap = _marcap_map()
    wics = naver_sector.sector_map()  # ticker -> WICS 업종 (네이버 금융)

    rows: list[dict] = []
    for r in desc.itertuples(index=False):
        code = getattr(r, "Code", None)
        market = getattr(r, "Market", None)
        if not code or market not in ("KOSPI", "KOSDAQ"):
            continue
        ticker = str(code)
        rows.append(
            {
                "market": "KR",
                "ticker": ticker,
                "name": getattr(r, "Name", None),
                "industry": (getattr(r, "Industry", None) or "기타"),
                "wics_sector": wics.get(ticker),
                "products": getattr(r, "Products", None),
                "region": getattr(r, "Region", None),
                "representative": getattr(r, "Representative", None),
                "homepage": getattr(r, "HomePage", None),
                "listing_date": str(getattr(r, "ListingDate", "") or "")[:10] or None,
                "market_cap": marcap.get(ticker),
            }
        )
    if not rows:
        return 0
    n = store.upsert_company_profile(pd.DataFrame(rows))
    with _lock:
        _cache["data"] = None  # invalidate grouped view
    return n


def _moves() -> dict[str, dict]:
    """ticker -> {change_pct, close} from the price-derived grid (cached)."""
    out: dict[str, dict] = {}
    try:
        for r in store.screen_table_prices():
            out[r["ticker"]] = {"change_pct": r.get("change_pct"), "close": r.get("close")}
    except Exception:
        pass
    return out


def industries(min_members: int = 2) -> list[dict]:
    """Companies grouped by WICS 업종 (네이버 금융), largest-cap industries first.

    WICS is the revenue-based classification 네이버·증권사 use, so competitors land
    together. Names without a WICS 업종 (newly listed, scrape miss) fall back to
    their KSIC industry, then "기타".

    Each group: {industry, count, market_cap (sum), avg_change_pct, members:[...]}.
    Members carry name/ticker/products/market_cap/change_pct, sorted by cap.
    """
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    prof = store.company_profiles()
    moves = _moves()
    groups: dict[str, list[dict]] = {}
    for rec in prof.to_dict("records"):
        ind = rec.get("wics_sector") or rec.get("industry") or "기타"
        mv = moves.get(rec["ticker"], {})
        groups.setdefault(ind, []).append(
            {
                "ticker": rec["ticker"],
                "name": rec.get("name"),
                "products": rec.get("products"),
                "region": rec.get("region"),
                "representative": rec.get("representative"),
                "homepage": rec.get("homepage"),
                "market_cap": _num(rec.get("market_cap")),
                "change_pct": mv.get("change_pct"),
            }
        )

    out: list[dict] = []
    for ind, members in groups.items():
        if len(members) < min_members:
            continue
        members.sort(key=lambda m: (m["market_cap"] or 0), reverse=True)
        caps = [m["market_cap"] for m in members if m["market_cap"]]
        chgs = [m["change_pct"] for m in members if m["change_pct"] is not None]
        out.append(
            {
                "industry": ind,
                "count": len(members),
                "market_cap": sum(caps) if caps else 0.0,
                "avg_change_pct": round(sum(chgs) / len(chgs), 2) if chgs else None,
                "leader": members[0]["name"],
                "members": members,
            }
        )
    out.sort(key=lambda g: g["market_cap"], reverse=True)

    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = out
    return out


def industry_names() -> list[dict]:
    """Lightweight index: [{industry, count, market_cap, leader}] (no members)."""
    return [
        {k: g[k] for k in ("industry", "count", "market_cap", "avg_change_pct", "leader")}
        for g in industries()
    ]


def get_industry(name: str) -> dict | None:
    for g in industries():
        if g["industry"] == name:
            return g
    return None
