"""Ops 모니터링 — 백그라운드 스케줄러/크롤러 상태 + DB 저장 현황.

별도 포트의 모니터 대시보드(backend/ops_monitor.py)가 이 엔드포인트를 폴링한다.
DB 는 실행 중인 이 프로세스가 단독 writer 로 잠그므로, 저장 현황(테이블 카운트)은
반드시 여기(메인 백엔드) 안에서 조회해야 한다. 전역 auth 미적용(로컬 운영용) —
main.py 에서 _protected 없이 include.
"""
from __future__ import annotations

import os
import time

from fastapi import APIRouter

from app.core.config import get_settings
from app.data.infra import store
from app.data.fundamentals import fundamentals_crawler
from app.data.schedulers import (
    blog_scheduler, budget_mail_scheduler, commerce_scheduler,
    costmodel_scheduler, delisting_scheduler,
    growth_scheduler, industry_scheduler, movers_scheduler, premarket_scheduler,
    price_scheduler, realestate_scheduler, region_stats_scheduler,
    report_scheduler,
)

router = APIRouter(prefix="/api/ops", tags=["ops"])

# 표시 순서 = 데이터 저장량이 큰 것부터 대략. (name → 모듈, 한글 라벨)
_SCHEDULERS: list[tuple[str, object, str]] = [
    ("price", price_scheduler, "주가 OHLCV 수집"),
    ("fundamentals", fundamentals_crawler, "펀더멘털 크롤러"),
    ("industry", industry_scheduler, "업종·재무·해외 프로파일"),
    ("report", report_scheduler, "데일리 리포트 스냅샷"),
    ("costmodel", costmodel_scheduler, "원가모델 배치"),
    ("delisting", delisting_scheduler, "관리종목·상폐 스캔"),
    ("movers", movers_scheduler, "급등락 기록"),
    ("premarket", premarket_scheduler, "장전 예측"),
    ("growth", growth_scheduler, "성장테마·시황 피드"),
    ("realestate", realestate_scheduler, "부동산 실거래"),
    ("region_stats", region_stats_scheduler, "시군구 월별 집계(매매·전월세·평형)"),
    ("commerce", commerce_scheduler, "지역 상권(업종 구성·성격)"),
    ("blog", blog_scheduler, "블로그 자동발행"),
    ("budget_mail", budget_mail_scheduler, "가계부 메일 명세서 수집"),
]

# 어느 스케줄러가 어느 테이블에 쌓는지(대시보드에서 묶어 보여주기용)
_SCHED_TABLES: dict[str, list[str]] = {
    "price": ["prices"],
    "fundamentals": ["fundamentals", "investor_flow"],
    "industry": ["company_profile", "financials", "dart_financials", "foreign_fin"],
}


def _size(path: str) -> int | None:
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _table_counts() -> list[dict]:
    """모든 테이블의 행 수(저장량 큰 순)."""
    out: list[dict] = []
    with store.connection() as conn:
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        for t in tables:
            try:
                n = int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
            except Exception:
                n = None
            out.append({"table": t, "rows": n})
    return sorted(out, key=lambda x: -(x["rows"] or 0))


@router.get("/stats")
def ops_stats() -> dict:
    """스케줄러 상태 + 테이블 저장 현황 + DB 용량 (모니터 대시보드용)."""
    schedulers = []
    for name, mod, label in _SCHEDULERS:
        try:
            st = mod.status()  # type: ignore[attr-defined]
        except Exception as e:  # 개별 실패가 전체를 막지 않도록
            st = {"error": str(e)}
        schedulers.append({
            "name": name,
            "label": label,
            "tables": _SCHED_TABLES.get(name, []),
            "status": st,
        })

    settings = get_settings()
    dbp = str(settings.duckdb_path)
    return {
        "ts": time.time(),
        "db": {
            "path": dbp,
            "size_bytes": _size(dbp),
            "wal_bytes": _size(dbp + ".wal"),
            "max_price_date": store.max_price_date(),
        },
        "tables": _table_counts(),
        "schedulers": schedulers,
    }
