"""금융위기 시뮬레이터 엔드포인트.

  GET /api/crisis/meta              — 지표·위기 목록
  GET /api/crisis/sim?metric=&crises=  — Day0 정렬 곡선 + 현재 아날로그 + 예상 투영
  GET /api/crisis/warning           — 위기 선행징후 조기경보(전조지표 체크)
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


@router.get("/warning")
def crisis_warning():
    return crisis.warning_signs()


@router.get("/korea-warning")
def crisis_korea_warning():
    return crisis.korea_fx_warning()


@router.get("/countries")
def crisis_countries():
    return crisis.country_macros()


@router.get("/sim")
def crisis_sim(
    metric: str = Query(default="fx"),
    crises: str | None = Query(default=None),
):
    keys = [k.strip() for k in crises.split(",") if k.strip()] if crises else None
    return crisis.simulate(metric, keys)
