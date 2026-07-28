"""Macro HTTP routes — thin transport layer.

Each handler only reads query params and delegates to the injected
``MacroService``. No business logic, no data access. Paths, params and
docstrings are unchanged from the legacy ``/api/data`` router so this is a
drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .deps import get_macro_service
from .service import MacroService

router = APIRouter(prefix="/api/data", tags=["macro"])

Svc = Depends(get_macro_service)


@router.get("/korea-flow")
def korea_flow_endpoint(svc: MacroService = Svc):
    """한국 경제 흐름 — 부동산/리츠 ETF·국채 ETF 자금 신호 + 부동산·국채 뉴스 동향. 키 불필요."""
    return svc.korea_flow()


@router.get("/korea-diagnosis")
def korea_diagnosis_endpoint(svc: MacroService = Svc):
    """한국경제 종합 진단 — GDP·물가·경상·유동성·금리·심리 축별 평가 + 종합 국면(ECOS 실측)."""
    return svc.korea_diagnosis()


@router.get("/realestate-trades")
def realestate_trades_endpoint(svc: MacroService = Svc):
    """부동산 실거래 — 서울 25개구 아파트 매매 월별 거래량·거래대금 + 지역별 분포(국토부 RTMS)."""
    return svc.realestate_trades()


@router.get("/realestate-map")
def realestate_map_endpoint(svc: MacroService = Svc):
    """부동산 지도 — 시군구별 아파트 실거래(완성 최신월)에 좌표를 얹어 지도용으로(국토부 RTMS)."""
    return svc.realestate_map()


@router.get("/realestate-deals")
def realestate_deals_endpoint(lawd: str, ym: str | None = None, svc: MacroService = Svc):
    """시군구(LAWD) 단지별 아파트 매매 실거래 상세 — 지도 마커 클릭 시 드릴다운."""
    return svc.realestate_deals(lawd, ym)


@router.get("/realestate-apartments")
def realestate_apartments_endpoint(lawd: str, ym: str | None = None, svc: MacroService = Svc):
    """시군구(LAWD) 실거래를 단지 단위로 묶어 지도 마커용 — 읍/면/동 지오코딩 + 단지 분산."""
    return svc.realestate_apartments(lawd, ym)


@router.get("/realestate-apartment")
def realestate_apartment_endpoint(lawd: str, apt: str, dong: str | None = None,
                                  months: int = 120, svc: MacroService = Svc):
    """단지 상세 — 면적별 시세/실거래 시계열·거래이력·요약(국토부 N개월 실거래 이력 기반)."""
    return svc.realestate_apartment(lawd, apt, dong, months)


@router.get("/realestate-rent")
def realestate_rent_endpoint(svc: MacroService = Svc):
    """부동산 전월세 실거래 — 전국 아파트 월별 거래량·전세/월세 비중·평균 전세보증금(국토부 RTMS)."""
    return svc.realestate_rent()


@router.get("/ecos-macro")
def ecos_macro_endpoint(svc: MacroService = Svc):
    """국내 거시지표 — M2 통화량·가계신용·주택매매가격지수 추이 + 증가율(한국은행 ECOS)."""
    return svc.ecos_macro()


@router.get("/money-supply")
def money_supply_endpoint(svc: MacroService = Svc):
    """통화량 장기·국가 비교 — 한국 M2를 과거 위기(IMF·금융위기·코로나)·해외 주요국과 견줌."""
    return svc.money_supply()


@router.get("/money-analysis")
def money_analysis_endpoint(svc: MacroService = Svc):
    """통화량 심층분석 — 마샬케이·유통속도·실질통화량·신용/GDP + 돈의 행선지(자산 상관) + 실질금리·NBER 침체."""
    return svc.money_analysis()


@router.get("/real-economy")
def real_economy_endpoint(svc: MacroService = Svc):
    """실물경제 — 한국 국민계정(민간소비·설비/건설투자·수출·취업자수) + 세계 비교(물가·소비·투자·수출·경상수지·실업률)."""
    return svc.real_economy()
