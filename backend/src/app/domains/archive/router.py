"""Archive HTTP routes — thin transport layer.

Each handler only: reads/validates query params, delegates to the injected
``ArchiveService``, and returns the payload. No business logic. Paths are
unchanged from the legacy ``/api/data`` router so this is a drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .deps import get_archive_service
from .service import ArchiveService

router = APIRouter(prefix="/api/data", tags=["archive"])

Svc = Depends(get_archive_service)


@router.get("/daily-archive/dates")
def daily_archive_dates(svc: ArchiveService = Svc):
    """Archived daily-report dates (newest first) + snapshotter status."""
    return svc.dates()


@router.get("/daily-archive")
def daily_archive_endpoint(
    date: str | None = Query(default=None, description="YYYY-MM-DD; omit for the latest"),
    svc: ArchiveService = Svc,
):
    """A persisted daily report (full market + per-stock + macro).

    Falls back to building today's report on the fly if it isn't saved yet, so a
    fresh install still returns something before the first scheduled snapshot.
    """
    if date is None:
        return svc.latest_or_build()
    data = svc.load(date)
    if data is None:
        raise HTTPException(404, f"{date} 데일리 리포트가 저장되어 있지 않습니다.")
    return data


@router.post("/daily-archive/snapshot")
def daily_archive_snapshot(force: bool = Query(default=False), svc: ArchiveService = Svc):
    """Build and persist today's report now (manual trigger). `force` rebuilds."""
    return svc.snapshot(force=force)
