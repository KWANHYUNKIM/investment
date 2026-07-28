"""Themes HTTP routes — thin transport layer.

Each handler only delegates to the injected ``ThemesService`` and returns the
payload untyped. The single transport decision kept here is the legacy 404 for
an unknown theme key. Paths are unchanged from the legacy ``/api/data`` router
so this is a drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .deps import get_themes_service
from .service import ThemesService

router = APIRouter(prefix="/api/data", tags=["themes"])

Svc = Depends(get_themes_service)


@router.get("/future-themes")
def future_themes_endpoint(svc: ThemesService = Svc):
    """미래 성장테마 요약(좌측 목록) — 메가트렌드별 모멘텀·종목수·하락후보수."""
    return svc.index()


@router.get("/future-theme")
def future_theme_endpoint(key: str = Query(..., description="theme key"), svc: ThemesService = Svc):
    """한 테마 상세 — 뉴스 동향(무엇이 구축되나) + 매핑 종목(미래가치 후보 강조)."""
    t = svc.get(key)
    if not t:
        raise HTTPException(404, "해당 테마 없음")
    return t


@router.get("/future-themes/status")
def future_themes_status(svc: ThemesService = Svc):
    """미래 성장테마 백그라운드 스케줄러 상태 + 저장된 스냅샷 날짜."""
    return svc.scheduler_status()


@router.get("/future-themes/dates")
def future_themes_dates(svc: ThemesService = Svc):
    """누적 저장된 미래 성장테마 스냅샷 날짜(최신순)."""
    return svc.list_dates()


@router.post("/future-themes/refresh")
def future_themes_refresh(svc: ThemesService = Svc):
    """미래 성장테마를 지금 즉시 재크롤(뉴스+매핑)하고 스냅샷 저장."""
    return svc.refresh()
