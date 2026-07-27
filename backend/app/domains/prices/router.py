"""Prices HTTP routes — thin transport layer.

Each handler only: reads/validates query params, delegates to the injected
``PricesService``, and returns a typed response. No business logic, no store
access. Paths are unchanged from the legacy ``/api/data`` router so this is a
drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .deps import get_prices_service
from .schemas import LiveResponse, OHLCResponse, PricesResponse, QuoteRow
from .service import PricesService

router = APIRouter(prefix="/api/data", tags=["prices"])

Svc = Depends(get_prices_service)


@router.get("/coverage")
def coverage(svc: PricesService = Svc):
    """Per-market summary of stored price data — feeds the dashboard."""
    return svc.coverage()


@router.get("/securities")
def securities(market: str | None = Query(default=None), svc: PricesService = Svc):
    return svc.securities(market)


@router.get("/prices", response_model=PricesResponse)
def prices(
    tickers: str = Query(..., description="comma-separated tickers"),
    market: str | None = None,
    start: str | None = None,
    end: str | None = None,
    field: str = "close",
    svc: PricesService = Svc,
):
    tk = [t.strip() for t in tickers.split(",") if t.strip()]
    return svc.prices(tk, market, start, end, field)


@router.get("/quotes", response_model=list[QuoteRow])
def quotes(market: str | None = Query(default=None), svc: PricesService = Svc):
    """Latest price + day/month change for every ticker — the market list."""
    return svc.quotes(market)


@router.get("/live", response_model=LiveResponse)
def live(
    market: str | None = Query(default=None),
    force: bool = Query(default=False),
    svc: PricesService = Svc,
):
    """Current market snapshot (price/change/volume) for every ticker, polled live.

    Sourced from FinanceDataReader and cached ~10s. Delayed/EOD data — not
    tick-level streaming (that needs a brokerage API).
    """
    return svc.live(market, force)


@router.get("/screen-table")
def screen_table(svc: PricesService = Svc):
    """Spreadsheet grid: price-derived factors for every ticker (cached)."""
    return svc.screen_table()


@router.get("/ohlc", response_model=OHLCResponse)
def ohlc(
    ticker: str = Query(..., description="single ticker"),
    start: str | None = None,
    end: str | None = None,
    svc: PricesService = Svc,
):
    """OHLCV history for one ticker — feeds the candlestick + volume chart."""
    return svc.ohlc(ticker, start, end)
