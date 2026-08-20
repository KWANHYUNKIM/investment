"""관심종목·보유·자산계획 — 사용자가 직접 만드는 투자 데이터."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, ForeignKey, Integer, Numeric,
                        SmallInteger, String, Text, UniqueConstraint, text)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (SCHEMA_IDENTITY, SCHEMA_PORTFOLIO, Base, TimestampMixin,
                         VersionMixin, pk)

_USER_FK = f"{SCHEMA_IDENTITY}.app_user.id"


class WatchItem(Base, TimestampMixin):
    __tablename__ = "watch_item"
    __table_args__ = (
        UniqueConstraint("user_id", "market", "ticker", name="uq_watch_item_user_id_market_ticker"),
        {"schema": SCHEMA_PORTFOLIO},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)      # KR|US
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text)


class Holding(Base, TimestampMixin, VersionMixin):
    """보유 종목. 수량·단가를 사람이 직접 고치므로 낙관적 잠금을 켠다."""

    __tablename__ = "holding"
    __table_args__ = (
        UniqueConstraint("user_id", "market", "ticker", name="uq_holding_user_id_market_ticker"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("avg_price >= 0", name="avg_price_non_negative"),
        {"schema": SCHEMA_PORTFOLIO},
    )
    __mapper_args__ = {"version_id_col": VersionMixin.version_id}

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    # 소수점 주식(해외)이 있어 수량도 NUMERIC. 정수로 두면 0.3주가 0 이 된다.
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False,
                                      server_default=text("'KRW'"))


class WealthProfile(Base, TimestampMixin, VersionMixin):
    """재테크 로드맵 입력값. 나이·결혼여부로 **자격 상품이 갈리므로** 개인정보에 가깝다."""

    __tablename__ = "wealth_profile"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_wealth_profile_user_id"),
        {"schema": SCHEMA_PORTFOLIO},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    age: Mapped[int | None] = mapped_column(SmallInteger)
    married: Mapped[bool | None] = mapped_column(Boolean)
    homeless: Mapped[bool | None] = mapped_column(Boolean)      # 무주택 여부(청약 자격)
    has_child: Mapped[bool | None] = mapped_column(Boolean)
    annual_income: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    monthly_saving: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    current_assets: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    goal_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    goal_years: Mapped[int | None] = mapped_column(SmallInteger)
    holdings_horizon: Mapped[int | None] = mapped_column(Integer)


__all__ = ["Holding", "WatchItem", "WealthProfile"]
