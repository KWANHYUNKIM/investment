"""Business logic for the market domain.

This domain is an *aggregator*: each method delegates to the same
``app.data.*`` module the legacy ``app/api/data/market.py`` endpoints called,
so behavior is byte-identical. The only logic that lives here is the thin
request shaping the legacy router did inline: splitting the comma-separated
constituent symbol list and turning a ``None`` asset detail into a semantic
404 (``NotFoundError`` — mapped to the same ``{"detail": ...}`` response by
``app.core.errors.install``). Never depends on FastAPI.
"""
from __future__ import annotations

from app.core.errors import NotFoundError

from app.data.market import asset_detail
from app.data.macro import crossasset
from app.data.market import institutional
from app.data.market import premarket
from app.data.market import premarket_archive
from app.data.market import target_price as target_price_mod
from app.data.market import signals as signals_mod
from app.data.market import stock_score
from app.data.market import market_movers
from app.data.market import movers_archive
from app.data.market import briefing
from app.data.news import livepulse
from app.data.macro import moneyflow
from app.data.reports import market_report


class MarketService:
    # -- cross-asset snapshot + per-asset drilldown ---------------------------
    def cross_asset(self) -> dict:
        return crossasset.cross_asset()

    def asset_detail(self, key: str, date: str | None) -> dict:
        data = asset_detail.asset_detail(key, as_of=date)
        if data is None:
            raise NotFoundError(f"'{key}' 자산 상세를 불러올 수 없습니다.")
        return data

    def asset_quotes(self, symbols: str, date: str | None) -> dict:
        syms = [s.strip() for s in symbols.split(",") if s.strip()]
        return {"quotes": asset_detail.constituent_quotes(syms, as_of=date)}

    # -- market-wide reads ----------------------------------------------------
    def market_report(self) -> dict:
        return market_report.market_report()

    def live_pulse(self) -> dict:
        return livepulse.pulse()

    def institutional(self) -> dict:
        return institutional.track()

    def money_flow(self) -> dict:
        return moneyflow.pulse()

    # -- premarket forecast + scorecard ---------------------------------------
    def premarket(self) -> dict:
        return premarket.forecast()

    def premarket_history(self, limit: int) -> dict:
        return premarket_archive.history(limit=limit)

    # -- per-ticker analytics -------------------------------------------------
    def target_price(self, ticker: str) -> dict:
        return target_price_mod.target_price(ticker)

    def signals(self, ticker: str) -> dict:
        return signals_mod.signals(ticker)

    def stock_score(self) -> dict:
        return stock_score.screen()

    # -- briefing + movers (auth-gated in the router) -------------------------
    def briefing(self, market: str) -> dict:
        return briefing.briefing(market)

    def movers(self, refresh: bool) -> dict:
        return market_movers.snapshot(force=refresh)

    def movers_history(self, limit: int) -> dict:
        return {"items": movers_archive.recent(limit)}
