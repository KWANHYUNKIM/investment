"""Business logic for the budget domain.

Pure delegation: every method forwards to the ``app.data.market.budget`` package,
which owns parsing (``cards/``), storage (``store``), and aggregation (``summary``).
File-upload endpoints hand the service ``(filename, data: bytes)`` — the async
read happens in the router, keeping this layer sync and framework-free.
"""
from __future__ import annotations

from app.data.market import budget as budget_data


class BudgetService:
    # --- 조회 ---------------------------------------------------------------
    def summary(self, user: str, month: str | None, basis: str = "billing_month") -> dict:
        return budget_data.summary(user, month, basis)

    def installments(self, user: str) -> dict:
        return budget_data.installments(user)

    def issuers(self) -> dict:
        return {"issuers": budget_data.ISSUERS, "categories": budget_data.CATEGORIES}

    def plan(self, user: str, emergency_months: int, invest_ratio: float) -> dict:
        return budget_data.plan(user, emergency_months, invest_ratio)

    # --- 수입 ---------------------------------------------------------------
    def set_income(self, user: str, monthly_net: float, extra: float, memo: str) -> dict:
        return budget_data.set_income(user, monthly_net, extra, memo)

    def parse_payslip(self, filename: str, data: bytes) -> dict:
        return budget_data.parse_payslip(filename, data)

    # --- 카드 명세서 --------------------------------------------------------
    def preview_file(self, filename: str, data: bytes) -> dict:
        return budget_data.preview_file(filename, data)

    def import_file(self, user: str, filename: str, data: bytes) -> dict:
        return budget_data.import_file(user, filename, data)

    def import_csv(self, user: str, text: str) -> dict:
        return budget_data.import_csv(user, text)

    # --- 편집 ---------------------------------------------------------------
    def add_transactions(self, user: str, items: list[dict]) -> dict:
        return budget_data.add_transactions(user, items)

    def delete_transaction(self, user: str, tx_id: int) -> dict:
        return budget_data.delete_transaction(user, tx_id)

    def set_category(self, user: str, tx_id: int, category: str, apply_all: bool) -> dict:
        return budget_data.set_category(user, tx_id, category, apply_all)

    def set_fixed(self, user: str, merchant: str, fixed: bool | None) -> dict:
        return budget_data.set_fixed(user, merchant, fixed)

    def clear_month(self, user: str, month: str, by: str = "billing_month") -> dict:
        return budget_data.clear_month(user, month, by)

    def clear_import(self, user: str, issuer: str, billing_month: str) -> dict:
        return budget_data.clear_import(user, issuer, billing_month)
