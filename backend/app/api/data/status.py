"""Background scheduler / crawler status endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.data.fundamentals import fundamentals_crawler
from app.data.schedulers import price_scheduler
from app.data.schedulers import report_scheduler

router = APIRouter()


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
