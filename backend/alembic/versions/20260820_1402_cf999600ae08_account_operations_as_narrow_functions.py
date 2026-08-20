"""account operations as narrow functions

인증을 파일에서 DB 로 완전히 옮기기 위한 통로들.

계정 관리에는 **사용자 경계를 넘어야만 하는 동작**이 몇 개 있다 — 가입할 때 아이디
중복 확인, 아이디 찾기, 비밀번호 재설정. 이것들 때문에 표를 통째로 열어 주면 앞
리비전에서 막은 것이 도로 열린다.

그래서 동작마다 **필요한 것만 돌려주는 함수**를 판다. 각 함수가 노출하는 것은 그
동작이 어차피 드러내는 정보뿐이다.

  · username_taken   → 불리언 하나. 가입 화면이 어차피 알려주는 사실이다.
  · find_usernames_by_email → 이메일이 맞을 때만, 그 이메일의 아이디만.
  · reset_credential → 아이디·이메일 쌍이 맞을 때만 바꾼다.
  · list_accounts    → 해시는 절대 안 준다. 관리자 화면용.

전부 SECURITY DEFINER 이고 search_path 를 고정한다 — 안 하면 호출자가 자기 스키마에
가짜 함수를 심어 이 함수들이 그것을 부르게 만들 수 있다.

Revision ID: cf999600ae08
Revises: 46b0f6b6a642
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "cf999600ae08"
down_revision: Union[str, None] = "46b0f6b6a642"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 조회 -----------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.has_any_user() RETURNS boolean
        LANGUAGE sql SECURITY DEFINER SET search_path = identity, pg_temp AS $$
            SELECT EXISTS (SELECT 1 FROM identity.app_user);
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.username_taken(p_username text) RETURNS boolean
        LANGUAGE sql SECURITY DEFINER SET search_path = identity, pg_temp AS $$
            SELECT EXISTS (
                SELECT 1 FROM identity.app_user WHERE lower(username) = lower(p_username));
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.find_usernames_by_email(p_email text)
        RETURNS TABLE (username text)
        LANGUAGE sql SECURITY DEFINER SET search_path = identity, pg_temp AS $$
            SELECT u.username FROM identity.app_user u
            WHERE p_email <> '' AND lower(u.email) = lower(p_email);
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.list_accounts()
        RETURNS TABLE (username text, email text, display_name text,
                       created_at timestamptz, status text)
        LANGUAGE sql SECURITY DEFINER SET search_path = identity, pg_temp AS $$
            SELECT u.username, u.email, u.display_name, u.created_at, u.status
            FROM identity.app_user u ORDER BY u.created_at;
        $$;
    """)

    # --- 가입 -----------------------------------------------------------------
    # 계정과 자격증명을 한 트랜잭션에서 만든다. 둘로 나누면 계정만 생기고 비밀번호가
    # 없는 상태가 남을 수 있다.
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.create_account(
            p_username text, p_email text, p_display_name text,
            p_algorithm text, p_iterations int, p_salt bytea, p_hash bytea)
        RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = identity, pg_temp AS $$
        DECLARE new_id bigint;
        BEGIN
            IF EXISTS (SELECT 1 FROM identity.app_user
                       WHERE lower(username) = lower(p_username)) THEN
                RAISE EXCEPTION 'username_taken';
            END IF;
            INSERT INTO identity.app_user (username, email, display_name, created_by)
            VALUES (p_username, nullif(p_email, ''), nullif(p_display_name, ''), 'signup')
            RETURNING id INTO new_id;
            INSERT INTO identity.user_credential
                (user_id, algorithm, iterations, salt, password_hash)
            VALUES (new_id, p_algorithm, p_iterations, p_salt, p_hash);
            RETURN new_id;
        END;
        $$;
    """)

    # --- 비밀번호 재설정 ---------------------------------------------------------
    # 로그인하지 않은 상태에서 일어나므로 set_credential(자기 것만) 을 못 쓴다.
    # 대신 **아이디와 이메일이 함께 맞을 때만** 바꾼다. 이메일 인증코드 확인은
    # 애플리케이션이 먼저 하고 오는 전제다.
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.reset_credential(
            p_username text, p_email text,
            p_algorithm text, p_iterations int, p_salt bytea, p_hash bytea)
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = identity, pg_temp AS $$
        DECLARE target bigint;
        BEGIN
            SELECT id INTO target FROM identity.app_user
            WHERE lower(username) = lower(p_username)
              AND email IS NOT NULL AND lower(email) = lower(p_email);
            IF target IS NULL THEN
                RETURN false;
            END IF;
            UPDATE identity.user_credential
               SET algorithm = p_algorithm, iterations = p_iterations,
                   salt = p_salt, password_hash = p_hash, rotated_at = now()
             WHERE user_id = target;
            RETURN true;
        END;
        $$;
    """)

    # 로그인 성공 시 재해시 — 자기 자신인데 아직 세션 컨텍스트가 없는 순간이라
    # set_credential 의 검사에 걸린다. 아이디로 지정하는 통로를 따로 둔다.
    op.execute("""
        CREATE OR REPLACE FUNCTION identity.rehash_credential(
            p_username text, p_algorithm text, p_iterations int,
            p_salt bytea, p_hash bytea)
        RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = identity, pg_temp AS $$
            UPDATE identity.user_credential c
               SET algorithm = p_algorithm, iterations = p_iterations,
                   salt = p_salt, password_hash = p_hash, rotated_at = now()
              FROM identity.app_user u
             WHERE u.id = c.user_id AND lower(u.username) = lower(p_username);
        $$;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION identity.touch_login(p_username text) RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = identity, pg_temp AS $$
            UPDATE identity.app_user SET last_login_at = now()
            WHERE lower(username) = lower(p_username);
        $$;
    """)

    for fn in (
        "identity.has_any_user()",
        "identity.username_taken(text)",
        "identity.find_usernames_by_email(text)",
        "identity.list_accounts()",
        "identity.create_account(text, text, text, text, int, bytea, bytea)",
        "identity.reset_credential(text, text, text, int, bytea, bytea)",
        "identity.rehash_credential(text, text, int, bytea, bytea)",
        "identity.touch_login(text)",
    ):
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO app_rw;")


def downgrade() -> None:
    for fn in (
        "identity.touch_login(text)",
        "identity.rehash_credential(text, text, int, bytea, bytea)",
        "identity.reset_credential(text, text, text, int, bytea, bytea)",
        "identity.create_account(text, text, text, text, int, bytea, bytea)",
        "identity.list_accounts()",
        "identity.find_usernames_by_email(text)",
        "identity.username_taken(text)",
        "identity.has_any_user()",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {fn};")
