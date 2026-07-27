"""Watchlist / portfolio endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.auth import require_auth

from app.data.market import watchlist

router = APIRouter()


@router.get("/watchlist")
def watchlist_get(user: str = Depends(require_auth)):
    """관심종목 — 현재가·매매신호·목표가 상승여력 포함."""
    return watchlist.get_watch(user)


@router.post("/watchlist/add")
def watchlist_add(ticker: str = Query(...), user: str = Depends(require_auth)):
    return watchlist.add_watch(user, ticker)


@router.post("/watchlist/remove")
def watchlist_remove(ticker: str = Query(...), user: str = Depends(require_auth)):
    return watchlist.remove_watch(user, ticker)


@router.get("/portfolio")
def portfolio_get(user: str = Depends(require_auth)):
    """보유 포트폴리오 진단 — 손익·비중·집중도·신호."""
    return watchlist.diagnose(user)


@router.post("/portfolio")
def portfolio_set(holdings: list[dict] = Body(...), user: str = Depends(require_auth)):
    """보유 종목 전체 교체 [{ticker, qty, avg}] → 진단 반환."""
    return watchlist.set_holdings(user, holdings)
