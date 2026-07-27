"""Business logic for the prices domain.

Holds everything that is *decision*, not *I/O* or *transport*: computing
day/month change, reshaping wide frames into API payloads, and the short-TTL
cache in front of the full-board quote scan. Depends on the repository (data)
and the live feed (external) — never on FastAPI.
"""
from __future__ import annotations

import time

from app.core.cache import TTLCache
from app.core.errors import UpstreamError
from app.core.numeric import json_float as _f
from . import feed

from .repository import PricesRepository
from .schemas import LiveResponse, OHLCResponse, PricesResponse, QuoteRow

# The full-board quote scan only moves on the price scheduler's cadence, so a
# short TTL absorbs frontend polling without ever serving stale numbers.
_QUOTES_TTL = 30.0


class PricesService:
    def __init__(self, repo: PricesRepository) -> None:
        self._repo = repo
        self._quotes_cache = TTLCache(ttl=_QUOTES_TTL)

    # -- pass-through reference data (dynamic column sets) --------------------
    def coverage(self) -> list[dict]:
        return self._repo.coverage().to_dict(orient="records")

    def securities(self, market: str | None) -> list[dict]:
        return self._repo.list_securities(market).to_dict(orient="records")

    def screen_table(self) -> list[dict]:
        return self._repo.screen_table()

    # -- shaped, typed payloads ---------------------------------------------
    def prices(
        self,
        tickers: list[str],
        market: str | None,
        start: str | None,
        end: str | None,
        field: str,
    ) -> PricesResponse:
        wide = self._repo.load_prices(tickers, market, start, end, field)
        if wide.empty:
            return PricesResponse(dates=[], series={})
        return PricesResponse(
            dates=[d.strftime("%Y-%m-%d") for d in wide.index],
            series={
                col: [None if v != v else round(float(v), 4) for v in wide[col]]
                for col in wide.columns
            },
        )

    def quotes(self, market: str | None) -> list[QuoteRow]:
        cached = self._quotes_cache.get(market)
        if cached is not None:
            return cached

        df = self._repo.latest_quotes(market)
        out: list[QuoteRow] = []
        for r in df.itertuples(index=False):
            close = _f(r.close)
            prev = _f(r.prev_close)
            m1 = _f(r.close_1m)
            change = (close - prev) if (close is not None and prev) else None
            change_pct = (change / prev * 100.0) if (change is not None and prev) else None
            change_1m = ((close - m1) / m1 * 100.0) if (close is not None and m1) else None
            out.append(
                QuoteRow(
                    ticker=r.ticker,
                    name=r.name,
                    sector=r.sector,
                    date=r.date.strftime("%Y-%m-%d") if r.date is not None else None,
                    close=close,
                    volume=_f(r.volume),
                    change=change,
                    change_pct=round(change_pct, 2) if change_pct is not None else None,
                    change_1m_pct=round(change_1m, 2) if change_1m is not None else None,
                )
            )
        return self._quotes_cache.set(market, out)

    def live(self, market: str | None, force: bool) -> LiveResponse:
        try:
            ts, rows = feed.live_quotes(force=force)
        except Exception as e:  # upstream unreachable and no cache
            raise UpstreamError(f"라이브 시세 소스에 연결할 수 없습니다: {e}")
        if market:
            rows = [r for r in rows if r["sector"] == market]
        return LiveResponse(
            ts=ts,
            as_of=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
            stale_sec=round(time.time() - ts, 1),
            count=len(rows),
            quotes=rows,
        )

    def ohlc(self, ticker: str, start: str | None, end: str | None) -> OHLCResponse:
        df = self._repo.ohlc(ticker, start, end)
        if df.empty:
            return OHLCResponse(
                ticker=ticker, dates=[], open=[], high=[], low=[], close=[], volume=[]
            )
        return OHLCResponse(
            ticker=ticker,
            dates=[d.strftime("%Y-%m-%d") for d in df["date"]],
            open=[_f(v) for v in df["open"]],
            high=[_f(v) for v in df["high"]],
            low=[_f(v) for v in df["low"]],
            close=[_f(v) for v in df["close"]],
            volume=[_f(v) for v in df["volume"]],
        )
