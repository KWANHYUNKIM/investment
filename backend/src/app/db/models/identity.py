"""계정·자격증명·감사 — 가장 보수적으로 설계하는 구획.

비밀번호 해시를 ``app_user`` 에 같이 두지 않는다. 사용자 목록을 읽는 화면·배치는
많지만 해시를 읽어야 하는 곳은 로그인 하나뿐이라, **테이블을 갈라 두면 권한도 갈린다**
(``GRANT SELECT ON identity.app_user`` 만 주면 해시는 애초에 닿지 않는다). 지금
``auth.json`` 은 둘이 한 덩어리라 그 구분이 불가능하다.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (CheckConstraint, ForeignKey, Index, Integer, LargeBinary,
                        String, func, text)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (SCHEMA_IDENTITY, ActorMixin, Base, TimestampMixin,
                         TZDateTime, VersionMixin, pk)


class AppUser(Base, TimestampMixin, ActorMixin, VersionMixin):
    """계정. ``user`` 는 예약어라 ``app_user`` 로 둔다."""

    __tablename__ = "app_user"
    __table_args__ = (
        # 대소문자만 다른 아이디로 가입하는 걸 막는다. 앱에서만 소문자화하면
        # psql·배치로 넣은 행이 규칙을 빠져나간다 — 규칙은 DB 에 둬야 예외가 없다.
        Index("uq_app_user_username_lower", func.lower(text("username")), unique=True),
        CheckConstraint("status IN ('active','locked','disabled')", name="status"),
        {"schema": SCHEMA_IDENTITY},
    )

    id: Mapped[int] = pk()
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(64))
    # 삭제 대신 상태로 둔다 — 지워 버리면 그 사람의 거래·감사기록이 고아가 된다.
    status: Mapped[str] = mapped_column(String(16), nullable=False,
                                    server_default=text("'active'"))
    last_login_at: Mapped[dt.datetime | None] = mapped_column(TZDateTime)

    credential: Mapped[UserCredential | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserCredential(Base, TimestampMixin):
    """비밀번호 해시. 알고리즘을 컬럼으로 들고 있어야 **나중에 갈아탈 수 있다.**

    지금은 PBKDF2 지만 언젠가 argon2 로 옮길 때, 알고리즘 컬럼이 없으면 전 사용자를
    한 번에 재설정시켜야 한다. 있으면 로그인 성공 시점에 조용히 재해시하면 된다.
    """

    __tablename__ = "user_credential"
    __table_args__ = (
        CheckConstraint("iterations > 0", name="iterations_positive"),
        {"schema": SCHEMA_IDENTITY},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_IDENTITY}.app_user.id", ondelete="CASCADE"),
        nullable=False, unique=True)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False,
                                       server_default=text("'pbkdf2_sha256'"))
    iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    # bytea 로 둔다. hex 문자열로 두면 길이가 두 배가 되고, 비교할 때 인코딩 실수가 난다.
    salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    password_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    rotated_at: Mapped[dt.datetime | None] = mapped_column(TZDateTime)

    user: Mapped[AppUser] = relationship(back_populates="credential")


class EmailVerification(Base, TimestampMixin):
    """가입·비밀번호 재설정 인증코드. 만료와 사용여부를 **행에** 남긴다 —
    메모리에 두면 서버를 내릴 때마다 사용자가 코드를 다시 받아야 한다."""

    __tablename__ = "email_verification"
    __table_args__ = (
        Index("ix_email_verification_email_expires", "email", "expires_at"),
        {"schema": SCHEMA_IDENTITY},
    )

    id: Mapped[int] = pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)   # 코드도 평문 저장 안 한다
    expires_at: Mapped[dt.datetime] = mapped_column(TZDateTime, nullable=False)
    consumed_at: Mapped[dt.datetime | None] = mapped_column(TZDateTime)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class AuditEvent(Base):
    """무슨 일이 있었나 — **추가만 되는 표**.

    UPDATE·DELETE 를 안 하는 게 요점이다. 사고 조사에서 감사기록 자체가 고쳐질 수
    있으면 아무것도 증명하지 못한다. 운영에서는 이 표에 INSERT 권한만 준다.

    ``payload`` 를 JSONB 로 둔 건 도메인마다 남길 것이 다르기 때문이다. 대신 검색에
    쓰는 값(actor·action·entity)은 정규 컬럼으로 빼서 인덱스를 건다.
    """

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_occurred_at", "occurred_at"),
        Index("ix_audit_event_actor_occurred", "actor", "occurred_at"),
        Index("ix_audit_event_entity", "entity_type", "entity_id"),
        {"schema": SCHEMA_IDENTITY},
    )

    id: Mapped[int] = pk()
    occurred_at: Mapped[dt.datetime] = mapped_column(
        TZDateTime, nullable=False, server_default=func.now())
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(INET)
    payload: Mapped[dict | None] = mapped_column(JSONB)


__all__ = ["AppUser", "AuditEvent", "EmailVerification", "UserCredential"]
