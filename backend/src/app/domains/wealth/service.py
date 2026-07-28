"""Business logic for the wealth domain.

Thin delegation layer: every method forwards to the same
``app.data.market.wealthplan`` / ``app.data.market.picks`` functions the legacy
router called, so behavior is bit-for-bit identical. The only "logic" that
lives here is what the legacy handlers did inline — splitting the raw
holdings body into ``(holdings, horizon)`` before delegating. Never depends
on FastAPI.
"""
from __future__ import annotations

from . import picks, wealthplan


class WealthService:
    # -- 계획/프로필 ----------------------------------------------------------
    def plan(self, user: str) -> dict:
        return wealthplan.get_plan(user)

    def save_profile(self, user: str, profile: dict) -> dict:
        return wealthplan.save_profile(user, profile)

    # -- 보유 상품 ------------------------------------------------------------
    def holdings(self, user: str) -> dict:
        return wealthplan.get_holdings(user)

    def save_holdings(self, user: str, body: dict) -> dict:
        # 레거시 핸들러의 body 분해를 그대로 이관: {holdings:[...], horizon:int}
        return wealthplan.save_holdings(user, body.get("holdings", []), body.get("horizon", 10))

    # -- 시뮬레이션 -----------------------------------------------------------
    def loan_sim(self, loan_amount: float, loan_rate: float, loan_years: int,
                 invest_return: float) -> dict:
        return wealthplan.loan_sim(loan_amount, loan_rate, loan_years, invest_return)

    def realty_sim(self, price: float, own_capital: float, loan_rate: float, years: int,
                   appreciation: float, mode: str, deposit: float, rent_monthly: float) -> dict:
        return wealthplan.realty_sim(price, own_capital, loan_rate, years, appreciation,
                                     mode, deposit, rent_monthly)

    def dividend_sim(self, invest: float, yield_pct: float, years: int, growth_pct: float,
                     reinvest: bool) -> dict:
        return wealthplan.dividend_plan(invest, yield_pct, years, growth_pct, reinvest)

    def ipo_sim(self, offer_price: float, alloc_shares: float, subscribe_amount: float) -> dict:
        return wealthplan.ipo_plan(offer_price, alloc_shares, subscribe_amount)

    def realty_loans(self, price: float, annual_income: float, age: float, married: bool,
                     homeless: bool, has_child: bool, deposit: float, mode: str) -> dict:
        return wealthplan.realty_loans(price, annual_income, age, married, homeless,
                                       has_child, deposit, mode)

    # -- 추천/일정 스냅샷 -----------------------------------------------------
    def dividend_picks(self, top: int) -> dict:
        return picks.dividend_picks(top)

    def ipo_schedule(self) -> dict:
        return picks.ipo_schedule()
