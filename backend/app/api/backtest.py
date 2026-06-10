"""Backtest endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.data import store
from app.models.schemas import BacktestRequest
from app.quant import backtest as bt

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("")
def run_backtest(req: BacktestRequest):
    prices = store.load_prices(
        tickers=req.tickers, market=req.market, start=req.start, end=req.end
    )
    if prices.empty:
        raise HTTPException(404, "no price data for those tickers/date range")

    settings = get_settings()
    config = bt.BacktestConfig(
        scheme=req.scheme,
        rebalance=req.rebalance,
        cost_bps=req.cost_bps,
        lookback=req.lookback,
        risk_free=settings.risk_free_rate,
    )

    try:
        if req.benchmark:
            bench = store.load_prices(
                tickers=[req.benchmark], market=req.market, start=req.start, end=req.end
            )
            if not bench.empty:
                return bt.with_benchmark(prices, bench[req.benchmark], config)
        return bt.run(prices, config)
    except ValueError as e:
        raise HTTPException(400, str(e))
