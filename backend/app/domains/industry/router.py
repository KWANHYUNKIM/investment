"""Industry HTTP routes — thin transport layer.

Each handler only: reads query params, delegates to the injected
``IndustryService``, and returns the payload. Paths are unchanged from the
legacy ``/api/data`` router so this is a drop-in migration. The unknown-
industry 404 (status + detail) is raised here, identical to the legacy
handler.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .deps import get_industry_service
from .service import IndustryService

router = APIRouter(prefix="/api/data", tags=["industry"])

Svc = Depends(get_industry_service)


@router.get("/industries")
def industries_endpoint(full: bool = Query(default=False), svc: IndustryService = Svc):
    """KOSPI/KOSDAQ companies grouped by KSIC industry (largest cap first).

    `full=false` (default) returns the lightweight index (no members) for the
    left-hand list; `full=true` returns every group with its member companies.
    """
    return svc.industries(full)


@router.get("/industry")
def industry_endpoint(
    name: str = Query(..., description="industry (업종) name"),
    svc: IndustryService = Svc,
):
    """One industry: member companies (경쟁군) + research feed (기술/M&A/계약/실적/전략)."""
    out = svc.industry_detail(name)
    if out is None:
        raise HTTPException(404, f"'{name}' 업종을 찾을 수 없습니다.")
    return out


@router.get("/industry-scheduler-status")
def industry_scheduler_status(svc: IndustryService = Svc):
    """Background industry map scheduler progress."""
    return svc.scheduler_status()


@router.post("/industry/refresh")
def industry_refresh(snapshot: bool = Query(default=False), svc: IndustryService = Svc):
    """Refresh industry profiles now; optionally also build today's snapshot."""
    return svc.refresh(snapshot)
