"""Future growth-theme endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data.intel import futuretheme
from app.data.schedulers import growth_scheduler

router = APIRouter()


@router.get("/future-themes")
def future_themes_endpoint():
    """미래 성장테마 요약(좌측 목록) — 메가트렌드별 모멘텀·종목수·하락후보수."""
    return {"themes": futuretheme.index()}


@router.get("/future-theme")
def future_theme_endpoint(key: str = Query(..., description="theme key")):
    """한 테마 상세 — 뉴스 동향(무엇이 구축되나) + 매핑 종목(미래가치 후보 강조)."""
    t = futuretheme.get(key)
    if not t:
        raise HTTPException(404, "해당 테마 없음")
    return t


@router.get("/future-themes/status")
def future_themes_status():
    """미래 성장테마 백그라운드 스케줄러 상태 + 저장된 스냅샷 날짜."""
    return growth_scheduler.status()


@router.get("/future-themes/dates")
def future_themes_dates():
    """누적 저장된 미래 성장테마 스냅샷 날짜(최신순)."""
    return {"dates": futuretheme.list_dates()}


@router.post("/future-themes/refresh")
def future_themes_refresh():
    """미래 성장테마를 지금 즉시 재크롤(뉴스+매핑)하고 스냅샷 저장."""
    futuretheme.themes(force=True)
    return futuretheme.snapshot(force=True)
