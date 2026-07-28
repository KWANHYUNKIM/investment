"""Market HTTP routes — thin transport layer.

Each handler only reads query params / auth and delegates to the injected
``MarketService``. Paths, params, docstrings and auth dependencies are
unchanged from the legacy ``app/api/data/market.py`` router so this is a
drop-in migration.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.auth import require_auth

from .deps import get_market_service
from .service import MarketService

router = APIRouter(prefix="/api/data", tags=["market"])

Svc = Depends(get_market_service)


@router.get("/cross-asset")
def cross_asset_endpoint(svc: MarketService = Svc):
    """Live cross-asset money-flow snapshot (미국·글로벌 증시 · 금 · 비트코인 · 환율).

    Grouped asset quotes + a risk-on/risk-off read. Cached ~60s so frontend
    polling refreshes without hammering the upstream (FinanceDataReader).
    """
    return svc.cross_asset()


@router.get("/asset-detail")
def asset_detail_endpoint(
    key: str = Query(..., description="cross-asset key, e.g. sp500/nasdaq/kospi/gold/btc"),
    date: str | None = Query(default=None, description="YYYY-MM-DD; 과거 날짜면 그날 장 마감으로 고정"),
    svc: MarketService = Svc,
):
    """장 마감 상세: 해당 지수/자산의 OHLC 세션 + 최근 시세 + 52주 고저 (+ 구성종목).

    ``date``를 주면 그 날짜까지로 시세를 잘라 그날 마감 시점으로 고정한다.
    """
    return svc.asset_detail(key, date)


@router.get("/asset-quotes")
def asset_quotes_endpoint(
    symbols: str = Query(..., description="comma-separated constituent symbols (max 60)"),
    date: str | None = Query(default=None, description="YYYY-MM-DD; 과거 날짜면 그날 종가로 고정"),
    svc: MarketService = Svc,
):
    """Batch quotes (현재가·등락·기간수익률) for index constituents — fills the grid lazily."""
    return svc.asset_quotes(symbols, date)


@router.get("/market-report")
def market_report_endpoint(svc: MarketService = Svc):
    """Market-wide daily report: movers, most-traded, investor sellers, news."""
    return svc.market_report()


@router.get("/live-pulse")
def live_pulse_endpoint(svc: MarketService = Svc):
    """실시간 시황 펄스 — 시황·전망·분석 글 취합 → 분위기·드라이버·시간순 흐름. 60초 캐시."""
    return svc.live_pulse()


@router.get("/institutional")
def institutional_endpoint(svc: MarketService = Svc):
    """기관 수급 추적 — 기관이 언제 담고 던졌나(매집/이탈 상위) + 왜 팔았을지 추정."""
    return svc.institutional()


@router.get("/money-flow")
def money_flow_endpoint(svc: MarketService = Svc):
    """글로벌 자금 흐름 — 유동성 레짐(완화/긴축)·한국 외국인 vs 국내 수급·크로스에셋·자산군별 자금 뉴스."""
    return svc.money_flow()


@router.get("/premarket")
def premarket_endpoint(svc: MarketService = Svc):
    """개장 예측 — 간밤 글로벌·연동 지표 + 한국 ADR + 코스피/코스닥 추세로 개장 방향 점수화(+선택적 Claude 서술)."""
    return svc.premarket()


@router.get("/premarket/history")
def premarket_history_endpoint(
    limit: int = Query(default=60, ge=1, le=200), svc: MarketService = Svc
):
    """개장 예측 성적표 — 과거 예측 vs 실제 개장 적중/실패·이유 + 누적 적중률."""
    return svc.premarket_history(limit)


@router.get("/target-price")
def target_price_endpoint(
    ticker: str = Query(..., description="single ticker"), svc: MarketService = Svc
):
    """종목 목표주가 — 정당PBR(ROE)·EPS×목표PER 적정주가 + 강세/기준/약세 시나리오(+선택 Claude)."""
    return svc.target_price(ticker)


@router.get("/signals")
def signals_endpoint(
    ticker: str = Query(..., description="single ticker"), svc: MarketService = Svc
):
    """매매 신호 — RSI·이평·MACD·볼린저·거래량 종합 매수/중립/매도 + ATR 손절·목표가·손익비 + 신호 백테스트."""
    return svc.signals(ticker)


@router.get("/stock-score")
def stock_score_endpoint(svc: MarketService = Svc):
    """종합 투자 점수 — 전 종목 가치·모멘텀·수급 백분위 종합 랭킹(TOP)."""
    return svc.stock_score()


@router.get("/briefing")
def briefing_endpoint(
    market: str = Query(default="auto"),
    user: str = Depends(require_auth),
    svc: MarketService = Svc,
):
    """장전 브리핑 — 전일 시장 스토리 요약 + 오늘 전망(한국/미국 자동 선택). 캐시 5분."""
    return svc.briefing(market)


@router.get("/movers")
def movers_endpoint(
    refresh: bool = Query(default=False),
    user: str = Depends(require_auth),
    svc: MarketService = Svc,
):
    """급등락 원인 규명 — 급등/급락 종목·업종 자동 감지 + 관련 뉴스(+선택 AI) 원인. 캐시 5분."""
    return svc.movers(refresh)


@router.get("/movers/history")
def movers_history_endpoint(
    limit: int = Query(default=50, ge=1, le=400),
    user: str = Depends(require_auth),
    svc: MarketService = Svc,
):
    """급등락 원인 이력 — 스케줄러가 주기적으로 기록한 급등락+원인 요약(시간 역순)."""
    return svc.movers_history(limit)
