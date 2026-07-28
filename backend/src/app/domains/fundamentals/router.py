"""Fundamentals HTTP routes — thin transport layer.

Each handler only: reads/validates query params, delegates to the injected
``FundamentalsService``, and returns the payload. No business logic, no store
access. Paths are unchanged from the legacy ``/api/data`` router so this is a
drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .deps import get_fundamentals_service
from .service import FundamentalsService

router = APIRouter(prefix="/api/data", tags=["fundamentals"])

Svc = Depends(get_fundamentals_service)


@router.get("/investor-flow")
def investor_flow_endpoint(
    ticker: str = Query(..., description="single ticker"),
    days: int = Query(default=60, ge=1, le=400),
    svc: FundamentalsService = Svc,
):
    """Accumulated daily investor net-buy history (DB) + cumulative sums.

    Grows over time as the background crawler stores new days (dedup by date),
    beyond Naver's ~10-day live window.
    """
    return svc.investor_flow(ticker, days)


@router.get("/fundamentals")
def fundamentals_endpoint(
    ticker: str = Query(..., description="single ticker"),
    svc: FundamentalsService = Svc,
):
    """Latest fundamentals snapshot + change (Δ) vs the previous stored snapshot."""
    return svc.fundamentals(ticker)


@router.get("/financials")
def financials_endpoint(
    ticker: str = Query(..., description="single ticker"),
    svc: FundamentalsService = Svc,
):
    """기업실적분석 — 연도별 매출/영업이익/당기순이익/영업이익률 (coinfo 표)."""
    return svc.financials(ticker)


@router.post("/financials/refresh")
def financials_refresh(
    limit: int = Query(default=0, ge=0, le=4000),
    svc: FundamentalsService = Svc,
):
    """Bulk-scrape 기업실적분석 for the whole board (또는 limit개) into DuckDB."""
    return svc.financials_refresh(limit)


@router.get("/dart-financials")
def dart_financials_endpoint(
    ticker: str = Query(..., description="single ticker"),
    svc: FundamentalsService = Svc,
):
    """DART 전 계정 재무제표 — 재무상태표/손익계산서/현금흐름표 전체, 연도별(원).

    표(statement)별로 계정을 보고서 순서대로, 각 계정은 연도→금액 맵으로 돌려준다.
    저장돼 있지 않으면 처음 볼 때 DART에서 즉석으로 받아 적재한다.
    """
    return svc.dart_financials(ticker)


@router.post("/dart-financials/refresh")
def dart_financials_refresh(
    limit: int = Query(default=0, ge=0, le=4000),
    skip_existing: bool = Query(default=True),
    svc: FundamentalsService = Svc,
):
    """Bulk-fetch DART 전체 재무제표 for the board (또는 limit개) into DuckDB."""
    return svc.dart_financials_refresh(limit, skip_existing)


@router.get("/investors")
def investors_endpoint(
    ticker: str = Query(..., description="single ticker"),
    svc: FundamentalsService = Svc,
):
    """Recent investor net-buy trend (개인/외국인/기관) + foreign holding ratio."""
    return svc.investors(ticker)


@router.get("/holders")
def holders_endpoint(
    ticker: str = Query(..., description="single ticker"),
    svc: FundamentalsService = Svc,
):
    """5%+ major holders by name (via DART 대량보유 공시)."""
    return svc.holders(ticker)
