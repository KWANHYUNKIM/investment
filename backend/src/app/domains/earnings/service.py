"""Business logic for the earnings domain.

The legacy endpoints are pure delegations to the ``app.data.market`` board
builders and the delisting scheduler's status probe, so the service simply
preserves those calls. The imports stay *lazy inside each method* on purpose —
exactly as in the legacy router — so importing the domain never triggers the
heavy board modules (pandas frames, DuckDB touches) at app startup.
"""
from __future__ import annotations


class EarningsService:
    def kospi_earnings(self):
        from . import earnings

        return earnings.board()

    def delisting_risk(self):
        from app.data.market import delisting

        return delisting.board()

    def delisting_batch_status(self):
        from app.data.schedulers import delisting_scheduler

        return delisting_scheduler.status()

    def earnings_quality(self):
        from . import earnings_quality

        return earnings_quality.board()
