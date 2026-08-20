"""종목·기업 기준정보 — **참조 데이터(dimension)** 만 둔다.

여기에 시세를 넣지 않는 게 이 설계의 의도적인 선택이다.

지금 DuckDB 에 있는 것: prices 437만 행, dart_financials 278만 행, investor_flow 13만,
fundamentals 4.5만. 이건 **분석 워크로드**다 — 한 종목의 10년치를 통째로 스캔하고,
전 종목을 훑어 순위를 매긴다. 컬럼 지향 엔진이 압도적으로 유리한 모양이고, DuckDB 는
이미 그 일을 잘 하고 있다. 굳이 PostgreSQL 로 옮기면 저장공간과 스캔 속도를 둘 다
잃으면서 얻는 게 없다.

반대로 종목명·업종·기업 프로파일은 **다른 표가 참조하는 기준값**이라 무결성이 필요하다.
관심종목이 존재하지 않는 티커를 가리키면 안 되고, 업종 분류는 화면 여러 곳이 같은 값을
봐야 한다. 그래서 이쪽만 PostgreSQL 로 온다.

이 구분을 문서 없이 두면 나중에 누군가 "왜 시세는 DB 에 없죠?" 하고 옮겨 버린다.
그래서 ``ops.dataset_snapshot`` 에 DuckDB 산출물의 계보를 남겨, 어디에 무엇이 있는지
DB 만 봐도 알 수 있게 한다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (Date, ForeignKeyConstraint, Index, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import SCHEMA_MARKET, Base, TimestampMixin, pk


class Security(Base, TimestampMixin):
    """상장 종목. (market, ticker) 가 자연키다."""

    __tablename__ = "security"
    __table_args__ = (
        UniqueConstraint("market", "ticker", name="uq_security_market_ticker"),
        Index("ix_security_name", "name"),
        {"schema": SCHEMA_MARKET},
    )

    id: Mapped[int] = pk()
    market: Mapped[str] = mapped_column(String(8), nullable=False)     # KR|US
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(64))
    wics_sector: Mapped[str | None] = mapped_column(String(64))
    # 관리종목·투자주의 등 시장경보 구분. 상폐 스크리너가 이 값 없이는 절반이 꺼진다.
    board: Mapped[str | None] = mapped_column(String(32))              # KOSPI|KOSDAQ|KONEX
    department: Mapped[str | None] = mapped_column(String(64))         # 관리종목 등
    delisted_at: Mapped[dt.date | None] = mapped_column(Date)


class CompanyProfile(Base, TimestampMixin):
    """기업 개요. 종목당 한 행이라 security 와 1:1 이지만 표를 나눈다 —
    갱신 주기가 다르고(개요는 분기, 종목명은 상시), 컬럼이 넓어 스캔을 방해한다."""

    __tablename__ = "company_profile"
    __table_args__ = (
        ForeignKeyConstraint(["market", "ticker"],
                             [f"{SCHEMA_MARKET}.security.market",
                              f"{SCHEMA_MARKET}.security.ticker"],
                             ondelete="CASCADE",
                             name="fk_company_profile_security"),
        UniqueConstraint("market", "ticker", name="uq_company_profile_market_ticker"),
        {"schema": SCHEMA_MARKET},
    )

    id: Mapped[int] = pk()
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(128))
    products: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(64))
    # 공동대표는 한 칸에 여러 명과 직위 설명이 들어온다("A and B (individual
    # representative directors)" — 실측 67자). 사람 이름 폭이 아니라 자유서술 폭이다.
    representative: Mapped[str | None] = mapped_column(String(255))
    homepage: Mapped[str | None] = mapped_column(String(255))
    listing_date: Mapped[dt.date | None] = mapped_column(Date)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    corp_code: Mapped[str | None] = mapped_column(String(16))      # DART 고유번호


__all__ = ["CompanyProfile", "Security"]
