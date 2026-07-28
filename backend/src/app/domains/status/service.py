"""Business logic for the status domain.

There is deliberately almost none: each method is a straight delegation to the
corresponding ``app.data`` crawler/scheduler singleton's ``status()`` — those
modules own their progress state. No store access, so no repository dependency.
"""
from __future__ import annotations

from app.data.fundamentals import fundamentals_crawler
from app.data.schedulers import price_scheduler
from app.data.schedulers import report_scheduler


class StatusService:
    def crawler_status(self) -> dict:
        return fundamentals_crawler.status()

    def price_scheduler_status(self) -> dict:
        return price_scheduler.status()

    def report_scheduler_status(self) -> dict:
        return report_scheduler.status()
