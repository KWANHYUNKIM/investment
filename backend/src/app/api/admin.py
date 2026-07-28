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


@router.post("/blog/publish")
def blog_publish(date: str = Body(default=""), force: bool = Body(default=True),
                 _: str = Depends(require_admin)):
    """오늘(또는 지정일) **증시 보고서**를 만들어 data/blog_posts/ 에 저장한다.

    스케줄러(평일 16:20 자동 발행)와 같은 경로. force=false 면 이미 있는 글을 재사용.
    """
    return blog.publish_market_wrap(date or None, force=force)


@router.get("/blog/posts")
def blog_posts(limit: int = 60, _: str = Depends(require_admin)):
    """저장된 블로그 글 목록(본문 제외, 최신순)."""
    from app.data.admin import blog_archive
    return {"posts": blog_archive.listing(limit), "dir": str(blog_archive.dir_path())}


@router.get("/blog/post")
def blog_post(date: str = "", kind: str = "market-wrap", _: str = Depends(require_admin)):
    """저장된 글 1편(마크다운·HTML 포함). date 를 비우면 가장 최근 글."""
    from app.data.admin import blog_archive
    got = blog_archive.load(date, kind) if date else blog_archive.latest(kind)
    if not got:
        return {"available": False, "reason": "저장된 글이 없습니다. 발행을 먼저 하세요."}
    return {"available": True, **got}


@router.get("/blog/scheduler")
def blog_scheduler_status(_: str = Depends(require_admin)):
    """자동 발행 스케줄러 상태(언제 도는지·마지막 글)."""
    from app.data.schedulers import blog_scheduler
    return blog_scheduler.status()


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
