"""Dividends HTTP routes — thin transport layer.

Each handler only reads/validates query params and delegates to the injected
``DividendsService``. No business logic, no store access. Paths are unchanged
from the legacy ``/api/data`` router so this is a drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .deps import get_dividends_service
from .service import DividendsService

router = APIRouter(prefix="/api/data", tags=["dividends"])

Svc = Depends(get_dividends_service)


@router.get("/dividends")
def dividends_endpoint(svc: DividendsService = Svc):
    """배당·실적 — 고배당 랭킹 + 영업이익 YoY 실적개선 랭킹."""
    return svc.board()


@router.get("/dividend-universe")
def dividend_universe_endpoint(svc: DividendsService = Svc):
    """종목 단위 배당 계산기 — 검색 가능한 전 종목 + 배당수익률·추정 주당배당금(DPS)."""
    return svc.stock_universe()


@router.get("/dividend-detail")
def dividend_detail_endpoint(
    ticker: str = Query(..., description="single ticker"),
    svc: DividendsService = Svc,
):
    """종목 단위 배당 심층 분석 — 배당률 + 투자전 체크리스트(매출·순이익·영업현금흐름·
    배당연수·배당성장률) + 3대 위기(2000·2008·2020) 배당 내역."""
    return svc.detail(ticker)


@router.get("/dividend-royalty")
def dividend_royalty_endpoint(
    invest: float = Query(default=0, ge=0),
    svc: DividendsService = Svc,
):
    """배당 성장주 레퍼런스 — 배당왕(50년+)·배당귀족(25년+ & S&P500)·월배당 포트.

    invest>0 이면 월배당 동일가중 포트폴리오의 월 배당(세전/세후) 추정도 함께 반환.
    """
    return svc.royalty_board(invest)


@router.get("/crisis-survivors")
def crisis_survivors_endpoint(svc: DividendsService = Svc):
    """3대 위기(2000·2008·2020)를 이겨내고 우상향한 배당주 — 장기 주가 궤적 +
    위기별 낙폭 + 배당 방어(배당왕/귀족). 첫 호출은 주가 취합으로 느릴 수 있음(하루 캐시)."""
    return svc.crisis_survivors()


@router.get("/dividend-etf")
def dividend_etf_endpoint(svc: DividendsService = Svc):
    """배당·인덱스 ETF 레퍼런스 — 배당성장(VIG·SCHD·DGRO 등)·고배당·커버드콜·S&P500."""
    return svc.etf_board()


@router.get("/sp-dca")
def sp_dca_endpoint(
    monthly: float = Query(default=500000, ge=0, description="월 적립액(원 또는 통화단위)"),
    years: float = Query(default=20, gt=0, le=60),
    annual_return: float = Query(default=0.10, ge=-0.5, le=0.5),
    svc: DividendsService = Svc,
):
    """S&P500 적립형 — 매월 적립 시 미래가치·예상 배당 추정(복리)."""
    return svc.sp_dca(monthly, years, annual_return)
