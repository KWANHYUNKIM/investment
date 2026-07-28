"""Report domain — per-stock daily report and news lookup.

Layered: router (transport) → service (logic) → repository (data sources).
Phase-2 deepened: the daily-report assembly now lives in ``service`` (moved out
of the deleted ``app.data.reports.report``); the repository owns access to the
price store, investor-flow read model, and the news feed.
"""
from .router import router

__all__ = ["router"]
