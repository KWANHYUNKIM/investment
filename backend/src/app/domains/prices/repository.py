"""Data-access layer for the prices domain.

The repository is the *seam* between the domain and the physical store: it is the
only place in the domain that knows ``app.data.infra.store`` (DuckDB) exists.
Today it wraps the legacy module-level ``store`` functions; when ``store`` later
moves under ``app/infra/db``, only this file changes — service/router don't.

Methods return raw pandas frames / primitive structures; shaping into response
schemas is the service's job, not the repository's.
"""
from __future__ import annotations

import pandas as pd

from app.data.infra import store


class PricesRepository:
    def coverage(self) -> pd.DataFrame:
        return store.coverage()

    def list_securities(self, market: str | None) -> pd.DataFrame:
        return store.list_securities(market=market)

    def load_prices(
        self,
        tickers: list[str],
        market: str | None,
        start: str | None,
        end: str | None,
        field: str,
    ) -> pd.DataFrame:
        return store.load_prices(
            tickers=tickers, market=market, start=start, end=end, field=field
        )

    def latest_quotes(self, market: str | None) -> pd.DataFrame:
        return store.latest_quotes(market=market)

    def screen_table(self) -> list[dict]:
        return store.screen_table_prices()

    def ohlc(self, ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
        return store.ohlc(ticker, start=start, end=end)
