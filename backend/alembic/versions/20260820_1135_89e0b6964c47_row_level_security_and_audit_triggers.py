"""row level security and audit triggers

계정별 데이터를 **DB 가 직접 막는다.**

지금은 모든 조회가 `WHERE user_id = ?` 를 코드에서 붙인다. 177개 엔드포인트 중
한 곳이라도 그 조건을 빠뜨리면 남의 가계부가 그대로 나간다. 리뷰로 막는 종류의
사고가 아니라, 구조로 막아야 하는 사고다.

PostgreSQL 의 Row-Level Security 를 켜면 정책에 맞지 않는 행은 **SELECT 결과에서
아예 사라진다.** 코드가 조건을 빠뜨려도 남의 행이 나오지 않는다. 애플리케이션은
요청마다 `SET LOCAL app.current_user_id` 로 자기가 누구인지만 알리면 된다.

세 가지를 같이 넣는다.
  1. 사용자 소유 표에 RLS 정책
  2. updated_at 자동 갱신 트리거 — 앱이 깜빡해도 시각이 맞게
  3. 감사기록을 못 고치게 막는 트리거 — append-only 를 규칙이 아니라 강제로

Revision ID: 89e0b6964c47
Revises: afb6047a7f4d
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "89e0b6964c47"
down_revision: Union[str, None] = "afb6047a7f4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# user_id 를 가진 표 = 사람 소유 데이터. 여기에만 RLS 를 건다.
_USER_OWNED = [
    ("budget", "card"),
    ("budget", "import_batch"),
    ("budget", "transaction"),
    ("budget", "merchant_rule"),
    ("budget", "income_profile"),
    ("budget", "mail_message"),
    ("portfolio", "watch_item"),
    ("portfolio", "holding"),
    ("portfolio", "wealth_profile"),
]

# updated_at 을 가진 표.
_TIMESTAMPED = _USER_OWNED + [
    ("identity", "app_user"),
    ("identity", "user_credential"),
    ("identity", "email_verification"),
    ("market", "security"),
    ("market", "company_profile"),
    ("realestate", "region"),
    ("realestate", "region_month_stat"),
    ("realestate", "interest_run"),
    ("ops", "dataset_snapshot"),
]


def upgrade() -> None:
    # --- 역할 -----------------------------------------------------------------
    # 배치·마이그레이션은 '현재 사용자' 가 없다. 그렇다고 슈퍼유저로 돌리면 RLS 가
    # 통째로 무력해지므로, 우회 권한만 가진 전용 역할을 따로 만든다.
    # 역할은 클러스터 단위라 이미 있을 수 있다 — CREATE ROLE 은 IF NOT EXISTS 가 없어
    # DO 블록으로 감싼다.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_maintenance') THEN
                CREATE ROLE app_maintenance NOLOGIN;
            END IF;
        END
        $$;
    """)

    # --- updated_at 자동 갱신 -------------------------------------------------
    # 앱이 채우게 두면 psql·배치로 고친 행은 옛 시각을 유지한다. '언제 바뀌었나' 는
    # 장애 조사에서 가장 먼저 보는 값이라, 예외가 있으면 안 된다.
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    for schema, table in _TIMESTAMPED:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON "{schema}"."{table}"
            FOR EACH ROW EXECUTE FUNCTION ops.set_updated_at();
        """)

    # --- 행 수준 보안 ---------------------------------------------------------
    # 현재 사용자를 읽는 헬퍼. 설정이 없으면 NULL 을 돌려주고, 그러면 정책이 모든 행을
    # 막는다 — **못 정하면 아무것도 안 보이는 쪽**이 안전한 기본값이다.
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.current_user_id() RETURNS bigint AS $$
            SELECT NULLIF(current_setting('app.current_user_id', true), '')::bigint;
        $$ LANGUAGE sql STABLE;
    """)

    for schema, table in _USER_OWNED:
        op.execute(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY;')
        # FORCE 를 켜야 테이블 소유자에게도 적용된다. 안 켜면 앱이 소유자로 붙는 흔한
        # 구성에서 정책이 통째로 무시되어, 켜 놓고 안 켠 것과 같아진다.
        op.execute(f'ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY;')
        op.execute(f"""
            CREATE POLICY {table}_owner ON "{schema}"."{table}"
            USING (user_id = ops.current_user_id())
            WITH CHECK (user_id = ops.current_user_id());
        """)
        # 배치·마이그레이션은 사용자 개념이 없다. 별도 역할에만 우회를 준다.
        op.execute(f"""
            CREATE POLICY {table}_maintenance ON "{schema}"."{table}"
            TO app_maintenance USING (true) WITH CHECK (true);
        """)

    # --- 감사기록은 못 고친다 --------------------------------------------------
    # append-only 를 문서로만 정해 두면 언젠가 누군가 UPDATE 를 쓴다. 사고 조사에서
    # 감사기록 자체가 고쳐질 수 있으면 그 기록은 아무것도 증명하지 못한다.
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.deny_audit_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_event is append-only (attempted %)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_event_immutable
        BEFORE UPDATE OR DELETE ON identity.audit_event
        FOR EACH ROW EXECUTE FUNCTION identity.deny_audit_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_event_immutable ON identity.audit_event;")
    op.execute("DROP FUNCTION IF EXISTS identity.deny_audit_mutation();")

    for schema, table in _USER_OWNED:
        op.execute(f'DROP POLICY IF EXISTS {table}_maintenance ON "{schema}"."{table}";')
        op.execute(f'DROP POLICY IF EXISTS {table}_owner ON "{schema}"."{table}";')
        op.execute(f'ALTER TABLE "{schema}"."{table}" DISABLE ROW LEVEL SECURITY;')
    op.execute("DROP FUNCTION IF EXISTS ops.current_user_id();")

    for schema, table in _TIMESTAMPED:
        op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_updated_at ON "{schema}"."{table}";')
    op.execute("DROP FUNCTION IF EXISTS ops.set_updated_at();")
