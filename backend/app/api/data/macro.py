"""Korea macro / real-estate / money-supply endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.data.macro import korea_flow
from app.data.macro import money_analysis
from app.data.macro import money_supply
from app.data.macro import realeconomy
from app.data.macro import realestate
from app.data.macro import rent
from app.data.macro import ecos

router = APIRouter()


@router.get("/korea-flow")
def korea_flow_endpoint():
    """한국 경제 흐름 — 부동산/리츠 ETF·국채 ETF 자금 신호 + 부동산·국채 뉴스 동향. 키 불필요."""
    return korea_flow.snapshot()


@router.get("/korea-diagnosis")
def korea_diagnosis_endpoint():
    """한국경제 종합 진단 — GDP·물가·경상·유동성·금리·심리 축별 평가 + 종합 국면(ECOS 실측)."""
    from app.data.macro import korea_diagnosis
    return korea_diagnosis.diagnosis()


@router.get("/realestate-trades")
def realestate_trades_endpoint():
    """부동산 실거래 — 서울 25개구 아파트 매매 월별 거래량·거래대금 + 지역별 분포(국토부 RTMS)."""
    return realestate.snapshot()


@router.get("/realestate-map")
def realestate_map_endpoint():
    """부동산 지도 — 시군구별 아파트 실거래(완성 최신월)에 좌표를 얹어 지도용으로(국토부 RTMS)."""
    from app.data.macro import realestate_map
    return realestate_map.map_snapshot()


@router.get("/realestate-deals")
def realestate_deals_endpoint(lawd: str, ym: str | None = None):
    """시군구(LAWD) 단지별 아파트 매매 실거래 상세 — 지도 마커 클릭 시 드릴다운."""
    from app.data.macro import realestate_map
    return realestate_map.region_deals(lawd, ym)


@router.get("/realestate-apartments")
def realestate_apartments_endpoint(lawd: str, ym: str | None = None):
    """시군구(LAWD) 실거래를 단지 단위로 묶어 지도 마커용 — 읍/면/동 지오코딩 + 단지 분산."""
    from app.data.macro import realestate_map
    return realestate_map.region_apartments(lawd, ym)


@router.get("/realestate-apartment")
def realestate_apartment_endpoint(lawd: str, apt: str, dong: str | None = None,
                                  months: int = 120):
    """단지 상세 — 면적별 시세/실거래 시계열·거래이력·요약(국토부 N개월 실거래 이력 기반)."""
    from app.data.macro import realestate_map
    return realestate_map.apartment_detail(lawd, apt, dong, months)


@router.get("/realestate-rent")
def realestate_rent_endpoint():
    """부동산 전월세 실거래 — 전국 아파트 월별 거래량·전세/월세 비중·평균 전세보증금(국토부 RTMS)."""
    return rent.snapshot()


@router.get("/ecos-macro")
def ecos_macro_endpoint():
    """국내 거시지표 — M2 통화량·가계신용·주택매매가격지수 추이 + 증가율(한국은행 ECOS)."""
    return ecos.snapshot()


@router.get("/money-supply")
def money_supply_endpoint():
    """통화량 장기·국가 비교 — 한국 M2를 과거 위기(IMF·금융위기·코로나)·해외 주요국과 견줌."""
    return money_supply.snapshot()


@router.get("/money-analysis")
def money_analysis_endpoint():
    """통화량 심층분석 — 마샬케이·유통속도·실질통화량·신용/GDP + 돈의 행선지(자산 상관) + 실질금리·NBER 침체."""
    return money_analysis.snapshot()


@router.get("/real-economy")
def real_economy_endpoint():
    """실물경제 — 한국 국민계정(민간소비·설비/건설투자·수출·취업자수) + 세계 비교(물가·소비·투자·수출·경상수지·실업률)."""
    return realeconomy.snapshot()
