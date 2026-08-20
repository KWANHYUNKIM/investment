"""운영 — 배치 이력 · 외부 API 쿼터 · 데이터 계보 · 방문통계.

이 구획이 있어야 "왜 어제 데이터가 안 들어왔지" 에 답할 수 있다. 지금은 스케줄러
상태가 **프로세스 메모리에만** 있어서 서버를 내리면 사라진다. 장애는 대개 재기동
뒤에 조사하므로, 그때 아무 기록도 없는 게 지금 구조의 가장 큰 구멍이다.

``api_quota_usage`` 는 실제로 겪은 문제에서 나왔다 — data.go.kr 하루 1,000건 한도를
넘겨 429 를 맞으면 그날 지도·전월세·집계가 한꺼번에 죽는데, 얼마나 썼는지 아무도
모르는 상태로 계속 두드리고 있었다.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (BigInteger, CheckConstraint, Date, Index, Integer, String,
                        Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import SCHEMA_OPS, Base, TimestampMixin, TZDateTime, pk


class BatchRun(Base):
    """배치 한 번의 실행 기록. 성공도 남긴다 — 실패만 남기면 '안 돌았다' 와
    '돌았는데 할 일이 없었다' 를 구분하지 못한다."""

    __tablename__ = "batch_run"
    __table_args__ = (
        Index("ix_batch_run_job_started", "job_name", "started_at"),
        CheckConstraint("status IN ('running','success','failed','skipped')", name="status"),
        {"schema": SCHEMA_OPS},
    )

    id: Mapped[int] = pk()
    job_name: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(TZDateTime, nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(TZDateTime)
    status: Mapped[str] = mapped_column(String(16), nullable=False,
                                    server_default=text("'running'"))
    items_processed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSONB)


class ApiQuotaUsage(Base):
    """외부 API 를 오늘 얼마나 썼나. 한도가 있는 공급자만 센다.

    (provider, usage_date) 로 UPSERT 한다 — 배치가 여러 개라도 같은 행을 올린다.
    """

    __tablename__ = "api_quota_usage"
    __table_args__ = (
        UniqueConstraint("provider", "usage_date", name="uq_api_quota_usage_provider_usage_date"),
        {"schema": SCHEMA_OPS},
    )

    id: Mapped[int] = pk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)   # data_go_kr|naver|dart…
    usage_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    call_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    error_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    daily_limit: Mapped[int | None] = mapped_column(BigInteger)
    last_error: Mapped[str | None] = mapped_column(Text)


class DatasetSnapshot(Base, TimestampMixin):
    """DB 밖(DuckDB·JSON·파케이)에 있는 산출물의 계보.

    시세·재무처럼 분석 워크로드는 DuckDB 에 남겨 두기로 했는데(``market`` 모듈 문서
    참고), 그러면 "지금 쓰는 데이터가 언제 만들어진 것인가" 를 물을 곳이 없어진다.
    파일 자체를 옮기지 않고 **어디에 무엇이 언제** 만 여기 남긴다.
    """

    __tablename__ = "dataset_snapshot"
    __table_args__ = (
        Index("ix_dataset_snapshot_name_built", "dataset_name", "built_at"),
        {"schema": SCHEMA_OPS},
    )

    id: Mapped[int] = pk()
    dataset_name: Mapped[str] = mapped_column(String(64), nullable=False)  # prices|dart_financials…
    storage: Mapped[str] = mapped_column(String(16), nullable=False)       # duckdb|json|parquet
    location: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    built_at: Mapped[dt.datetime] = mapped_column(TZDateTime, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))                 # pykrx|DART|RTMS…


class PageViewDaily(Base):
    """화면별 일자별 방문. 어떤 기능이 실제로 쓰이는지 없이는 무엇을 고칠지 못 정한다."""

    __tablename__ = "page_view_daily"
    __table_args__ = (
        UniqueConstraint("view_name", "view_date", name="uq_page_view_daily_view_name_view_date"),
        {"schema": SCHEMA_OPS},
    )

    id: Mapped[int] = pk()
    view_name: Mapped[str] = mapped_column(String(32), nullable=False)
    view_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    view_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


__all__ = ["ApiQuotaUsage", "BatchRun", "DatasetSnapshot", "PageViewDaily"]
