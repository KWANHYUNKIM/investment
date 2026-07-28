"""Business logic for the dividends domain.

There is deliberately almost none: each method delegates to the corresponding
``app.data.market`` business module (which owns caching/data assembly). The only
decision moved here from the legacy router is the ``invest > 0`` portfolio
branch on the royalty board. No store access, so no repository dependency.

NOTE: ``app.data.market.dividends`` (business module) does not clash with this
package ``app.domains.dividends`` — imports are absolute.
"""
from __future__ import annotations

from app.data.market import crisis_survivors as crisis_survivors_data
from app.data.market import dividend_detail as dividend_detail_data
from app.data.market import dividend_etf as dividend_etf_data
from app.data.market import dividend_royalty as dividend_royalty_data
from app.data.market import dividends as dividends_data


class DividendsService:
    def board(self) -> dict:
        return dividends_data.board()

    def stock_universe(self) -> dict:
        return dividends_data.stock_universe()

    def detail(self, ticker: str) -> dict:
        return dividend_detail_data.detail(ticker)

    def royalty_board(self, invest: float) -> dict:
        out = dividend_royalty_data.board()
        if invest > 0:
            out["portfolio"] = dividend_royalty_data.monthly_portfolio(invest)
        return out

    def crisis_survivors(self) -> dict:
        return crisis_survivors_data.board()

    def etf_board(self) -> dict:
        return dividend_etf_data.board()

    def sp_dca(self, monthly: float, years: float, annual_return: float) -> dict:
        return dividend_etf_data.sp_dca(monthly, years, annual_return)
