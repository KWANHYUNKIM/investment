"""스키마가 **실제로 지키는가** — PostgreSQL 에 붙여서 확인한다.

여기 있는 것들은 문서로 적어 두면 지켜지지 않는 종류의 규칙이다. 돈이 NUMERIC 인지,
남의 행이 정말 안 보이는지, 감사기록이 정말 못 고쳐지는지는 DB 에 물어봐야 안다.

DB 가 없으면 통째로 건너뛴다 — CI 에 Postgres 가 없다고 전체 테스트가 빨개지면
아무도 안 고치고 그냥 꺼 버린다.

    docker compose -f ops/postgres/docker-compose.yml up -d
    PYTHONPATH=src .venv/bin/python -m alembic upgrade head
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def conn():
    from sqlalchemy.exc import OperationalError

    from app.db.session import get_engine
    try:
        engine = get_engine()
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except (OperationalError, Exception) as e:  # noqa: BLE001
        pytest.skip(f"PostgreSQL 없음 — 건너뜀 ({type(e).__name__})")
    with engine.connect() as c:
        yield c


@pytest.fixture
def tx(conn):
    """각 테스트를 롤백한다 — 검증이 실제 데이터를 남기면 안 된다.

    역할 전환을 **트랜잭션 안에서** 한다. 접속 시점에 걸면 커넥션이 풀에서 재사용될 때
    풀려서, 검증은 통과하는데 실제로는 RLS 가 안 걸리는 상태가 된다(실제로 그랬다).
    """
    from app.core.config import get_settings

    trans = conn.begin()
    role = get_settings().db_app_role
    if role:
        conn.execute(text(f'SET LOCAL ROLE "{role}"'))
    yield conn
    trans.rollback()


# --- 돈 ---------------------------------------------------------------------
def test_money_columns_are_numeric_not_float(tx) -> None:
    """float 로 두면 6만 건을 더할 때 원 단위가 조용히 어긋난다. 금융에서 이건
    취향이 아니라 규칙이다 — 지금 JSON 저장소가 float 를 쓰고 있어 옮기는 게 목적이다."""
    rows = tx.execute(text("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema IN ('budget','portfolio','market','realestate')
          AND column_name ~ '(amount|price|income|saving|assets|total|charged|fee|rent|cap)'
          AND data_type IN ('double precision','real')
    """)).fetchall()
    assert rows == [], f"부동소수로 남은 금액 컬럼: {rows}"


def test_numeric_keeps_won_exactly(tx) -> None:
    """0.1 + 0.2 != 0.3 이 되는지 실제로 확인한다."""
    got = tx.execute(text(
        "SELECT (0.1::numeric + 0.2::numeric) = 0.3::numeric,"
        "       (0.1::float8 + 0.2::float8) = 0.3::float8")).one()
    assert got[0] is True and got[1] is False


# --- 시각 -------------------------------------------------------------------
def test_all_timestamps_carry_timezone(tx) -> None:
    """naive timestamp 를 허용하면 서버 시간대가 바뀌는 순간 과거 데이터의 의미가
    통째로 달라진다."""
    rows = tx.execute(text("""
        SELECT table_schema, table_name, column_name
        FROM information_schema.columns
        WHERE table_schema IN ('identity','budget','portfolio','market','realestate','ops')
          AND data_type = 'timestamp without time zone'
    """)).fetchall()
    assert rows == [], f"시간대 없는 컬럼: {rows}"


# --- 무결성 -----------------------------------------------------------------
def test_every_table_has_a_primary_key(tx) -> None:
    """PK 없는 표는 복제·업데이트·중복제거가 전부 어려워진다."""
    rows = tx.execute(text("""
        SELECT t.table_schema, t.table_name
        FROM information_schema.tables t
        WHERE t.table_schema IN ('identity','budget','portfolio','market','realestate','ops')
          AND t.table_type = 'BASE TABLE'
          AND NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints c
            WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name
              AND c.constraint_type = 'PRIMARY KEY')
    """)).fetchall()
    assert rows == [], f"PK 없는 표: {rows}"


def test_duplicate_transaction_fingerprint_is_rejected(tx) -> None:
    """같은 명세서를 두 번 올리는 일이 흔하다. 앱 로직으로만 막으면 두 요청이 동시에
    들어올 때 뚫린다 — 제약으로 둬야 한다."""
    from sqlalchemy.exc import IntegrityError

    tx.execute(text("INSERT INTO identity.app_user (id, username, status) "
                    "VALUES (9001, 'dup_test', 'active')"))
    tx.execute(text("SELECT set_config('app.current_user_id', '9001', true)"))
    ins = text("""
        INSERT INTO budget.transaction
          (user_id, txn_date, billing_month, merchant, merchant_key,
           amount, charged, fee, total, tx_type, fingerprint)
        VALUES (9001, DATE '2026-08-01', '2026-09', '스타벅스', '스타벅스',
                5600, 5600, 0, 5600, '일시불', 'fp-dup')
    """)
    tx.execute(ins)
    with pytest.raises(IntegrityError):
        tx.execute(ins)


