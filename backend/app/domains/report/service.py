"""Business logic for the report domain.

Both endpoints are pure delegations to the existing ``app.data`` builders —
``reports.report`` (daily report assembly) and ``news.news`` (KR+EN news with
its own ~5min cache). The service keeps that seam explicit without
reimplementing any of it. Never depends on FastAPI.
"""
from __future__ import annotations

from app.data.news import news
from app.data.reports import report


class ReportService:
    def daily_report(self, ticker: str, name: str | None) -> dict:
        return report.daily_report(ticker, name)

    def news_for(self, name: str, limit: int) -> dict:
        return news.news_for(name, limit=limit)
