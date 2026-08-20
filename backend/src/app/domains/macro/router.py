"""Macro HTTP routes — thin transport layer.

Each handler only reads query params and delegates to the injected
``MacroService``. No business logic, no data access. Paths, params and
docstrings are unchanged from the legacy ``/api/data`` router so this is a
drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

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


@router.get("/realestate-region-series")
def realestate_region_series_endpoint(
    lawd: str,
    trade: str = Query(default="sale", pattern="^(sale|jeonse|wolse)$"),
    svc: MacroService = Svc,
):
    """시군구 월별 거래량·평균가(+평형별) + 같은 기간 검색 관심도.

    ``trade``: ``sale``(매매·거래가) | ``jeonse``(전세·보증금) | ``wolse``(월세·보증금+월세)
    """
    return svc.realestate_region_series(lawd, trade)


@router.get("/realestate-commerce")
def realestate_commerce_endpoint(lawd: str, svc: MacroService = Svc):
    """지역 상권 — 업종 구성과 성격.

    업종 구성이 그 동네가 무엇을 하는 곳인지를 말한다. 사무실이 있어야 존재하는
    업종(과학·기술·시설관리)과 사람이 살아야 존재하는 업종(교육·보건·수리)의 비로
    업무지역·혼합·주거를 가른다.
    """
    return svc.realestate_commerce(lawd)


@router.get("/realestate-commerce/ranking")
def realestate_commerce_ranking_endpoint(
    character: str | None = Query(default=None, pattern="^(업무·상업|혼합|주거)$"),
    limit: int = Query(default=30, ge=1, le=250),
    svc: MacroService = Svc,
):
    """업무지수 순위(수집이 끝난 지역만)."""
    return svc.realestate_commerce_ranking(character, limit)


@router.get("/realestate-interest")
def realestate_interest_endpoint(svc: MacroService = Svc):
    """지역별 부동산 관심도 — 네이버 데이터랩 검색어 트렌드(앵커 정규화).

    거래량은 관심의 결과라 몇 주 늦는다. 검색은 그보다 먼저 튀므로 '검색은 올랐는데
    거래는 아직 안 붙은 지역' 을 볼 수 있다.
    """
    return svc.realestate_interest()


@router.post("/realestate-interest/collect")
def realestate_interest_collect_endpoint(months: int | None = None, svc: MacroService = Svc):
    """관심도 수집을 백그라운드로 시작(시군구 250곳이면 60여 번 호출이라 즉답 불가)."""
    return svc.realestate_interest_collect(months)


@router.get("/realestate-deals")
def realestate_deals_endpoint(lawd: str, ym: str | None = None, svc: MacroService = Svc):
    """시군구(LAWD) 단지별 아파트 매매 실거래 상세 — 지도 마커 클릭 시 드릴다운."""
    return svc.realestate_deals(lawd, ym)


@router.get("/realestate-apartments")
def realestate_apartments_endpoint(lawd: str, ym: str | None = None,
                                   trade: str = "sale", kind: str = "apt",
                                   svc: MacroService = Svc):
    """시군구(LAWD) 실거래를 단지 단위로 묶어 지도 마커용 — 읍/면/동 지오코딩 + 단지 분산.

    trade=sale|jeonse|wolse — 네이버 부동산의 매매/전세/월세 전환에 대응한다.
    kind=apt|offi|rh|sh|nrg|land|silv — 네이버의 매물 종류 탭에 대응한다.
    """
    return svc.realestate_apartments(lawd, ym, trade, kind)


@router.get("/poi-schools")
def poi_schools_endpoint(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
                         levels: str | None = None, svc: MacroService = Svc):
    """지도 범위 안의 학교 — 네이버 부동산의 학군 레이어. levels=초등학교,중학교 로 거른다."""
    return svc.poi_schools(sw_lat, sw_lng, ne_lat, ne_lng, levels)


@router.get("/poi-stations")
def poi_stations_endpoint(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
                          svc: MacroService = Svc):
    """지도 범위 안의 지하철역 — 네이버 부동산의 교통 레이어."""
    return svc.poi_stations(sw_lat, sw_lng, ne_lat, ne_lng)


@router.get("/realestate-kinds")
def realestate_kinds_endpoint(svc: MacroService = Svc):
    """지원하는 매물 종류 목록 — 유형별 전월세 실거래 제공 여부까지."""
    return svc.realestate_kinds()


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
