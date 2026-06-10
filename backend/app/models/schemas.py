"""Pydantic request/response models for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


# --- Screening ---------------------------------------------------------------
class FilterIn(BaseModel):
    factor: str
    min: float | None = None
    max: float | None = None


class FactorWeightIn(BaseModel):
    factor: str
    weight: float = 1.0
    direction: int | None = Field(default=None, description="-1 lower-is-better, +1 higher-is-better")


class ScreenRequest(BaseModel):
    market: str | None = Field(default=None, description="'KR' | 'US' | None for all")
    filters: list[FilterIn] = []
    factors: list[FactorWeightIn] = []
    top_n: int = 30
    as_of: str | None = None


# --- Backtest ----------------------------------------------------------------
class BacktestRequest(BaseModel):
    tickers: list[str]
    market: str | None = None
    start: str | None = None
    end: str | None = None
    scheme: str = "equal"          # equal | inverse_vol | min_variance | max_sharpe
    rebalance: str = "M"           # D | W | M | Q | Y
    cost_bps: float = 10.0
    lookback: int = 252
    benchmark: str | None = Field(default=None, description="ticker to buy-and-hold as benchmark")


# --- Portfolio ---------------------------------------------------------------
class PortfolioRequest(BaseModel):
    tickers: list[str]
    market: str | None = None
    start: str | None = None
    end: str | None = None
    scheme: str = "max_sharpe"
