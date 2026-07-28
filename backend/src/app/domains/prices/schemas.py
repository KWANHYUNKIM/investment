"""Response contracts for the prices domain.

Typed models are applied via ``response_model=`` only on endpoints whose shape we
fully control and stringify ourselves (prices/quotes/ohlc/live envelope). The
genuinely dynamic payloads (coverage/securities/screen-table rows come straight
from DuckDB with a wide, evolving column set) are passed through as ``dict`` on
purpose — a strict model there would silently strip columns the frontend reads.
"""
from __future__ import annotations

from pydantic import BaseModel


class PricesResponse(BaseModel):
    """Wide price matrix: aligned dates + one series per ticker."""

    dates: list[str]
    series: dict[str, list[float | None]]


class QuoteRow(BaseModel):
    """Latest close + day/month change for one ticker (the market list)."""

    ticker: str
    name: str | None = None
    sector: str | None = None
    date: str | None = None
    close: float | None = None
    volume: float | None = None
    change: float | None = None
    change_pct: float | None = None
    change_1m_pct: float | None = None


class LiveResponse(BaseModel):
    """Live snapshot envelope. ``quotes`` stays untyped to preserve the extra
    fields demo/tick mode layers on (price, change, change_pct, …)."""

    ts: float
    as_of: str
    stale_sec: float
    count: int
    quotes: list[dict]


class OHLCResponse(BaseModel):
    """OHLCV history for one ticker — feeds the candlestick + volume chart."""

    ticker: str
    dates: list[str]
    open: list[float | None]
    high: list[float | None]
    low: list[float | None]
    close: list[float | None]
    volume: list[float | None]
