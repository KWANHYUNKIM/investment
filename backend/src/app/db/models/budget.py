"""가계부 — 개인 금융. 이 저장소에서 가장 민감하고, 가장 자주 고쳐지는 데이터.

지금 ``budget_<계정>.json`` 한 파일에 거래·규칙·카드설정·업로드이력이 전부 들어 있다.
그걸 다섯 표로 가른다. 이유는 셋이다.

1. **금액이 float 였다.** 0.1 + 0.2 != 0.3 인 세계에서 6만 건을 더하면 원 단위가
   조용히 어긋난다. 전부 ``NUMERIC`` 으로 바꾼다 — 금융에서 이건 취향이 아니라 규칙이다.
2. **동시성.** 파일은 통째로 읽고 통째로 쓴다. 두 요청이 겹치면 나중 쓰기가 앞 쓰기를
   통째로 날린다. 지금은 프로세스 안 락으로 막고 있어 서버가 둘이 되는 순간 깨진다.
3. **부분 수정.** 거래 한 건을 고치려고 6만 건을 직렬화한다.

돈의 뜻을 컬럼 이름으로 구분하는 것도 그대로 옮긴다 — ``amount``(그 청구월에 실제로
빠지는 돈) · ``charged``(이번 회차 원금) · ``fee``(수수료) · ``total``(거래 전액).
이걸 하나로 합치면 할부가 있는 순간 지출 합계가 통장과 어긋난다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, Date, ForeignKey, Index, Integer,
                        Numeric, SmallInteger, String, Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (SCHEMA_BUDGET, SCHEMA_IDENTITY, ActorMixin, Base,
                         TimestampMixin, TZDateTime, VersionMixin, pk)

_USER_FK = f"{SCHEMA_IDENTITY}.app_user.id"


class Card(Base, TimestampMixin):
    """카드 한 장 + 결제 주기.

    청구월을 거래일에서 계산하려면 이용기간과 결제일이 필요하다. 지금은 JSON 안
    ``card_cycles`` dict 인데, 카드는 명세서·거래가 걸리는 **참조 대상**이라 표가 맞다.
    """

    __tablename__ = "card"
    __table_args__ = (
        UniqueConstraint("user_id", "card_key", name="uq_card_user_id_card_key"),
        CheckConstraint("cycle_start_day BETWEEN 1 AND 31", name="cycle_start_day_range"),
        CheckConstraint("cycle_end_day BETWEEN 1 AND 31", name="cycle_end_day_range"),
        CheckConstraint("pay_day BETWEEN 1 AND 31", name="pay_day_range"),
        {"schema": SCHEMA_BUDGET},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    # '신한카드 본인717' 처럼 명세서에서 뽑은 식별자. 사람이 바꿀 수 있어 자연키로만 쓴다.
    card_key: Mapped[str] = mapped_column(String(128), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(32))
    label: Mapped[str | None] = mapped_column(String(64))
    # 주기 설정은 없을 수 있다(사용자가 아직 안 넣음) — NULL 이면 명세서가 말한 청구월을 쓴다.
    cycle_start_day: Mapped[int | None] = mapped_column(SmallInteger)
    cycle_end_day: Mapped[int | None] = mapped_column(SmallInteger)
    pay_day: Mapped[int | None] = mapped_column(SmallInteger)
    pay_offset: Mapped[int | None] = mapped_column(SmallInteger)

    transactions: Mapped[list[Transaction]] = relationship(back_populates="card")


class ImportBatch(Base, TimestampMixin, ActorMixin):
    """명세서 업로드 한 번. 거래가 **어디서 왔는지** 를 남긴다.

    이게 있어야 '이 카드사 이 청구월 등록분만 되돌리기' 가 가능하다. 지금도 화면에
    그 기능이 있는데, 파일 저장소에서는 이력 목록을 최근 20건만 들고 있어 그 이전은
    되돌릴 수 없다.
    """

    __tablename__ = "import_batch"
    __table_args__ = (
        Index("ix_import_batch_user_created", "user_id", "created_at"),
        {"schema": SCHEMA_BUDGET},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False,
                                    server_default=text("'upload'"))  # upload|mail|paste
    filename: Mapped[str | None] = mapped_column(String(255))
    issuer: Mapped[str | None] = mapped_column(String(32))
    billing_month: Mapped[str | None] = mapped_column(String(7))     # YYYY-MM
    parsed_by: Mapped[str | None] = mapped_column(String(32))        # shinhan|lotte|generic…
    added_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # 원본 첨부를 어디 뒀는지. 파싱이 틀렸을 때 대조할 게 없으면 원인을 못 찾는다.
    stored_path: Mapped[str | None] = mapped_column(Text)

    transactions: Mapped[list[Transaction]] = relationship(back_populates="import_batch")


class Transaction(Base, TimestampMixin, VersionMixin):
    """거래 한 건. 이 표가 가계부의 사실상 전부다."""

    __tablename__ = "transaction"
    __table_args__ = (
        # 같은 명세서를 두 번 올리는 일이 흔하다(카드사가 확정본을 다시 내려준다).
        # 지문으로 막는데, **DB 제약으로** 둬야 두 요청이 동시에 들어와도 안 뚫린다.
        UniqueConstraint("user_id", "fingerprint", name="uq_transaction_user_id_fingerprint"),
        # 화면의 주 질의: 이 사람의 이 청구월 거래 전부.
        Index("ix_transaction_user_billing_month", "user_id", "billing_month"),
        # 거래일 기준 보기(캘린더)·기간 필터용.
        Index("ix_transaction_user_txn_date", "user_id", "txn_date"),
        # 가맹점 검색. 정규화 키로 걸어야 '스타벅스강남'·'스타벅스 강남점' 이 같이 잡힌다.
        Index("ix_transaction_user_merchant_key", "user_id", "merchant_key"),
        CheckConstraint("tx_type IN ('일시불','할부','현금서비스','해외','취소')", name="tx_type"),
        CheckConstraint(
            "(installment_months IS NULL) = (installment_seq IS NULL)",
            name="installment_pair"),
        {"schema": SCHEMA_BUDGET},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    card_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_BUDGET}.card.id", ondelete="SET NULL"))
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_BUDGET}.import_batch.id", ondelete="SET NULL"))

    txn_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    # 'YYYY-MM'. Date 로 두면 '월' 이라는 의미가 흐려지고, 1일로 저장하면 거래일과 헷갈린다.
    billing_month: Mapped[str] = mapped_column(String(7), nullable=False)
    billing_month_known: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                  server_default=text("true"))

    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_key: Mapped[str] = mapped_column(String(255), nullable=False)   # 지점 접미사 제거본

    # --- 돈. 전부 NUMERIC. 여기가 이 마이그레이션의 핵심이다. ---
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)   # 그 달 실제 지출
    charged: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # 이번 회차 원금
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)    # 거래 전액

    tx_type: Mapped[str] = mapped_column(String(16), nullable=False)
    installment_months: Mapped[int | None] = mapped_column(SmallInteger)
    installment_seq: Mapped[int | None] = mapped_column(SmallInteger)

    category_code: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA_BUDGET}.category.code", ondelete="SET NULL"))
    # 고정지출 여부는 판정 결과를 캐시한 것. 사용자가 못박으면 merchant_rule 이 이긴다.
    is_fixed: Mapped[bool | None] = mapped_column(Boolean)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(32))

    card: Mapped[Card | None] = relationship(back_populates="transactions")
    import_batch: Mapped[ImportBatch | None] = relationship(back_populates="transactions")


class Category(Base):
    """카테고리 기준값. 화면 드롭다운과 집계 축이 같은 목록을 봐야 한다."""

    __tablename__ = "category"
    __table_args__ = {"schema": SCHEMA_BUDGET}

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))


class MerchantRule(Base, TimestampMixin):
    """사용자가 못박은 규칙 — 자동 판정보다 **항상 우선**한다.

    자동 분류는 틀릴 수 있고, 틀렸을 때 사용자가 고친 것이 다음 수집에서 되돌아가면
    같은 수정을 매달 반복하게 된다. 그래서 규칙을 거래와 분리해 따로 남긴다.
    """

    __tablename__ = "merchant_rule"
    __table_args__ = (
        UniqueConstraint("user_id", "merchant_key", name="uq_merchant_rule_user_id_merchant_key"),
        {"schema": SCHEMA_BUDGET},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    merchant_key: Mapped[str] = mapped_column(String(255), nullable=False)
    category_code: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA_BUDGET}.category.code", ondelete="SET NULL"))
    is_fixed: Mapped[bool | None] = mapped_column(Boolean)


class IncomeProfile(Base, TimestampMixin, VersionMixin):
    """수입. **이력으로 둔다** — 지금은 값 하나를 덮어쓰고 있어 급여가 오르면 과거
    달의 저축률이 소급해 틀려진다."""

    __tablename__ = "income_profile"
    __table_args__ = (
        UniqueConstraint("user_id", "effective_from", name="uq_income_profile_user_id_effective_from"),
        {"schema": SCHEMA_BUDGET},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    monthly_net: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False,
                                             server_default=text("0"))
    extra: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default=text("0"))
    memo: Mapped[str | None] = mapped_column(Text)


class MailMessage(Base, TimestampMixin):
    """메일로 걷은 카드 명세서. 같은 메일을 두 번 처리하지 않기 위한 표.

    지금은 처리한 Message-ID 를 JSON 배열에 최근 1,000개만 들고 있다. 표로 두면
    잘라낼 이유가 없어지고, 왜 대기시켰는지도 행에 남는다.
    """

    __tablename__ = "mail_message"
    __table_args__ = (
        UniqueConstraint("user_id", "message_id", name="uq_mail_message_user_id_message_id"),
        Index("ix_mail_message_user_status", "user_id", "status"),
        CheckConstraint("status IN ('pending','imported','discarded','locked','skipped')",
                        name="status"),
        {"schema": SCHEMA_BUDGET},
    )

    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey(_USER_FK, ondelete="CASCADE"), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    sender: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[dt.datetime | None] = mapped_column(TZDateTime)
    status: Mapped[str] = mapped_column(String(16), nullable=False,
                                    server_default=text("'pending'"))
    reason: Mapped[str | None] = mapped_column(Text)          # 왜 자동 등록하지 않았나
    issuer: Mapped[str | None] = mapped_column(String(32))
    billing_month: Mapped[str | None] = mapped_column(String(7))
    filename: Mapped[str | None] = mapped_column(String(255))
    stored_path: Mapped[str | None] = mapped_column(Text)
    # 파싱 결과(거래 목록)를 승인 전까지 들고 있는 자리. 승인되면 transaction 으로 옮겨간다.
    parsed_payload: Mapped[dict | None] = mapped_column(JSONB)


__all__ = ["Card", "Category", "ImportBatch", "IncomeProfile", "MailMessage",
           "MerchantRule", "Transaction"]
