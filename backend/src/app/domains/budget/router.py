"""Budget HTTP routes — thin transport layer.

Each handler only: reads/validates params (auth via ``require_auth``), delegates
to the injected ``BudgetService``, and returns the payload unchanged. File
uploads are read here (``await file.read()``) so the service stays sync and
framework-free.

카드 명세서는 **먼저 보고(preview-file) 나중에 등록(import-file)** 하는 두 단계를
둔다. 카드사마다 금액의 의미가 달라(할부·포인트·취소) 바로 저장하면 틀린 걸
나중에 찾기 어렵기 때문이다. 예전처럼 한 번에 넣고 싶으면 import-file 만 쓰면 된다.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile

from app.core.auth import require_auth

from .deps import get_budget_service
from .service import BudgetService

router = APIRouter(prefix="/api/data", tags=["budget"])

Svc = Depends(get_budget_service)


@router.get("/budget/summary")
def budget_summary(month: str | None = Query(default=None),
                   basis: str = Query(default="billing_month",
                                      pattern="^(billing_month|date)$"),
                   user: str = Depends(require_auth), svc: BudgetService = Svc):
    """월별 지출 요약 — 카테고리·카드·거래구분·고정비 네 축으로 분리 + 할부 잔여.

    basis: ``billing_month``(청구월, 기본) | ``date``(거래월).
    """
    return svc.summary(user, month, basis)


@router.get("/budget/installments")
def budget_installments(user: str = Depends(require_auth), svc: BudgetService = Svc):
    """남은 할부와 향후 월별 확정 지출."""
    return svc.installments(user)


@router.get("/budget/issuers")
def budget_issuers(svc: BudgetService = Svc):
    """전용 파서가 있는 카드사 목록 + 카테고리 목록."""
    return svc.issuers()


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


@router.post("/budget/preview-file")
async def budget_preview_file(file: UploadFile = File(...), user: str = Depends(require_auth),
                              svc: BudgetService = Svc):
    """카드사 파일 업로드 → 파싱 결과만 반환(저장하지 않음). 확인 후 /budget/add 로 등록."""
    data = await file.read()
    return svc.preview_file(file.filename or "", data)


@router.post("/budget/import-file")
async def budget_import_file(file: UploadFile = File(...), user: str = Depends(require_auth),
                             svc: BudgetService = Svc):
    """카드사 파일 업로드 → 파싱 후 바로 등록(중복 자동 제외)."""
    data = await file.read()
    return svc.import_file(user, file.filename or "", data)


@router.post("/budget/import")
def budget_import(text: str = Body(..., embed=True), user: str = Depends(require_auth),
                  svc: BudgetService = Svc):
    """카드사 CSV/표 텍스트를 붙여넣어 거래내역 일괄 등록(자동 카테고리)."""
    return svc.import_csv(user, text)


@router.post("/budget/add")
def budget_add(items: list[dict] = Body(...), user: str = Depends(require_auth),
               svc: BudgetService = Svc):
    """거래내역 등록. preview-file 이 준 거래를 그대로 넘기거나
    ``[{date, merchant, amount, category?}]`` 로 직접 넣는다."""
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


@router.post("/budget/fixed")
def budget_fixed(merchant: str = Query(...), fixed: bool | None = Query(default=None),
                 user: str = Depends(require_auth), svc: BudgetService = Svc):
    """가맹점을 고정비/변동비로 못박는다. fixed 를 생략하면 자동 판정으로 되돌린다."""
    return svc.set_fixed(user, merchant, fixed)


@router.post("/budget/clear-month")
def budget_clear_month(month: str = Query(...),
                       by: str = Query(default="billing_month",
                                       pattern="^(billing_month|date)$"),
                       user: str = Depends(require_auth), svc: BudgetService = Svc):
    return svc.clear_month(user, month, by)


@router.post("/budget/clear-import")
def budget_clear_import(issuer: str = Query(...), billing_month: str = Query(...),
                        user: str = Depends(require_auth), svc: BudgetService = Svc):
    """방금 올린 명세서 되돌리기 — 카드사 + 청구월로 한 번에 지운다."""
    return svc.clear_import(user, issuer, billing_month)


@router.post("/budget/move-month")
def budget_move_month(issuer: str = Query(...), from_month: str = Query(...),
                      to_month: str = Query(...), user: str = Depends(require_auth),
                      svc: BudgetService = Svc):
    """등록해 둔 한 묶음의 청구월을 옮긴다 — 추정 청구월이 한 달 어긋났을 때."""
    return svc.move_month(user, issuer, from_month, to_month)


@router.get("/budget/plan")
def budget_plan(emergency_months: int = Query(default=3, ge=1, le=12),
                invest_ratio: float = Query(default=0.5, ge=0.0, le=1.0),
                user: str = Depends(require_auth),
                svc: BudgetService = Svc):
    """저축·투자 계획 — 수입−평균지출 여유에서 고정비·할부 확정분을 떼고 배분."""
    return svc.plan(user, emergency_months, invest_ratio)
