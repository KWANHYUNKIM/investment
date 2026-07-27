"""Report HTTP routes — thin transport layer.

Each handler only reads/validates query params and delegates to the injected
``ReportService``. Paths, params, and docstrings are unchanged from the legacy
``/api/data`` router so this is a drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .deps import get_report_service
from .service import ReportService

router = APIRouter(prefix="/api/data", tags=["report"])

Svc = Depends(get_report_service)


@router.get("/report")
def report_endpoint(
    ticker: str = Query(..., description="single ticker"),
    name: str | None = Query(default=None),
    svc: ReportService = Svc,
):
    """Post-market daily report: price move + investor flow + news + summary."""
    return svc.daily_report(ticker, name)


@router.get("/news")
def news_endpoint(
    name: str = Query(..., description="company name to search news for"),
    limit: int = Query(default=15, ge=1, le=30),
    svc: ReportService = Svc,
):
    """Domestic (KR) + global (EN) news for a stock, newest first. Cached ~5min."""
    return svc.news_for(name, limit)
