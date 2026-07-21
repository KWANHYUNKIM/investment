"""관리자 전용 API — 블로그 생성·콘텐츠 큐레이션·사용자/데이터 관리·방문자 통계.

모든 엔드포인트는 require_admin(관리자 계정)만 접근 가능. 방문자 추적(POST /api/track)은
로그인 사용자 누구나 보낼 수 있어 별도 공개 라우터(track_router)로 둔다.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core import auth
from app.core.auth import require_admin, require_auth
from app.data.admin import blog, stats, curation
from app.data.infra import store
from app.data.schedulers import price_scheduler, report_scheduler
from app.data.fundamentals import dart_financials, fundamentals_crawler

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/blog/generate")
def blog_generate(kind: str = Body(...), ticker: str = Body(default=""),
                  title: str = Body(default=""), body: str = Body(default=""),
                  _: str = Depends(require_admin)):
    """대시보드 분석을 블로그용 글(마크다운+HTML)로 생성. kind: dividend-stock/
    daily-report/crisis-survivors/etf/royalty/custom."""
    return blog.generate(kind, {"ticker": ticker, "title": title, "body": body})


@router.get("/users")
def users(_: str = Depends(require_admin)):
    return {"users": auth.list_users(), "admins": sorted(auth.admin_users())}


@router.get("/status")
def status(_: str = Depends(require_admin)):
    """운영 대시보드 — 데이터 커버리지 + 백그라운드 스케줄러 상태."""
    try:
        cov = store.coverage().to_dict(orient="records")
    except Exception:
        cov = []
    return {
        "coverage": cov,
        "price_scheduler": _safe(price_scheduler.status),
        "report_scheduler": _safe(report_scheduler.status),
        "fundamentals_crawler": _safe(fundamentals_crawler.status),
        "dart_enabled": dart_financials.enabled(),
    }


def _safe(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:120]}


@router.get("/stats")
def visitor_stats(_: str = Depends(require_admin)):
    return stats.summary()


@router.get("/curation")
def curation_get(_: str = Depends(require_admin)):
    return curation.get()


@router.post("/curation")
def curation_set(headline: str = Body(default=""), picks: list = Body(default=[]),
                 note: str = Body(default=""), _: str = Depends(require_admin)):
    return curation.set_(headline, picks, note)


# ── 공개(로그인 사용자) 방문자 추적 ───────────────────────────────────────
track_router = APIRouter(prefix="/api", tags=["track"])


@track_router.post("/track")
def track(view: str = Body(..., embed=True), user: str = Depends(require_auth)):
    stats.track(view, user)
    return {"ok": True}
