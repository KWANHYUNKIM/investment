"""Data / reference endpoints: what's in the store.

NOTE: the ``prices`` domain has been migrated to the layered
``app/domains/prices`` package (router→service→repository) and is now wired
directly in ``app.main``. It is intentionally absent here — this legacy
aggregate holds only the not-yet-migrated domains (strangler-fig in progress).
"""
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
    report,
    status,
    themes,
    watchlist,
    wealth,
)

router = APIRouter(prefix="/api/data", tags=["data"])

for _m in (
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
