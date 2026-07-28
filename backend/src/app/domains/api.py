"""Aggregate router for all migrated domains.

Each domain package (``app/domains/<name>``) owns a self-prefixed
``APIRouter(prefix="/api/data", tags=[<name>])``. This module collects them into
one ``domain_router`` that ``app.main`` mounts under the shared auth dependency —
so wiring a new domain is a one-line addition here, not a change to ``main``.

The strangler-fig migration of the old monolithic ``app/api/data`` router is
complete: every endpoint now lives in a layered domain (router→service→
repository→schemas).
"""
from __future__ import annotations

from fastapi import APIRouter

from app.domains.archive import router as archive_router
from app.domains.budget import router as budget_router
from app.domains.costmodel import router as costmodel_router
from app.domains.dividends import router as dividends_router
from app.domains.earnings import router as earnings_router
from app.domains.fundamentals import router as fundamentals_router
from app.domains.global_map import router as global_map_router
from app.domains.income import router as income_router
from app.domains.industry import router as industry_router
from app.domains.macro import router as macro_router
from app.domains.market import router as market_router
from app.domains.prices import router as prices_router
from app.domains.report import router as report_router
from app.domains.status import router as status_router
from app.domains.themes import router as themes_router
from app.domains.watchlist import router as watchlist_router
from app.domains.wealth import router as wealth_router

domain_router = APIRouter()

for _r in (
    prices_router,
    status_router,
    fundamentals_router,
    global_map_router,
    market_router,
    watchlist_router,
    dividends_router,
    earnings_router,
    budget_router,
    income_router,
    wealth_router,
    macro_router,
    themes_router,
    archive_router,
    industry_router,
    report_router,
    costmodel_router,
):
    domain_router.include_router(_r)
