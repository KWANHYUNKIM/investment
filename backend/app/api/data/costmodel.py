"""Cost-model / unit-economics / statement-audit / peer-compare endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data.fundamentals import unit_economics
from app.data.fundamentals import company_costmodel
from app.data.fundamentals import peer_compare
from app.data.fundamentals import commodities

router = APIRouter()


@router.get("/unit-economics/products")
def unit_economics_products():
    """제품 단위 원가분해가 가능한 제품 목록 (위젯 드롭다운용)."""
    return {"as_of": commodities.AS_OF, "products": unit_economics.list_products()}


@router.get("/unit-economics")
def unit_economics_endpoint(
    product: str = Query(..., description="product id, e.g. 004370:sinramyeon"),
):
    """제품 1개를 팔면 소비자가가 누구에게 얼마씩 가는지 + 마진 민감도."""
    try:
        return unit_economics.teardown(product)
    except KeyError:
        raise HTTPException(404, f"unknown product: {product}")


@router.get("/company-costmodel/list")
def company_costmodel_list():
    """레벨1: 회사 목록(업종 태그 포함) + 업종 필터 목록.  (원가분석 드릴다운)"""
    return {
        "as_of": commodities.AS_OF,
        "sectors": company_costmodel.sectors(),
        "companies": company_costmodel.list_companies(),
    }


@router.get("/company-costmodel")
def company_costmodel_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 004370"),
):
    """레벨2·3: 회사의 품목 전체 원가·영익 + 원재료 시세 + 마진 정합성 + 재무근거."""
    try:
        return company_costmodel.analyze(ticker)
    except KeyError:
        raise HTTPException(404, f"unknown company: {ticker}")


@router.get("/company-labor")
def company_labor_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 004370"),
):
    """(W1) 인건비 실측 — DART 「직원 등의 현황」 3개년·부문별 + 노동생산성 + 조작탐지 플래그."""
    from app.data.fundamentals import labor_cost
    return labor_cost.analyze(ticker)


@router.get("/statement-audit")
def statement_audit_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 005930"),
    with_report: bool = Query(True, description="감사보고서(의견·KAM)까지 원문에서 확인"),
):
    """재무제표 3종(재무상태표·손익계산서·현금흐름표) 구비 점검 + 정합성 조작탐지."""
    from app.data.fundamentals import report_notes, statement_audit
    nt = report_notes.notes(ticker) if with_report else None
    return statement_audit.audit(ticker, nt)


@router.get("/report-business")
def report_business_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 005490"),
    refresh: bool = Query(False),
):
    """(B3·B4) 사업보고서 「사업의 내용」 — 실제 원재료·제품 단가 변동 + 생산실적·가동률."""
    from app.data.fundamentals import report_business
    return report_business.business(ticker, refresh=refresh)


@router.get("/report-notes")
def report_notes_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 004370"),
    refresh: bool = Query(False),
):
    """사업보고서 **원문** 실측 — 「비용의 성격별 분류」(재료비·노무비·감가상각) + 감사보고서."""
    from app.data.fundamentals import report_notes
    return report_notes.notes(ticker, refresh=refresh)


@router.get("/dart-full")
def dart_full_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 161890"),
    refresh: bool = Query(False),
):
    """(§15.2) 사업보고서 **전 항목** 파싱 — 원재료 매입액·매출실적·영업부문·재고·특수관계자·
    감사메타·자금조달·연결범위 + 원단위(原單位) 역산."""
    from app.data.fundamentals import dart_full
    return dart_full.full(ticker, refresh=refresh)


@router.get("/integrity")
def integrity_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 161890"),
    refresh: bool = Query(False, description="사업보고서 파싱 캐시를 무시하고 다시 읽는다"),
):
    """(§15.1) 원가 진실성 스코어 — 교차검증 X1~X35 전 항목과 근거(A·B 출처·수치)."""
    from app.data.fundamentals import (dart_full, integrity, labor_cost,
                                       report_business, report_notes)
    d = dart_full.full(ticker, refresh=refresh)
    nt = report_notes.notes(ticker, refresh=refresh)
    sep = d.get("separate") or {}
    return integrity.evaluate(
        ticker, dfull=d, notes=nt, labor=labor_cost.analyze(ticker),
        biz=report_business.business(ticker),
        separate=(sep.get(max(sep)) if sep else None))


@router.get("/statement-audit/coverage")
def statement_audit_coverage_endpoint(
    limit: int = Query(0, description="0=전체"),
):
    """전 종목 재무제표 적재 현황 — 어느 표가 몇 개 종목에 몇 개년 들어와 있는지."""
    from app.data.fundamentals import statement_audit
    return statement_audit.coverage_summary(limit or None)


@router.get("/costing-education")
def costing_education_endpoint():
    """⚪ 원가회계 교육 레이어 — 툴팁 + 해설 카드(정적 콘텐츠)."""
    from app.data.fundamentals import costing_edu
    return costing_edu.content()


@router.get("/company-costmodel/ranking")
def company_costmodel_ranking(
    sector: str | None = Query(None, description="업종 필터(없으면 전체)"),
    limit: int = Query(0, ge=0, le=500, description="상위 N개만(0=전체)"),
):
    """원가 경쟁력 순 회사 랭킹 — 수익성·원가추세·전가력·안정성·신뢰도 5개 항목 점수."""
    from app.data.fundamentals import cost_ranking
    return cost_ranking.ranking(sector=sector, limit=limit)


@router.get("/future-value")
def future_value_endpoint(
    sector: str | None = Query(None, description="업종 필터(없으면 전체)"),
    only_loss: bool = Query(False, description="적자기업만 — 미래투자형/소멸형 판별"),
    limit: int = Query(0, ge=0, le=1000),
):
    """미래가치 4문(門) — 재투자30·전환30·체력30·시장10 + 반증 신호(등급 상한)."""
    from app.data.fundamentals import future_value
    b = future_value.board()
    rows = b["rows"]
    if sector:
        rows = [r for r in rows if r["sector"] == sector]
    if only_loss:
        rows = [r for r in rows if r["loss_making"]]
    return {**b, "rows": rows[:limit] if limit else rows, "filtered": len(rows)}


@router.get("/company-costmodel/batch")
def company_costmodel_batch_status():
    """(I1) 전 종목 원가모델 야간 배치 상태 — 언제 돌았고 몇 개/몇 건 실패인지."""
    from app.data.schedulers import costmodel_scheduler
    return costmodel_scheduler.status()


@router.get("/company-products")
def company_products_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 004370"),
):
    """(P1) DART 사업보고서에서 회사가 실제로 파는 품목·매출비중% 자동 발굴."""
    return company_costmodel.dart_products(ticker)


@router.get("/analyst-reports")
def analyst_reports_endpoint(
    ticker: str = Query(..., description="종목코드, 예: 004370"),
    company: str = Query(..., description="회사명, 예: 농심"),
):
    """회사별 애널리스트 리포트 취합(Tier 1) — 제목·증권사·작성일·원문 링크(사실+링크만)."""
    from app.data.news import naver_research
    return naver_research.reports(company, ticker)


@router.get("/commodities")
def commodities_endpoint():
    """원자재 시세 스냅샷 (원가분해 엔진의 가격 소스)."""
    return {"as_of": commodities.AS_OF, "items": commodities.all()}


@router.get("/peer-compare")
def peer_compare_endpoint(
    product: str = Query(..., description="기준 제품 id, e.g. 004370:sinramyeon"),
):
    """같은 업종 경쟁 제품들의 원가구조 + 주가 변동성 비교."""
    try:
        return peer_compare.compare(product)
    except KeyError:
        raise HTTPException(404, f"unknown product: {product}")


@router.get("/peer-news")
def peer_news_endpoint(
    product: str = Query(..., description="기준 제품 id"),
    per: int = Query(default=6, ge=2, le=12),
):
    """경쟁군 회사들의 뉴스를 최신순으로 취합. Cached ~5min."""
    try:
        return peer_compare.news_compare(product, per=per)
    except KeyError:
        raise HTTPException(404, f"unknown product: {product}")


@router.get("/peer-global")
def peer_global_endpoint(
    product: str = Query(..., description="기준 제품 id"),
):
    """같은 제품군의 국내 경쟁사 + 글로벌 리더를 시가총액(USD)으로 비교."""
    try:
        return peer_compare.global_compare(product)
    except KeyError:
        raise HTTPException(404, f"unknown product: {product}")
