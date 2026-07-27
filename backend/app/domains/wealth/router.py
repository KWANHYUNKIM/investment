"""Wealth HTTP routes — thin transport layer.

Each handler only: reads/validates query/body params, checks auth, and
delegates to the injected ``WealthService``. No business logic. Paths are
unchanged from the legacy ``/api/data`` router so this is a drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.auth import require_auth

from .deps import get_wealth_service
from .service import WealthService

router = APIRouter(prefix="/api/data", tags=["wealth"])

Svc = Depends(get_wealth_service)


@router.get("/wealth/plan")
def wealth_plan(user: str = Depends(require_auth), svc: WealthService = Svc):
    """목표 달성 계획 + 자격 상품 추천 + 로드맵."""
    return svc.plan(user)


@router.post("/wealth/profile")
def wealth_profile(profile: dict = Body(...), user: str = Depends(require_auth),
                   svc: WealthService = Svc):
    """프로필/목표 저장(나이·연봉·월수입·월저축·현재자산·결혼·무주택·자녀·목표금액·기간) → 계획 반환."""
    return svc.save_profile(user, profile)


@router.get("/wealth/loan-sim")
def wealth_loan_sim(loan_amount: float = Query(...), loan_rate: float = Query(default=6.0),
                    loan_years: int = Query(default=5, ge=1, le=40),
                    invest_return: float = Query(default=8.0),
                    user: str = Depends(require_auth), svc: WealthService = Svc):
    """대출 레버리지 시뮬 — 월 상환액·총이자·투자 예상가치·순손익·손익분기 수익률·위험 경고."""
    return svc.loan_sim(loan_amount, loan_rate, loan_years, invest_return)


@router.get("/wealth/realty-sim")
def wealth_realty_sim(price: float = Query(...), own_capital: float = Query(...),
                      loan_rate: float = Query(default=4.5), years: int = Query(default=5, ge=1, le=40),
                      appreciation: float = Query(default=3.0),
                      mode: str = Query(default="wolse"),
                      deposit: float = Query(default=0.0), rent_monthly: float = Query(default=0.0),
                      user: str = Depends(require_auth), svc: WealthService = Svc):
    """부동산 투자 시뮬 — 자기자본+대출로 매입해 전세/월세. 대출·월현금흐름·수익률(ROE)·집값 시나리오·위험."""
    return svc.realty_sim(price, own_capital, loan_rate, years, appreciation, mode, deposit, rent_monthly)


@router.get("/wealth/holdings")
def wealth_holdings(user: str = Depends(require_auth), svc: WealthService = Svc):
    """내가 하고 있는 저축·상품 + 혜택 + N년 뒤 예상 금액(정부매칭·세제혜택 포함)."""
    return svc.holdings(user)


@router.post("/wealth/holdings")
def wealth_holdings_save(body: dict = Body(...), user: str = Depends(require_auth),
                         svc: WealthService = Svc):
    """내 저축·상품 저장 → 예상 재계산. body: {holdings:[{name,monthly,current}], horizon:int}"""
    return svc.save_holdings(user, body)


@router.get("/wealth/dividend-sim")
def wealth_dividend_sim(invest: float = Query(default=100000000), yield_pct: float = Query(default=5.0),
                        years: int = Query(default=10, ge=1, le=40), growth_pct: float = Query(default=3.0),
                        reinvest: bool = Query(default=True), user: str = Depends(require_auth),
                        svc: WealthService = Svc):
    """배당주 소득 — 투자금→연/월 배당(세후)·재투자 경로·목표 월소득에 필요한 투자금 + 방법 가이드."""
    return svc.dividend_sim(invest, yield_pct, years, growth_pct, reinvest)


@router.get("/wealth/ipo-sim")
def wealth_ipo_sim(offer_price: float = Query(default=30000), alloc_shares: float = Query(default=10),
                   subscribe_amount: float = Query(default=0), user: str = Depends(require_auth),
                   svc: WealthService = Svc):
    """공모주(IPO) 소득 — 배정 주수·공모가→상장일 상승률별 수익 시나리오 + 청약 방법 가이드."""
    return svc.ipo_sim(offer_price, alloc_shares, subscribe_amount)


@router.get("/wealth/realty-loans")
def wealth_realty_loans(price: float = Query(...), annual_income: float = Query(default=0),
                        age: float = Query(default=0), married: bool = Query(default=False),
                        homeless: bool = Query(default=True), has_child: bool = Query(default=False),
                        deposit: float = Query(default=0), mode: str = Query(default="wolse"),
                        user: str = Depends(require_auth), svc: WealthService = Svc):
    """부동산 대출 종류·한도 — 매매가·소득·자격으로 주담대(LTV·DSR)·디딤돌·보금자리·신생아특례·전세자금 한도."""
    return svc.realty_loans(price, annual_income, age, married, homeless, has_child, deposit, mode)


@router.get("/wealth/dividend-picks")
def wealth_dividend_picks(top: int = Query(default=12, ge=1, le=40), user: str = Depends(require_auth),
                          svc: WealthService = Svc):
    """배당주 추천 — 고배당 상위(유동성 필터·2~15% 밴드) + 1천만 투자 시 세후 월배당. 실시간 스냅샷."""
    return svc.dividend_picks(top)


@router.get("/wealth/ipo-schedule")
def wealth_ipo_schedule(user: str = Depends(require_auth), svc: WealthService = Svc):
    """공모주 청약일정 — 38커뮤니케이션 스크래핑(캐시 30분). 청약중·예정·최근마감 종목·공모가밴드·주간사."""
    return svc.ipo_schedule()
