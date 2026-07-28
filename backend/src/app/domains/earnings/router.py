"""Earnings HTTP routes — thin transport layer.

Each handler only delegates to the injected ``EarningsService`` and returns its
payload untouched. No business logic, no store access. Paths are unchanged from
the legacy ``/api/data`` router so this is a drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .deps import get_earnings_service
from .service import EarningsService

router = APIRouter(prefix="/api/data", tags=["earnings"])

Svc = Depends(get_earnings_service)


@router.get("/kospi-earnings")
def kospi_earnings_endpoint(svc: EarningsService = Svc):
    """전체 기업 실적 — 매출·영업이익·순이익·영업이익률·전년比 + PER/PBR/ROE/시총(전 종목)."""
    return svc.kospi_earnings()


@router.get("/delisting-risk")
def delisting_risk_endpoint(svc: EarningsService = Svc):
    """관리종목·상장폐지 위험 스크리너 + 감사 정정(어닝쇼크) 공시 경보."""
    return svc.delisting_risk()


@router.get("/delisting-risk/batch")
def delisting_batch_status(svc: EarningsService = Svc):
    """관리종목·상폐 스크리너 데이터 배치 상태(시장구분·공시·반기 자본계정 준비 여부)."""
    return svc.delisting_batch_status()


@router.get("/earnings-quality")
def earnings_quality_endpoint(svc: EarningsService = Svc):
    """이익의 질·회계 착시 — 연결범위·비지배지분·일회성이익·자산처분이익 탐지."""
    return svc.earnings_quality()
