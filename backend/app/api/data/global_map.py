"""Global competition map (clusters) endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data.fundamentals import finnhub
from app.data.intel import global_map
from app.data.infra import global_universe
from app.data.infra import store

router = APIRouter()


@router.get("/global-clusters")
def global_clusters_endpoint():
    """글로벌 경쟁지도 — 기술/산업 클러스터 요약(한국+해외 합산 시총·평균 영업이익률)."""
    return {"clusters": global_map.index(), "finnhub": finnhub.enabled(),
            "foreign_loaded": store.foreign_fin_count()}


@router.get("/global-cluster")
def global_cluster_endpoint(key: str = Query(..., description="cluster key")):
    """한 클러스터의 전체 경쟁사(한국+해외) — 시총(USD)·영업이익률·등락률 비교."""
    c = global_map.get(key)
    if not c:
        raise HTTPException(status_code=404, detail="해당 클러스터 없음")
    return c


@router.post("/global-clusters/refresh")
def global_clusters_refresh():
    """해외 경쟁사 펀더멘털(Finnhub)을 일괄 갱신 → 클러스터 캐시 무효화."""
    if not finnhub.enabled():
        raise HTTPException(status_code=400, detail="FINNHUB_API_KEY 미설정")
    n = finnhub.refresh_many(global_universe.all_foreign_symbols())
    global_map.invalidate()
    return {"fetched": n, "foreign_loaded": store.foreign_fin_count()}
