"""Watchlist HTTP routes — thin transport layer.

Each handler only: reads/validates params, delegates to the injected
``WatchlistService``, and returns the payload unchanged. Paths, params and
docstrings are verbatim from the legacy ``/api/data`` router so this is a
drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.auth import require_auth

from .deps import get_watchlist_service
from .service import WatchlistService

router = APIRouter(prefix="/api/data", tags=["watchlist"])

Svc = Depends(get_watchlist_service)


@router.get("/watchlist")
def watchlist_get(user: str = Depends(require_auth), svc: WatchlistService = Svc):
    """관심종목 — 현재가·매매신호·목표가 상승여력 포함."""
    return svc.get_watch(user)


@router.post("/watchlist/add")
def watchlist_add(
    ticker: str = Query(...),
    user: str = Depends(require_auth),
    svc: WatchlistService = Svc,
):
    return svc.add_watch(user, ticker)


@router.post("/watchlist/remove")
def watchlist_remove(
    ticker: str = Query(...),
    user: str = Depends(require_auth),
    svc: WatchlistService = Svc,
):
    return svc.remove_watch(user, ticker)


@router.get("/portfolio")
def portfolio_get(user: str = Depends(require_auth), svc: WatchlistService = Svc):
    """보유 포트폴리오 진단 — 손익·비중·집중도·신호."""
    return svc.diagnose(user)


@router.post("/portfolio")
def portfolio_set(
    holdings: list[dict] = Body(...),
    user: str = Depends(require_auth),
    svc: WatchlistService = Svc,
):
    """보유 종목 전체 교체 [{ticker, qty, avg}] → 진단 반환."""
    return svc.set_holdings(user, holdings)
