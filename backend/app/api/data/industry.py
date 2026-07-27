"""Industry / competition map endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data.intel import industry
from app.data.intel import industry_research
from app.data.schedulers import industry_scheduler

router = APIRouter()


@router.get("/industries")
def industries_endpoint(full: bool = Query(default=False)):
    """KOSPI/KOSDAQ companies grouped by KSIC industry (largest cap first).

    `full=false` (default) returns the lightweight index (no members) for the
    left-hand list; `full=true` returns every group with its member companies.
    """
    if full:
        return {"industries": industry.industries()}
    return {
        "industries": industry.industry_names(),
        "scheduler": industry_scheduler.status(),
    }


@router.get("/industry")
def industry_endpoint(name: str = Query(..., description="industry (업종) name")):
    """One industry: member companies (경쟁군) + research feed (기술/M&A/계약/실적/전략)."""
    grp = industry.get_industry(name)
    if grp is None:
        raise HTTPException(404, f"'{name}' 업종을 찾을 수 없습니다.")
    research = industry_research.research_industry(name)
    return {"group": grp, "research": research}


@router.get("/industry-scheduler-status")
def industry_scheduler_status():
    """Background industry map scheduler progress."""
    return industry_scheduler.status()


@router.post("/industry/refresh")
def industry_refresh(snapshot: bool = Query(default=False)):
    """Refresh industry profiles now; optionally also build today's snapshot."""
    n = industry.refresh_profiles()
    out: dict = {"profiles": n}
    if snapshot:
        out["snapshot"] = industry_research.snapshot(force=True)
    return out