def test_unknown_tx_type_is_rejected(tx) -> None:
    """거래구분이 자유 문자열이면 집계 축이 조용히 갈라진다('일시불' vs '일시 불')."""
    from sqlalchemy.exc import IntegrityError

    tx.execute(text("INSERT INTO identity.app_user (id, username, status) "
                    "VALUES (9002, 'ck_test', 'active')"))
    tx.execute(text("SELECT set_config('app.current_user_id', '9002', true)"))
    with pytest.raises(IntegrityError):
        tx.execute(text("""
            INSERT INTO budget.transaction
              (user_id, txn_date, billing_month, merchant, merchant_key,
               amount, charged, fee, total, tx_type, fingerprint)
            VALUES (9002, DATE '2026-08-01', '2026-09', 'x', 'x',
                    1, 1, 0, 1, '없는구분', 'fp-ck')
        """))


# --- 행 수준 보안 -------------------------------------------------------------
def test_row_level_security_hides_other_users_rows(tx) -> None:
    """이 저장소에서 가장 중요한 검증.

    177개 엔드포인트 중 한 곳이라도 `WHERE user_id = ?` 를 빠뜨리면 남의 가계부가
    그대로 나간다. 리뷰로 막을 수 있는 종류가 아니라서 DB 에 맡긴다.
    """
    tx.execute(text("INSERT INTO identity.app_user (id, username, status) "
                    "VALUES (9101, 'alice', 'active'), (9102, 'bob', 'active')"))
    # 각자 자기 자격으로 넣는다 — 정책이 켜져 있으면 남의 이름으로는 애초에 못 넣는다.
    for uid, fp in ((9101, "fp-alice"), (9102, "fp-bob")):
        tx.execute(text("SELECT set_config('app.current_user_id', :uid, true)"),
                   {"uid": str(uid)})
        tx.execute(text("""
            INSERT INTO budget.transaction
              (user_id, txn_date, billing_month, merchant, merchant_key,
               amount, charged, fee, total, tx_type, fingerprint)
            VALUES (:uid, DATE '2026-08-01', '2026-09', 'm', 'm',
                    1000, 1000, 0, 1000, '일시불', :fp)
        """), {"uid": uid, "fp": fp})

    # 앨리스로 붙는다.
    tx.execute(text("SELECT set_config('app.current_user_id', '9101', true)"))
    seen = tx.execute(text("SELECT fingerprint FROM budget.transaction "
                           "WHERE fingerprint IN ('fp-alice','fp-bob')")).scalars().all()
    assert seen == ["fp-alice"], f"남의 행이 보인다: {seen}"

    # 밥으로 바꾸면 반대가 보인다.
    tx.execute(text("SELECT set_config('app.current_user_id', '9102', true)"))
    seen = tx.execute(text("SELECT fingerprint FROM budget.transaction "
                           "WHERE fingerprint IN ('fp-alice','fp-bob')")).scalars().all()
    assert seen == ["fp-bob"]


def test_no_current_user_means_no_rows(tx) -> None:
    """설정을 깜빡했을 때 **전부 보이는 쪽**으로 실패하면 안 된다. 아무것도 안 보여야 한다."""
    tx.execute(text("INSERT INTO identity.app_user (id, username, status) "
                    "VALUES (9103, 'carol', 'active')"))
    tx.execute(text("SELECT set_config('app.current_user_id', '9103', true)"))
    tx.execute(text("""
        INSERT INTO budget.transaction
          (user_id, txn_date, billing_month, merchant, merchant_key,
           amount, charged, fee, total, tx_type, fingerprint)
        VALUES (9103, DATE '2026-08-01', '2026-09', 'm', 'm',
                1000, 1000, 0, 1000, '일시불', 'fp-carol')
    """))
    tx.execute(text("SELECT set_config('app.current_user_id', '', true)"))
    seen = tx.execute(text("SELECT count(*) FROM budget.transaction "
                           "WHERE fingerprint = 'fp-carol'")).scalar_one()
    assert seen == 0


def test_cannot_insert_a_row_owned_by_someone_else(tx) -> None:
    """WITH CHECK 이 없으면 조회만 막히고 **남의 이름으로 쓰기**는 통과한다."""
    from sqlalchemy.exc import ProgrammingError

    tx.execute(text("INSERT INTO identity.app_user (id, username, status) "
                    "VALUES (9104, 'dave', 'active'), (9105, 'eve', 'active')"))
    tx.execute(text("SELECT set_config('app.current_user_id', '9104', true)"))
    with pytest.raises(ProgrammingError):
        tx.execute(text("""
            INSERT INTO budget.transaction
              (user_id, txn_date, billing_month, merchant, merchant_key,
               amount, charged, fee, total, tx_type, fingerprint)
            VALUES (9105, DATE '2026-08-01', '2026-09', 'm', 'm',
                    1, 1, 0, 1, '일시불', 'fp-eve')
        """))


# --- 감사 -------------------------------------------------------------------
def test_audit_events_cannot_be_modified(tx) -> None:
    """사고 조사에서 감사기록 자체가 고쳐질 수 있으면 아무것도 증명하지 못한다."""
    from sqlalchemy.exc import InternalError, ProgrammingError

    tx.execute(text("INSERT INTO identity.audit_event (actor, action) "
                    "VALUES ('tester', 'login')"))
    with pytest.raises((InternalError, ProgrammingError)):
        tx.execute(text("UPDATE identity.audit_event SET action = 'tampered' "
                        "WHERE actor = 'tester'"))
