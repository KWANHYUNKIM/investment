"""Per-stock daily report / news endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.data.news import news
from app.data.reports import report

router = APIRouter()


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
