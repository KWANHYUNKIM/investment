"""Business logic for the costmodel domain.

Pure delegation to the same ``app.data.*`` engines the legacy router used —
behavior is identical by construction. Function-local lazy imports are kept
lazy *inside* the corresponding method, exactly where the legacy endpoints had
them (they gate heavy parsers/schedulers so process start stays fast). The
``integrity`` orchestration and ``future-value`` row filtering are moved here
verbatim. ``KeyError`` from unknown product/ticker propagates to the router,
which maps it to the same 404 as before.
"""
from __future__ import annotations

from app.data.fundamentals import commodities
from app.data.fundamentals import company_costmodel
from app.data.fundamentals import peer_compare
from app.data.fundamentals import unit_economics


class CostmodelService:
    # -- unit economics -----------------------------------------------------
    def unit_economics_products(self) -> dict:
        return {"as_of": commodities.AS_OF, "products": unit_economics.list_products()}

    def unit_economics_teardown(self, product: str) -> dict:
        return unit_economics.teardown(product)

    # -- company cost model -------------------------------------------------
    def company_costmodel_list(self) -> dict:
        return {
            "as_of": commodities.AS_OF,
            "sectors": company_costmodel.sectors(),
            "companies": company_costmodel.list_companies(),
        }

    def company_costmodel_analyze(self, ticker: str) -> dict:
        return company_costmodel.analyze(ticker)

    def company_labor(self, ticker: str) -> dict:
        from app.data.fundamentals import labor_cost
        return labor_cost.analyze(ticker)

    # -- statements / reports ----------------------------------------------
    def statement_audit(self, ticker: str, with_report: bool) -> dict:
        from app.data.fundamentals import report_notes, statement_audit
        nt = report_notes.notes(ticker) if with_report else None
        return statement_audit.audit(ticker, nt)

    def report_business(self, ticker: str, refresh: bool) -> dict:
        from app.data.fundamentals import report_business
        return report_business.business(ticker, refresh=refresh)

    def report_notes(self, ticker: str, refresh: bool) -> dict:
        from app.data.fundamentals import report_notes
        return report_notes.notes(ticker, refresh=refresh)

    def dart_full(self, ticker: str, refresh: bool) -> dict:
        from app.data.fundamentals import dart_full
        return dart_full.full(ticker, refresh=refresh)

    def integrity(self, ticker: str, refresh: bool) -> dict:
        from app.data.fundamentals import (dart_full, integrity, labor_cost,
                                           report_business, report_notes)
        d = dart_full.full(ticker, refresh=refresh)
        nt = report_notes.notes(ticker, refresh=refresh)
        sep = d.get("separate") or {}
        return integrity.evaluate(
            ticker, dfull=d, notes=nt, labor=labor_cost.analyze(ticker),
            biz=report_business.business(ticker),
            separate=(sep.get(max(sep)) if sep else None))

    def statement_audit_coverage(self, limit: int) -> dict:
        from app.data.fundamentals import statement_audit
        return statement_audit.coverage_summary(limit or None)

    # -- education / ranking / future value ---------------------------------
    def costing_education(self) -> dict:
        from app.data.fundamentals import costing_edu
        return costing_edu.content()

    def company_costmodel_ranking(self, sector: str | None, limit: int) -> dict:
        from app.data.fundamentals import cost_ranking
        return cost_ranking.ranking(sector=sector, limit=limit)

    def future_value(self, sector: str | None, only_loss: bool, limit: int) -> dict:
        from app.data.fundamentals import future_value
        b = future_value.board()
        rows = b["rows"]
        if sector:
            rows = [r for r in rows if r["sector"] == sector]
        if only_loss:
            rows = [r for r in rows if r["loss_making"]]
        return {**b, "rows": rows[:limit] if limit else rows, "filtered": len(rows)}

    # -- batch / products / reports / commodities ---------------------------
    def batch_status(self) -> dict:
        from app.data.schedulers import costmodel_scheduler
        return costmodel_scheduler.status()

    def company_products(self, ticker: str) -> dict:
        return company_costmodel.dart_products(ticker)

    def analyst_reports(self, ticker: str, company: str) -> dict:
        from app.data.news import naver_research
        return naver_research.reports(company, ticker)

    def commodities(self) -> dict:
        return {"as_of": commodities.AS_OF, "items": commodities.all()}

    # -- peer comparison ----------------------------------------------------
    def peer_compare(self, product: str) -> dict:
        return peer_compare.compare(product)

    def peer_news(self, product: str, per: int) -> dict:
        return peer_compare.news_compare(product, per=per)

    def peer_global(self, product: str) -> dict:
        return peer_compare.global_compare(product)
