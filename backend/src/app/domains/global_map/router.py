"""Global map HTTP routes — thin transport layer.

Each handler only: reads/validates query params, delegates to the injected
``GlobalMapService``, and returns the payload. No business logic, no store
access. Paths are unchanged from the legacy ``/api/data`` router so this is a
drop-in migration; the legacy 404/400 stay here to keep behavior identical.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .deps import get_global_map_service
from .service import GlobalMapService

router = APIRouter(prefix="/api/data", tags=["global"])

Svc = Depends(get_global_map_service)


@router.get("/global-clusters")
def global_clusters_endpoint(svc: GlobalMapService = Svc):
    """글로벌 경쟁지도 — 기술/산업 클러스터 요약(한국+해외 합산 시총·평균 영업이익률)."""
    return svc.clusters()


@router.get("/global-cluster")
def global_cluster_endpoint(
    key: str = Query(..., description="cluster key"), svc: GlobalMapService = Svc
):
    """한 클러스터의 전체 경쟁사(한국+해외) — 시총(USD)·영업이익률·등락률 비교."""
    c = svc.cluster(key)
    if not c:
        raise HTTPException(status_code=404, detail="해당 클러스터 없음")
    return c


@router.post("/global-clusters/refresh")
def global_clusters_refresh(svc: GlobalMapService = Svc):
    """해외 경쟁사 펀더멘털(Finnhub)을 일괄 갱신 → 클러스터 캐시 무효화."""
    if not svc.finnhub_enabled():
        raise HTTPException(status_code=400, detail="FINNHUB_API_KEY 미설정")
    return svc.refresh()
