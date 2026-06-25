"""금융위기 시뮬레이터 엔드포인트.

  GET /api/crisis/meta              — 지표·위기 목록
  GET /api/crisis/sim?metric=&crises=  — Day0 정렬 곡선 + 현재 한국 궤적 + 유사도
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.data.market import crisis

router = APIRouter(prefix="/api/crisis", tags=["crisis"])


@router.get("/meta")
def crisis_meta():
    return crisis.meta()


@router.get("/warm-status")
def crisis_warm_status():
    return crisis.warm_status()


@router.get("/sim")
def crisis_sim(
    metric: str = Query(default="fx"),
    crises: str | None = Query(default=None),
):
    keys = [k.strip() for k in crises.split(",") if k.strip()] if crises else None
    return crisis.simulate(metric, keys)
