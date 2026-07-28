"""Business logic for the archive domain.

Thin by design: the heavy lifting (building, persisting, and loading daily
reports; scheduler status) already lives in ``app.data.reports.daily_archive``
and ``app.data.schedulers.report_scheduler``. The service delegates to those
same functions so behavior is identical to the legacy router — it only owns
the *decisions* (latest-date fallback, build-on-miss) and never touches
FastAPI.
"""
from __future__ import annotations

from app.data.reports import daily_archive
from app.data.schedulers import report_scheduler


class ArchiveService:
    def dates(self) -> dict:
        return {"dates": daily_archive.list_dates(), "scheduler": report_scheduler.status()}

    def latest_or_build(self) -> dict:
        dates = daily_archive.list_dates()
        if dates:
            return daily_archive.load(dates[0])
        return daily_archive.build()

    def load(self, date: str) -> dict | None:
        return daily_archive.load(date)

    def snapshot(self, force: bool) -> dict:
        return daily_archive.snapshot(force=force)
