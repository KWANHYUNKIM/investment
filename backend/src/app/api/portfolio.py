"""Portfolio construction endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.data.infra import store
from app.models.schemas import PortfolioRequest
from app.quant import metrics, portfolio

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.post("")
def build(req: PortfolioRequest):
    prices = store.load_prices(
        tickers=req.tickers, market=req.market, start=req.start, end=req.end
    )
    if prices.empty:
        raise HTTPException(404, "no price data for those tickers/date range")

    settings = get_settings()
    try:
        weights = portfolio.build_weights(
            prices, scheme=req.scheme, risk_free=settings.risk_free_rate
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Report the in-sample risk/return of the proposed allocation.
    rets = prices.pct_change().dropna(how="all")
    aligned_w = weights.reindex(rets.columns).fillna(0.0)
    port_rets = (rets[aligned_w.index] * aligned_w).sum(axis=1)

    return {
        "scheme": req.scheme,
        "weights": {k: round(float(v), 4) for k, v in weights.items() if v > 1e-6},
        "metrics": metrics.summary(port_rets, settings.risk_free_rate),
    }
