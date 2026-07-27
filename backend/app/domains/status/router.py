"""Status HTTP routes — thin transport layer.

Each handler only delegates to the injected ``StatusService``. The payloads are
the crawler/scheduler modules' own progress dicts, passed through untyped.
Paths are unchanged from the legacy ``/api/data`` router so this is a drop-in
migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .deps import get_status_service
from .service import StatusService

router = APIRouter(prefix="/api/data", tags=["status"])

Svc = Depends(get_status_service)


@router.get("/crawler-status")
def crawler_status(svc: StatusService = Svc):
    """Background crawler progress (fundamentals + investor flow)."""
    return svc.crawler_status()


@router.get("/price-scheduler-status")
def price_scheduler_status(svc: StatusService = Svc):
    """Background price scheduler progress (daily OHLCV bars → DuckDB)."""
    return svc.price_scheduler_status()


@router.get("/report-scheduler-status")
def report_scheduler_status(svc: StatusService = Svc):
    """Background daily-report snapshotter progress (one JSON per trading day)."""
    return svc.report_scheduler_status()
