"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Directory holding the DuckDB file and parquet datasets.
    data_dir: Path = Path("../data")

    # Frontend dev origin allowed through CORS.
    frontend_origin: str = "http://localhost:3000"

    # Annual risk-free rate used in Sharpe / Sortino calculations.
    risk_free_rate: float = 0.03

    # DART (전자공시) open API key — enables 5% major-holder names by ticker.
    dart_api_key: str = ""

    # Finnhub (finnhub.io) free API key — enables 해외 종목 펀더멘털(영업이익률·시총·
    # 섹터·국가) for the 글로벌 경쟁지도. yfinance가 429로 막혀 그 대체 소스로 쓴다.
    finnhub_api_key: str = ""

    # 공공데이터포털(data.go.kr) 무료 키 — 국토부 아파트 매매 실거래가(RTMS).
    # 한국 경제 흐름 탭의 '부동산 거래액·거래량'(월별·지역별) 집계에 쓴다.
    data_go_kr_key: str = ""

    # 한국은행 ECOS 무료 키 — 거시 통화/신용/주택 지표(M2·가계신용·주택매매가격지수).
    # 한국 경제 흐름 탭의 '국내 돈 흐름' 하드데이터로 쓴다.
    ecos_api_key: str = ""

    # Anthropic Claude API 키 — 'AI 주가 예측' 탭에서 Claude Fable 5로 최근 시세를 넣고
    # 향후 주가 시나리오(강세/기준/약세) 경로를 예측한다. 없으면 예측 탭만 비활성.
    anthropic_api_key: str = ""

    # 이메일 인증(회원가입·비밀번호 찾기) 발송용 SMTP. 미설정이면 개발모드로
    # 코드를 응답에 노출(테스트용) — 외부 배포 전 반드시 설정할 것.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""   # 미설정 시 smtp_user 사용

    # 인증코드를 HTTP 응답에 노출할지(=SMTP 미설정 시 dev_code). 기본 False.
    # True 로 켜면 이메일 인증이 무력화되므로 로컬 개발에서만, 절대 공개 배포에선 금지.
    # (공개 URL 노출 시 누구나 send-code→reset-password 로 계정 탈취 가능)
    auth_expose_dev_code: bool = False

    # Demo mode: synthesize small intraday ticks on top of the settled snapshot
    # so the live grid visibly moves without a brokerage streaming API.
    mock_ticks: bool = True

    # Background price scheduler: periodically snapshot the whole KR board and
    # upsert today's OHLCV bar into DuckDB, so the price series accumulates
    # forward without a manual ingest run. Set PRICE_INGEST=false to disable.
    price_ingest: bool = True
    # Seconds between price snapshots (default 5 min). Intraday ticks refresh
    # today's bar in place; each new trading day appends a fresh row.
    price_ingest_interval: float = 300.0

    # Daily report archive: persist a full market + per-stock daily report as one
    # JSON file per trading day, so the history accumulates instead of evaporating
    # with the 10-min cache. Set REPORT_ARCHIVE=false to disable the snapshotter.
    report_archive: bool = True
    # How often the snapshotter wakes to check whether today's report exists yet
    # (it writes at most once per trading day). Default hourly.
    report_archive_interval: float = 3600.0
    # How many stocks get the deep news (국내+해외) + investor-cause analysis each
    # day. They are picked by trading significance (most-traded ∪ top gainers ∪ top
    # losers); every other stock is still archived at the price / investor-flow
    # level. Each deep stock costs a live domestic+global news fetch, so this is a
    # speed/coverage knob (≈0.4s/stock).
    report_deep_n: int = 100

    # Industry / competition map: refresh company industry profiles (KRX-DESC) and
    # snapshot per-industry research (tech/M&A/contracts/perf/strategy) on a daily
    # cadence so the competitive picture accumulates. Set INDUSTRY_MAP=false to off.
    industry_map: bool = True
    industry_map_interval: float = 6 * 3600.0  # how often the scheduler checks
    industry_top_k: int = 6        # companies analysed per industry (news fetch)
    industry_snapshot_n: int = 30  # industries persisted in each daily snapshot

    # 미래 성장테마 + 실시간 시황: 백그라운드로 주기적으로 뉴스를 다시 크롤링해 캐시를
    # 데우고, 미래 성장테마는 하루 1개 JSON으로 누적 저장한다. GROWTH_SCHEDULER=false로 끔.
    growth_scheduler: bool = True
    growth_scheduler_interval: float = 1800.0  # 30분마다 테마/시황 갱신

    # 개장 예측 아카이브: 매 세션 예측을 저장하고, 다음 세션 실제 개장과 대조해
    # 적중/실패를 채점한다(자동 반복). PREMARKET_ARCHIVE=false로 끔.
    premarket_archive: bool = True
    premarket_archive_interval: float = 1800.0  # 30분마다 기록·채점 점검

    # 급등락 원인 규명: 급등/급락 종목·업종을 감지하고 관련 뉴스(+선택 AI)로 원인을 찾아
    # 스냅샷을 주기적으로 기록(자동 반복). MOVERS=false로 끔.
    movers: bool = True
    movers_interval: float = 900.0        # 15분마다 감지·원인 규명·기록
    movers_threshold: float = 5.0         # |등락률| 이 % 이상이면 급등락으로 간주
    movers_top_n: int = 8                 # 원인(뉴스) 규명할 상위 급등·급락 종목 수

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "market.duckdb"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "daily_reports"

    @property
    def future_themes_dir(self) -> Path:
        return self.data_dir / "future_themes"

    @property
    def movers_dir(self) -> Path:
        return self.data_dir / "movers"

    @property
    def premarket_dir(self) -> Path:
        return self.data_dir / "premarket"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.future_themes_dir.mkdir(parents=True, exist_ok=True)
        self.premarket_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
