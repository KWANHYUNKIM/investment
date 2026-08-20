"""harden identity: rls, login function, least privilege

**앱 역할이 전 계정의 비밀번호 해시를 읽을 수 있었다.**

가계부·포트폴리오에는 행 수준 보안을 걸었는데 ``identity`` 스키마는 빼놓았다. 그래서
``app_rw`` 로 붙은 상태에서 ``SELECT * FROM identity.user_credential`` 이 그냥 됐다.
SQL 인젝션이 한 곳만 뚫리거나 앱 코드가 실수로 조인 한 번만 잘못해도 전 계정 해시가
통째로 나간다. 해시가 PBKDF2 200,000회라 즉시 풀리진 않지만, 오프라인 대입은 시간
문제일 뿐이다 — 애초에 나가지 않게 하는 것이 방어다.

여기서 딜레마가 하나 있다. **로그인은 자기가 누구인지 알기 전에 자격증명을 읽어야
한다.** 그래서 RLS 만 걸면 로그인 자체가 불가능해진다.

해결은 통로를 하나만 남기는 것이다.

  · 표 자체는 RLS 로 잠그고, 앱 역할의 직접 SELECT 권한을 회수한다.
  · 로그인에 필요한 것만 돌려주는 SECURITY DEFINER 함수를 만들어 그것만 실행 허용.

이러면 앱은 **아이디 하나당 한 행**밖에 못 가져온다. 전량 덤프가 구조적으로 막힌다.
비밀번호 대조는 애플리케이션에서 계속 한다(PBKDF2 파라미터를 코드가 소유해야
반복수를 올리고 재해시하는 이행이 가능하다).

Revision ID: 46b0f6b6a642
Revises: ee653639583b
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "46b0f6b6a642"
down_revision: Union[str, None] = "ee653639583b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 로그인 전용 통로 -----------------------------------------------------
    # SECURITY DEFINER 라 소유자 권한으로 돈다. search_path 를 고정하는 게 중요하다 —
    # 안 하면 호출자가 자기 스키마에 가짜 함수를 심어 이 함수가 그걸 부르게 만들 수 있다.
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.credential_for_login(p_username text)
        RETURNS TABLE (user_id bigint, algorithm text, iterations int,
                       salt bytea, password_hash bytea, status text)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = identity, pg_temp
        AS $$
            SELECT u.id, c.algorithm, c.iterations, c.salt, c.password_hash, u.status
            FROM identity.app_user u
            JOIN identity.user_credential c ON c.user_id = u.id
            WHERE lower(u.username) = lower(p_username)
            LIMIT 1;
        $$;
    """)

    # 비밀번호 변경·재설정도 자기 것만 되게 통로를 따로 판다.
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.set_credential(
            p_user_id bigint, p_algorithm text, p_iterations int,
            p_salt bytea, p_hash bytea)
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = identity, pg_temp
        AS $$
        BEGIN
            -- 남의 자격증명을 바꾸는 것을 함수 안에서 막는다. 호출부가 실수해도
            -- 여기서 걸린다.
            IF p_user_id IS DISTINCT FROM ops.current_user_id() THEN
                RAISE EXCEPTION '자기 자격증명만 바꿀 수 있습니다';
            END IF;
            INSERT INTO identity.user_credential
                (user_id, algorithm, iterations, salt, password_hash, rotated_at)
            VALUES (p_user_id, p_algorithm, p_iterations, p_salt, p_hash, now())
            ON CONFLICT (user_id) DO UPDATE
              SET algorithm = EXCLUDED.algorithm,
                  iterations = EXCLUDED.iterations,
                  salt = EXCLUDED.salt,
                  password_hash = EXCLUDED.password_hash,
                  rotated_at = now();
        END;
        $$;
    """)

    # --- 자격증명 표를 잠근다 --------------------------------------------------
    op.execute("ALTER TABLE identity.user_credential ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE identity.user_credential FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY user_credential_self ON identity.user_credential
        USING (user_id = ops.current_user_id())
        WITH CHECK (user_id = ops.current_user_id());
    """)
    # 직접 접근 자체를 끊는다. 남는 통로는 위 두 함수뿐이다.
    op.execute("REVOKE ALL ON identity.user_credential FROM app_rw;")
    op.execute("GRANT EXECUTE ON FUNCTION identity.credential_for_login(text) TO app_rw;")
    op.execute("GRANT EXECUTE ON FUNCTION "
               "identity.set_credential(bigint, text, int, bytea, bytea) TO app_rw;")

    # --- 계정 표도 자기 것만 -----------------------------------------------------
    # 사용자 목록이 통째로 보일 이유가 없다. 관리자 화면은 유지보수 역할로 본다.
    op.execute("ALTER TABLE identity.app_user ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE identity.app_user FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY app_user_self ON identity.app_user
        USING (id = ops.current_user_id())
        WITH CHECK (id = ops.current_user_id());
    """)
    # 가입은 '아직 누구도 아닌' 상태에서 일어난다 — 그 한 경우만 열어 둔다.
    op.execute("""
        CREATE POLICY app_user_signup ON identity.app_user
        FOR INSERT WITH CHECK (ops.current_user_id() IS NULL);
    """)
    op.execute("""
        CREATE POLICY app_user_maintenance ON identity.app_user
        TO app_maintenance USING (true) WITH CHECK (true);
    """)

    # --- 인증코드도 잠근다 ------------------------------------------------------
    # 남의 인증코드 해시를 읽을 수 있으면 비밀번호 재설정을 가로챌 수 있다.
    # 이메일로만 조회하는 흐름이라 RLS 대신 권한으로 좁힌다 — 앱은 넣고 지우기만 한다.
    op.execute("REVOKE ALL ON identity.email_verification FROM app_rw;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE "
               "ON identity.email_verification TO app_rw;")


def downgrade() -> None:
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON identity.user_credential TO app_rw;")
    op.execute("DROP POLICY IF EXISTS app_user_maintenance ON identity.app_user;")
    op.execute("DROP POLICY IF EXISTS app_user_signup ON identity.app_user;")
    op.execute("DROP POLICY IF EXISTS app_user_self ON identity.app_user;")
    op.execute("ALTER TABLE identity.app_user DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS user_credential_self ON identity.user_credential;")
    op.execute("ALTER TABLE identity.user_credential DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP FUNCTION IF EXISTS "
               "identity.set_credential(bigint, text, int, bytea, bytea);")
    op.execute("DROP FUNCTION IF EXISTS identity.credential_for_login(text);")
