"""부동산 — 지역 기준정보 · 월별 실거래 집계 · 검색 관심도.

지금 파일 세 개(``realestate_region_stats.json`` 등)에 흩어져 있는데, 셋이 **같은
지역·같은 달** 을 가리키면서 서로 못 조인한다. 화면에서 '검색은 올랐는데 거래는 아직'
을 뽑을 때마다 파이썬에서 dict 를 맞붙이고 있다.

표로 두면 그 질문이 SQL 한 줄이 된다. 성능보다 이게 크다 — 조인을 코드로 하면 조건이
하나 늘 때마다 코드가 늘지만, SQL 은 WHERE 절 하나다.

집계 셀에 ``fetched_at`` 을 남기는 게 중요하다. data.go.kr 은 하루 1,000건 한도라
'무엇을 다시 받을지' 를 정확히 골라야 하는데, 그 판단의 근거가 이 컬럼이다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, Date, ForeignKey, Index, Integer,
                        Numeric, String, UniqueConstraint, text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import SCHEMA_REALESTATE, Base, TimestampMixin, TZDateTime, pk


class Region(Base, TimestampMixin):
    """시군구. 법정동코드 5자리(LAWD)가 자연키다."""

    __tablename__ = "region"
    __table_args__ = (
        UniqueConstraint("lawd_cd", name="uq_region_lawd_cd"),
        {"schema": SCHEMA_REALESTATE},
    )

    id: Mapped[int] = pk()
    lawd_cd: Mapped[str] = mapped_column(String(5), nullable=False)
    sido: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    # 좌표를 어떻게 얻었나. 시도중심 근사인지 실제 지오코딩인지 화면이 구분해 보여준다.
    geocode_source: Mapped[str | None] = mapped_column(String(16))   # osm|ncp|approx


class RegionMonthStat(Base, TimestampMixin):
    """시군구 × 월 × 거래유형 집계.

    금액의 뜻이 거래유형마다 다르다 — 매매는 거래가, 전세·월세는 보증금. 월세만
    ``avg_monthly_rent`` 가 붙는다. 한 컬럼에 뭉개면 평균이 무의미해진다.
    """

    __tablename__ = "region_month_stat"
    __table_args__ = (
        UniqueConstraint("region_id", "year_month", "trade_type",
                         name="uq_region_month_stat_region_id_year_month_trade_type"),
        # 화면의 주 질의: 이 지역의 이 거래유형 시계열.
        Index("ix_region_month_stat_region_trade_month", "region_id", "trade_type", "year_month"),
        CheckConstraint("trade_type IN ('sale','jeonse','wolse')", name="trade_type"),
        CheckConstraint("deal_count >= 0", name="deal_count_non_negative"),
        {"schema": SCHEMA_REALESTATE},
    )

    id: Mapped[int] = pk()
    region_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_REALESTATE}.region.id", ondelete="CASCADE"), nullable=False)
    year_month: Mapped[str] = mapped_column(String(6), nullable=False)      # YYYYMM
    trade_type: Mapped[str] = mapped_column(String(8), nullable=False)

    deal_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))    # 억
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))       # 억
    avg_monthly_rent: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # 만원(월세만)

    # 신고 기한(계약 후 30일)이 남은 달인지. 화면이 '잠정치' 라고 적어야 오독을 막는다.
    is_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                             server_default=text("false"))
    # 언제 받았나 — 한도 안에서 '무엇을 다시 받을지' 를 정하는 근거.
    fetched_at: Mapped[dt.datetime] = mapped_column(TZDateTime, nullable=False)

    area_stats: Mapped[list[RegionMonthAreaStat]] = relationship(
        back_populates="month_stat", cascade="all, delete-orphan")


class RegionMonthAreaStat(Base):
    """평형별 세부. 부모 셀과 1:N 이라 따로 둔다 — 평형 구간이 바뀌어도 부모는 안 흔들린다."""

    __tablename__ = "region_month_area_stat"
    __table_args__ = (
        UniqueConstraint("month_stat_id", "area_bucket",
                         name="uq_region_month_area_stat_month_stat_id_area_bucket"),
        {"schema": SCHEMA_REALESTATE},
    )

    id: Mapped[int] = pk()
    month_stat_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_REALESTATE}.region_month_stat.id", ondelete="CASCADE"),
        nullable=False)
    area_bucket: Mapped[str] = mapped_column(String(16), nullable=False)   # '60~85' 등
    deal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    month_stat: Mapped[RegionMonthStat] = relationship(back_populates="area_stats")


class RegionCommerce(Base, TimestampMixin):
    """시군구 × 업종대분류 점포 수 — 상권 규모와 **성격**을 함께 담는다.

    왜 업종별로 나눠 담는가: 점포 총수만으로는 "사람이 많은 곳" 밖에 모른다. 업종
    구성을 보면 **그 동네가 무엇을 하는 곳인지**가 나온다. 실측으로 확인했다 —
    (과학기술+시설관리)/(교육+보건의료+수리개인) 이 종로 1.74 · 강남 1.69 ·
    마포 1.27 · 강서 0.83 · 분당 0.61 · 노원 0.36 으로, 업무지역부터 순수 주거지역까지
    한 줄로 늘어선다.

    비율·지수는 저장하지 않는다. 전부 이 표에서 나오는 값이라 계산이 정답이고,
    분류 기준을 바꿀 때마다 다시 채워 넣을 이유가 없다.
    """

    __tablename__ = "region_commerce"
    __table_args__ = (
        UniqueConstraint("region_id", "category_code",
                         name="uq_region_commerce_region_id_category_code"),
        Index("ix_region_commerce_region", "region_id"),
        CheckConstraint("store_count >= 0", name="store_count_non_negative"),
        {"schema": SCHEMA_REALESTATE},
    )

    id: Mapped[int] = pk()
    region_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_REALESTATE}.region.id", ondelete="CASCADE"), nullable=False)
    category_code: Mapped[str] = mapped_column(String(4), nullable=False)   # G2·I2·M1…
    category_name: Mapped[str] = mapped_column(String(32), nullable=False)
    store_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # 원본이 분기 갱신이라 '언제 받은 값인가' 가 곧 신선도다.
    fetched_at: Mapped[dt.datetime] = mapped_column(TZDateTime, nullable=False)


class InterestRun(Base, TimestampMixin):
    """관심도 수집 한 번. **앵커가 무엇이었는지** 를 남기는 게 핵심이다.

    관심도 값은 '앵커 대비 배수' 라 앵커가 바뀌면 축이 통째로 달라진다. 실행 정보를
    안 남기면 지난달 값과 이번달 값을 비교할 수 있는지조차 알 수 없게 된다.
    """

    __tablename__ = "interest_run"
    __table_args__ = {"schema": SCHEMA_REALESTATE}

    id: Mapped[int] = pk()
    anchor_keyword: Mapped[str] = mapped_column(String(64), nullable=False)
    time_unit: Mapped[str] = mapped_column(String(8), nullable=False,
                                       server_default=text("'month'"))
    period_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    region_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source: Mapped[str] = mapped_column(String(32), nullable=False,
                                    server_default=text("'naver_api_hub'"))

    points: Mapped[list[InterestPoint]] = relationship(
        back_populates="run", cascade="all, delete-orphan")


class InterestPoint(Base):
    """지역 × 기간의 관심도 한 점."""

    __tablename__ = "interest_point"
    __table_args__ = (
        UniqueConstraint("run_id", "region_id", "period",
                         name="uq_interest_point_run_id_region_id_period"),
        Index("ix_interest_point_region_period", "region_id", "period"),
        {"schema": SCHEMA_REALESTATE},
    )

    id: Mapped[int] = pk()
    run_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_REALESTATE}.interest_run.id", ondelete="CASCADE"), nullable=False)
    region_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_REALESTATE}.region.id", ondelete="CASCADE"), nullable=False)
    period: Mapped[dt.date] = mapped_column(Date, nullable=False)
    keyword: Mapped[str] = mapped_column(String(64), nullable=False)
    # 앵커 대비 배수. 절대 검색량이 아니다 — 이름으로 그 사실을 드러낸다.
    ratio_to_anchor: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)

    run: Mapped[InterestRun] = relationship(back_populates="points")


__all__ = ["InterestPoint", "InterestRun", "Region", "RegionCommerce",
           "RegionMonthAreaStat", "RegionMonthStat"]
