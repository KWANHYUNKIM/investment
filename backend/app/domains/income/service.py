"""Business logic seam for the income domain.

The actual computation (급여 실수령 계산, 인상 시뮬 복리, 부업 집계, 조언 생성)
lives in ``app.data.market.income`` and is deliberately NOT reimplemented here —
the strangler-fig contract is identical behavior, so every method delegates 1:1
to the same functions the legacy endpoints called. When that module is later
split into real service/repository code, only this file changes.
"""
from __future__ import annotations

from app.data.market import income as income_data


class IncomeService:
    # -- 종합 -----------------------------------------------------------------
    def overview(self, user: str) -> dict:
        return income_data.overview(user)

    # -- 급여 -----------------------------------------------------------------
    def get_salary(self, user: str) -> dict:
        return income_data.get_salary(user)

    def set_salary(self, user: str, earnings: list[dict], deductions: list[dict],
                   memo: str) -> dict:
        return income_data.set_salary(user, earnings, deductions, memo)

    def raise_sim(self, user: str, raise_pct: float, raise_amount: float, years: int,
                  invest_ratio: float, annual_return: float) -> dict:
        return income_data.raise_sim(user, raise_pct, raise_amount, years,
                                     invest_ratio, annual_return)

    # -- 부업 -----------------------------------------------------------------
    def list_side(self, user: str, month: str | None) -> dict:
        return income_data.list_side(user, month)

    def add_side(self, user: str, items: list[dict]) -> dict:
        return income_data.add_side(user, items)

    def delete_side(self, user: str, sid: int) -> dict:
        return income_data.delete_side(user, sid)
