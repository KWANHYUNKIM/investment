"""Data-access layer for the report domain.

The only place in the domain that reaches the physical data sources: the DuckDB
``store`` (price history) plus the two shared read models the daily report is
stitched from — investor-flow rows and the KR/EN news feed. Keeping them behind
one repository means the service composes a report without knowing where each
piece comes from.
"""
from __future__ import annotations

import pandas as pd

from app.data.infra import store
from app.data.market import investor
from app.data.news import news


class ReportRepository:
    def ohlc(self, ticker: str) -> pd.DataFrame:
        return store.ohlc(ticker)

    def investor_flow(self, ticker: str) -> list[dict]:
        """Recent investor net-buy rows (newest first); ``[]`` on any source error."""
        try:
            return investor.investors(ticker) or []
        except Exception:
            return []

    def news(self, name: str, limit: int) -> dict:
        return news.news_for(name, limit=limit)
