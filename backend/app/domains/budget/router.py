"""Budget HTTP routes — thin transport layer.

Each handler only: reads/validates params (auth via ``require_auth``), delegates
to the injected ``BudgetService``, and returns the payload unchanged. File
uploads are read here (``await file.read()``) so the service stays sync and
framework-free. Paths are unchanged from the legacy ``/api/data`` router so
this is a drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile

from app.core.auth import require_auth

from .deps import get_budget_service
from .service import BudgetService

router = APIRouter(prefix="/api/data", tags=["budget"])

Svc = Depends(get_budget_service)


@router.get("/budget/summary")
def budget_summary(month: str | None = Query(default=None), user: str = Depends(require_auth),
                   svc: BudgetService = Svc):
    """월별 지출 요약 + 카테고리 분류 + 저축 가능액."""
    return svc.summary(user, month)


@router.post("/budget/income")
def budget_income(monthly_net: float = Body(...), extra: float = Body(default=0),
                  memo: str = Body(default=""), user: str = Depends(require_auth),
                  svc: BudgetService = Svc):
    """월 급여(실수령액) 등 수입 설정."""
    return svc.set_income(user, monthly_net, extra, memo)


@router.post("/budget/income/parse")
async def budget_income_parse(file: UploadFile = File(...), user: str = Depends(require_auth),
                              svc: BudgetService = Svc):
    """급여명세서(엑셀/PDF/CSV) 업로드 → 실수령액·지급·공제 추출(저장 아님, 확인용)."""
    data = await file.read()
    return svc.parse_payslip(file.filename or "", data)


@router.post("/budget/import")
def budget_import(text: str = Body(..., embed=True), user: str = Depends(require_auth),
                  svc: BudgetService = Svc):
    """카드사 CSV/표 텍스트를 붙여넣어 거래내역 일괄 등록(자동 카테고리)."""
    return svc.import_csv(user, text)


@router.post("/budget/import-file")
async def budget_import_file(file: UploadFile = File(...), user: str = Depends(require_auth),
                             svc: BudgetService = Svc):
    """카드사 엑셀(.xlsx/.xls)/CSV 파일 업로드 → 헤더 인식 파싱 후 거래내역 등록."""
    data = await file.read()
    return svc.import_file(user, file.filename or "", data)


@router.post("/budget/add")
def budget_add(items: list[dict] = Body(...), user: str = Depends(require_auth),
               svc: BudgetService = Svc):
    """거래내역 수동 추가 [{date, merchant, amount, category?}]."""
    return svc.add_transactions(user, items)


@router.post("/budget/delete")
def budget_delete(tx_id: int = Query(...), user: str = Depends(require_auth),
                  svc: BudgetService = Svc):
    return svc.delete_transaction(user, tx_id)


@router.post("/budget/category")
def budget_category(tx_id: int = Query(...), category: str = Query(...),
                    apply_all: bool = Query(default=True), user: str = Depends(require_auth),
                    svc: BudgetService = Svc):
    """거래 분류 변경(같은 가맹점은 규칙으로 기억·재분류)."""
    return svc.set_category(user, tx_id, category, apply_all)


@router.post("/budget/clear-month")
def budget_clear_month(month: str = Query(...), user: str = Depends(require_auth),
                       svc: BudgetService = Svc):
    return svc.clear_month(user, month)


@router.get("/budget/plan")
def budget_plan(emergency_months: int = Query(default=3, ge=1, le=12),
                invest_ratio: float = Query(default=0.5, ge=0.0, le=1.0),
                user: str = Depends(require_auth),
                svc: BudgetService = Svc):
    """저축·투자 계획 — 수입−평균지출 여유로 비상금·저축·투자(주식 자산 포함) 배분."""
    return svc.plan(user, emergency_months, invest_ratio)
