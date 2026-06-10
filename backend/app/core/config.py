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

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "market.duckdb"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
