"""Earnings board / delisting-risk / earnings-quality endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/kospi-earnings")
def kospi_earnings_endpoint():
    """전체 기업 실적 — 매출·영업이익·순이익·영업이익률·전년比 + PER/PBR/ROE/시총(전 종목)."""
    from app.data.market import earnings
    return earnings.board()


@router.get("/delisting-risk")
def delisting_risk_endpoint():
    """관리종목·상장폐지 위험 스크리너 + 감사 정정(어닝쇼크) 공시 경보."""
    from app.data.market import delisting
    return delisting.board()


@router.get("/delisting-risk/batch")
def delisting_batch_status():
    """관리종목·상폐 스크리너 데이터 배치 상태(시장구분·공시·반기 자본계정 준비 여부)."""
    from app.data.schedulers import delisting_scheduler
    return delisting_scheduler.status()


@router.get("/earnings-quality")
def earnings_quality_endpoint():
    """이익의 질·회계 착시 — 연결범위·비지배지분·일회성이익·자산처분이익 탐지."""
    from app.data.market import earnings_quality
    return earnings_quality.board()
