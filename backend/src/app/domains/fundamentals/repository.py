"""Data-access layer for the fundamentals domain.

The repository is the *seam* between the domain and the physical store: it is the
only place in the domain that knows ``app.data.infra.store`` (DuckDB) exists.
Today it wraps the legacy module-level ``store`` functions; when ``store`` later
moves under ``app/infra/db``, only this file changes — service/router don't.

Methods return raw pandas frames / primitive structures; shaping into response
payloads is the service's job, not the repository's.
"""
from __future__ import annotations

import pandas as pd

from app.data.infra import store


class FundamentalsRepository:
    def investor_flow_history(self, ticker: str, days: int) -> pd.DataFrame:
        return store.investor_flow_history(ticker, days=days)

    def fundamentals_history(self, ticker: str) -> pd.DataFrame:
        return store.fundamentals_history(ticker)

    def dart_latest_bs(self, ticker: str) -> dict:
        return store.dart_latest_bs(ticker)

    def financials_series(self, ticker: str) -> pd.DataFrame:
        return store.financials_series(ticker)

    def dart_financials(self, ticker: str) -> pd.DataFrame:
        return store.dart_financials(ticker)

    def financials_count(self) -> int:
        return store.financials_count()

    def dart_financials_count(self) -> int:
        return store.dart_financials_count()

    def company_profiles(self) -> pd.DataFrame:
        return store.company_profiles()
