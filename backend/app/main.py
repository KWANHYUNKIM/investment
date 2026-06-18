"""FastAPI application entry point.

Run from the backend/ directory:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import backtest, data, portfolio, screening
from app.core.config import get_settings
from app.data import fundamentals_crawler, industry_scheduler, price_scheduler, report_scheduler, store

settings = get_settings()

app = FastAPI(
    title="Quant Investment API",
    version="0.1.0",
    description="Screening · Backtesting · Portfolio construction for KR/US equities",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    store.init_db()
    # Background fundamentals crawler (same process → shares the DuckDB writer,
    # no lock conflicts). Stores a snapshot only when values change.
    fundamentals_crawler.start()
    # Background price scheduler: periodically accumulate today's OHLCV bar for
    # the whole KR board into DuckDB (same process → same writer connection).
    price_scheduler.start()
    # Background report scheduler: persist the full daily report as JSON once per
    # trading day so the 데일리 리포트 history accumulates instead of evaporating.
    report_scheduler.start()
    # Background industry scheduler: refresh KRX-DESC industry profiles and snapshot
    # the per-industry competition/research feed so it accumulates over time.
    industry_scheduler.start()


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "data_dir": str(settings.data_dir.resolve())}


app.include_router(data.router)
app.include_router(screening.router)
app.include_router(backtest.router)
app.include_router(portfolio.router)
