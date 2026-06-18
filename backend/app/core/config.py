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

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "market.duckdb"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "daily_reports"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
