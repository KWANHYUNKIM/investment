"""Data / reference endpoints: what's in the store."""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    archive,
    budget,
    costmodel,
    dividends,
    earnings,
    fundamentals,
    global_map,
    income,
    industry,
    macro,
    market,
    prices,
    report,
    status,
    themes,
    watchlist,
    wealth,
)

router = APIRouter(prefix="/api/data", tags=["data"])

for _m in (
    prices,
    status,
    fundamentals,
    global_map,
    market,
    watchlist,
    dividends,
    earnings,
    budget,
    income,
    wealth,
    macro,
    themes,
    archive,
    industry,
    report,
    costmodel,
):
    router.include_router(_m.router)
