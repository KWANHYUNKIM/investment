"""Daily-report archive endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data.reports import daily_archive
from app.data.schedulers import report_scheduler

router = APIRouter()


@router.get("/daily-archive/dates")
def daily_archive_dates():
    """Archived daily-report dates (newest first) + snapshotter status."""
    return {"dates": daily_archive.list_dates(), "scheduler": report_scheduler.status()}


@router.get("/daily-archive")
def daily_archive_endpoint(
    date: str | None = Query(default=None, description="YYYY-MM-DD; omit for the latest"),
):
    """A persisted daily report (full market + per-stock + macro).

    Falls back to building today's report on the fly if it isn't saved yet, so a
    fresh install still returns something before the first scheduled snapshot.
    """
    if date is None:
        dates = daily_archive.list_dates()
        if dates:
            return daily_archive.load(dates[0])
        return daily_archive.build()
    data = daily_archive.load(date)
    if data is None:
        raise HTTPException(404, f"{date} 데일리 리포트가 저장되어 있지 않습니다.")
    return data


@router.post("/daily-archive/snapshot")
def daily_archive_snapshot(force: bool = Query(default=False)):
    """Build and persist today's report now (manual trigger). `force` rebuilds."""
    return daily_archive.snapshot(force=force)
