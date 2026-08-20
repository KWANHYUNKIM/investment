"""application role for rls

**RLS 는 슈퍼유저에게 통하지 않는다.**

앞 리비전에서 정책을 다 켰는데 검증이 실패했다 — 남의 행이 그대로 보였다. 원인은
정책이 아니라 **접속 계정**이었다. PostgreSQL 은 슈퍼유저에게 행 수준 보안을 아예
적용하지 않고, ``FORCE ROW LEVEL SECURITY`` 도 슈퍼유저는 못 막는다. 도커 이미지가
``POSTGRES_USER`` 를 슈퍼유저로 만들기 때문에 그 계정으로 붙는 한 정책은 장식이다.

이건 실무에서 RLS 를 켜 놓고도 안 걸리는 가장 흔한 원인이고, **켠 줄 알고 있는 상태**
라 더 위험하다. 그래서 권한이 제한된 애플리케이션 역할을 따로 만들고, 앱은 그 역할로
동작한다. 마이그레이션·백업만 소유자 계정을 쓴다.

Revision ID: dade0747a11f
Revises: 9509c3c67de8
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "dade0747a11f"
down_revision: Union[str, None] = "9509c3c67de8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_APP_SCHEMAS = ("identity", "budget", "portfolio", "market", "realestate", "ops")


def upgrade() -> None:
    # 애플리케이션 역할. NOLOGIN 으로 두고 소유자 계정이 SET ROLE 로 갈아입는다 —
    # 비밀번호를 하나 더 관리하지 않아도 되고, 마이그레이션은 소유자로 그대로 돈다.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                CREATE ROLE app_rw NOLOGIN;
            END IF;
        END
        $$;
    """)
    op.execute("GRANT app_rw TO CURRENT_USER;")

    for schema in _APP_SCHEMAS:
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO app_rw;")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO app_rw;")
        # 대리키가 시퀀스를 쓰므로 USAGE 가 없으면 INSERT 가 통째로 막힌다.
        op.execute(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA {schema} TO app_rw;")
        # 앞으로 만들 표에도 같은 권한이 자동으로 붙게 한다. 안 걸어 두면 새 표가
        # 생길 때마다 앱이 조용히 권한 오류를 낸다.
        op.execute(f"""
            ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
        """)
        op.execute(f"""
            ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
            GRANT USAGE ON SEQUENCES TO app_rw;
        """)

    # 감사기록은 넣기만 한다 — 지우거나 고칠 권한을 애초에 주지 않는다.
    # (트리거로도 막지만, 권한으로 한 번 더 막는 게 방어의 기본이다.)
    op.execute("REVOKE UPDATE, DELETE ON identity.audit_event FROM app_rw;")


def downgrade() -> None:
    for schema in _APP_SCHEMAS:
        op.execute(f"""
            ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
            REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_rw;
        """)
        op.execute(f"""
            ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE USAGE ON SEQUENCES FROM app_rw;
        """)
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM app_rw;")
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM app_rw;")
        op.execute(f"REVOKE USAGE ON SCHEMA {schema} FROM app_rw;")
    # 역할 자체는 남긴다 — 다른 DB 가 같은 역할을 쓰고 있을 수 있다(클러스터 단위).
