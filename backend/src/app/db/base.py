"""ORM 토대 — 명명 규칙 · 공통 컬럼 · 스키마 구획.

여기서 정한 세 가지가 이후 모든 테이블을 지배한다. 나중에 바꾸려면 마이그레이션을
전부 다시 써야 하므로 처음에 못박는다.

1) 제약조건 이름을 **자동으로 짓는다**
   Alembic 이 제약을 지우거나 바꾸려면 이름으로 찾아야 하는데, 이름을 DB 가 알아서
   붙이게 두면 환경마다 달라진다(로컬은 ``users_email_key``, 운영은 ``users_email_key1``).
   그러면 운영에서만 마이그레이션이 실패한다. SQLAlchemy 의 ``naming_convention`` 으로
   규칙을 고정해 두면 어디서 만들든 같은 이름이 나온다.

2) 도메인마다 **스키마를 나눈다**
   ``public`` 하나에 60개 테이블을 쏟으면 경계가 사라진다. 가계부 테이블과 시장데이터
   테이블은 수명도 접근권한도 다르므로 물리적으로 갈라 둔다. 권한을 스키마 단위로
   줄 수 있게 되는 것이 실질적인 이득이다 — 배치 계정에 ``budget`` 을 통째로 안 주면 된다.

3) 모든 테이블이 **언제·누가**를 갖는다
   장애를 추적할 때 가장 먼저 묻는 게 그것이다. 나중에 붙이면 과거 행은 영영 비어 있다.

돈은 절대 float 로 두지 않는다(``Money``). 지금 JSON 저장소가 float 를 쓰고 있는데,
0.1 + 0.2 != 0.3 인 세계에서 합계를 반복하면 원 단위가 조용히 어긋난다. 금융 데이터에서
이건 버그가 아니라 사고다.
"""
from __future__ import annotations

import datetime as dt
from typing import Annotated

from sqlalchemy import BigInteger, DateTime, MetaData, Numeric, String, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# --- 스키마(바운디드 컨텍스트) ------------------------------------------------
# 도메인 경계를 DB 에도 그대로 새긴다. 애플리케이션에서만 나눠 두면 시간이 지나면서
# 조인 한 줄로 경계가 무너진다.
SCHEMA_IDENTITY = "identity"      # 계정·자격증명·감사
SCHEMA_BUDGET = "budget"          # 가계부(개인 금융 — 가장 민감)
SCHEMA_PORTFOLIO = "portfolio"    # 관심종목·보유·자산계획
SCHEMA_MARKET = "market"          # 종목·기업 기준정보(참조 데이터)
SCHEMA_REALESTATE = "realestate"  # 지역·실거래·검색관심도
SCHEMA_OPS = "ops"                # 배치 이력·쿼터·방문통계

ALL_SCHEMAS = (
    SCHEMA_IDENTITY, SCHEMA_BUDGET, SCHEMA_PORTFOLIO,
    SCHEMA_MARKET, SCHEMA_REALESTATE, SCHEMA_OPS,
)

# --- 명명 규칙 ---------------------------------------------------------------
# ix_/uq_/ck_/fk_/pk_ 접두사는 psql 목록에서 종류가 한눈에 갈리게 한다.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=NAMING_CONVENTION)


# --- 공통 타입 ---------------------------------------------------------------
# 돈: 원 단위 정수도 담을 수 있게 소수 2자리. 18자리면 1경까지 들어간다.
Money = Annotated[float, mapped_column(Numeric(18, 2))]
# 비율·지수: 계산용이라 부동소수로 충분하다(합계를 누적하지 않는다).
Ratio = Annotated[float, mapped_column(Numeric(12, 6))]

# 시각은 예외 없이 timestamptz. naive datetime 을 허용하면 서버 시간대가 바뀌는 순간
# 과거 데이터의 의미가 통째로 달라진다.
TZDateTime = DateTime(timezone=True)


class Base(DeclarativeBase):
    metadata = metadata_obj


class TimestampMixin:
    """생성·수정 시각. DB 기본값으로 둬야 배치·psql 로 넣은 행도 빠지지 않는다."""

    created_at: Mapped[dt.datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ActorMixin:
    """누가 만들었나. 사람이 아닌 배치도 주체이므로 문자열로 둔다('scheduler:blog')."""

    created_by: Mapped[str] = mapped_column(String(64), nullable=False,
                                            server_default=text("'system'"))


class VersionMixin:
    """낙관적 잠금용 컬럼. 두 화면이 같은 행을 고칠 때 나중 저장이 앞 저장을 조용히
    덮는 것을 막는다 — 가계부·보유종목처럼 사람이 직접 고치는 표에서 실제로 일어난다.

    컬럼만 여기서 주고, 실제로 켜는 건 모델이 한다::

        class Holding(Base, VersionMixin):
            __mapper_args__ = {"version_id_col": VersionMixin.version_id}

    믹스인에서 일괄로 켜지 않는 이유는, 배치가 대량 UPSERT 하는 표에서는 버전 충돌이
    이득 없이 실패만 늘리기 때문이다.
    """

    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                            server_default=text("1"))


def pk() -> Mapped[int]:
    """대리키. 자연키(티커·지문 등)는 UNIQUE 로 따로 건다.

    자연키를 PK 로 쓰면 그 값이 바뀌는 날(카드사가 가맹점명을 바꾸는 날) 참조하는
    모든 테이블이 함께 흔들린다. 대리키는 그 사건과 무관하다.
    """
    return mapped_column(BigInteger, primary_key=True, autoincrement=True)
