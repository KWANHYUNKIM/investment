"""FastAPI application entry point.

Run from the backend/ directory:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, backtest, crisis, data, portfolio, screening
from app.api import admin
from app.core.auth import require_auth
from app.core.config import get_settings
from app.data.fundamentals import fundamentals_crawler
from app.data.schedulers import costmodel_scheduler
from app.data.schedulers import growth_scheduler
from app.data.schedulers import industry_scheduler
from app.data.schedulers import premarket_scheduler
from app.data.schedulers import movers_scheduler
from app.data.schedulers import price_scheduler
from app.data.schedulers import realestate_scheduler
from app.data.schedulers import report_scheduler
from app.data.infra import store
from app.data.market import crisis as crisis_data

settings = get_settings()

app = FastAPI(
    title="Quant Investment API",
    version="0.1.0",
    description="Screening · Backtesting · Portfolio construction for KR/US equities",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    store.init_db()
    # Background fundamentals crawler (same process → shares the DuckDB writer,
    # no lock conflicts). Stores a snapshot only when values change.
    fundamentals_crawler.start()
    # Background price scheduler: periodically accumulate today's OHLCV bar for
    # the whole KR board into DuckDB (same process → same writer connection).
    price_scheduler.start()
    # Background report scheduler: persist the full daily report as JSON once per
    # trading day so the 데일리 리포트 history accumulates instead of evaporating.
    report_scheduler.start()
    # Background industry scheduler: refresh KRX-DESC industry profiles and snapshot
    # the per-industry competition/research feed so it accumulates over time.
    industry_scheduler.start()
    # Background growth scheduler: keep the news-driven feeds (미래 성장테마·실시간 시황)
    # continuously crawled/warmed and snapshot the future-theme picture daily.
    growth_scheduler.start()
    # 금융위기 시뮬레이터: 필요한 FRED 시계열을 백그라운드에서 천천히 받아 디스크 캐시에
    # 저장(throttle 회피). 이후 /api/crisis/sim 은 캐시에서 즉시 응답한다.
    crisis_data.start()
    # 개장 예측 스케줄러: 매 세션 예측을 저장하고 다음 세션 실제 개장과 대조해 채점(반복).
    premarket_scheduler.start()
    # 급등락 원인 규명 스케줄러: 급등/급락 종목·업종을 감지하고 뉴스(+선택 AI)로 원인을
    # 규명해 이력에 기록(자동 반복).
    movers_scheduler.start()
    # 부동산 지도 프리워밍: 국토부 실거래(최신월)+시군구 좌표를 서버 시작 시 미리 받아
    # 디스크 캐시에 채워둔다. 이후 부동산 지도 탭은 캐시에서 즉시 렌더(수집 대기 사라짐).
    realestate_scheduler.start()
    # 원가모델 전 종목 배치: 매일 야간 1회 company_costmodels.json 을 갱신해
    # 원가분석 목록이 추정 대신 DART 실측으로 뜨게 한다(장중 부하·rate limit 회피).
    costmodel_scheduler.start()


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "data_dir": str(settings.data_dir.resolve())}


# 인증 라우터는 공개(로그인 전 접근). /api/health(@app.get)도 공개.
app.include_router(auth.router)

# 나머지 데이터 API는 전부 로그인 필요(외부망 노출 대비).
_protected = [Depends(require_auth)]
app.include_router(data.router, dependencies=_protected)
app.include_router(crisis.router, dependencies=_protected)
app.include_router(screening.router, dependencies=_protected)
app.include_router(backtest.router, dependencies=_protected)
app.include_router(portfolio.router, dependencies=_protected)
# 관리자 라우터(엔드포인트별 require_admin) + 방문자 추적(require_auth) 공개 라우터.
app.include_router(admin.router)
app.include_router(admin.track_router)
