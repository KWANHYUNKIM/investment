"""소득·성장 (급여 상세·인상 시뮬·부업·투자수익) endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.auth import require_auth

from app.data.market import income

router = APIRouter()


@router.get("/income/overview")
def income_overview(user: str = Depends(require_auth)):
    """소득 종합 — 급여·부업·투자수익 + 월 총소득 + 조언."""
    return income.overview(user)


@router.get("/income/salary")
def income_salary_get(user: str = Depends(require_auth)):
    return income.get_salary(user)


@router.post("/income/salary")
def income_salary_set(earnings: list[dict] = Body(...), deductions: list[dict] = Body(default=[]),
                      memo: str = Body(default=""), user: str = Depends(require_auth)):
    """지급/공제 항목별 급여 저장(월 기준). [{label, amount}]"""
    return income.set_salary(user, earnings, deductions, memo)


@router.get("/income/raise-sim")
def income_raise_sim(raise_pct: float = Query(default=0), raise_amount: float = Query(default=0),
                     years: int = Query(default=5, ge=1, le=40),
                     invest_ratio: float = Query(default=0.5, ge=0.0, le=1.0),
                     annual_return: float = Query(default=6.0, ge=0.0, le=30.0),
                     user: str = Depends(require_auth)):
    """급여 인상 시나리오 + 인상분 적립투자 복리 미래가치."""
    return income.raise_sim(user, raise_pct, raise_amount, years, invest_ratio, annual_return)


@router.get("/income/side")
def income_side_list(month: str | None = Query(default=None), user: str = Depends(require_auth)):
    return income.list_side(user, month)


@router.post("/income/side")
def income_side_add(items: list[dict] = Body(...), user: str = Depends(require_auth)):
    """부업 소득 추가 [{date, source, amount, memo}]."""
    return income.add_side(user, items)


@router.post("/income/side/delete")
def income_side_delete(sid: int = Query(...), user: str = Depends(require_auth)):
    return income.delete_side(user, sid)
