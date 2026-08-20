"""계정 보안 — 앱 역할이 남의 자격증명에 닿을 수 있는가.

이 파일이 지키는 것은 하나다: **앱이 뚫려도 전 계정 해시가 통째로 나가지 않는다.**

가계부에는 행 수준 보안을 걸어 놓고 ``identity`` 는 빼놓은 상태였다. 그래서
``SELECT * FROM identity.user_credential`` 이 앱 역할로 그냥 됐다 — SQL 인젝션이
한 곳만 뚫리거나 조인을 한 번만 잘못해도 전 계정 해시가 나가는 구조였다.

해시가 PBKDF2 라 즉시 풀리지는 않지만 오프라인 대입은 시간 문제다. 애초에 나가지
않게 하는 것이 방어이고, 그게 지켜지는지는 DB 에 물어봐야 안다.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db


@pytest.fixture
def app_conn():
    """앱 역할로 붙은 연결 — 실제 서비스가 쓰는 권한 그대로."""
    from app.core.config import get_settings
    from app.db.session import get_engine

    try:
        engine = get_engine()
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"PostgreSQL 없음 — 건너뜀 ({type(e).__name__})")

    with engine.connect() as c:
        trans = c.begin()
        role = get_settings().db_app_role
        if role:
            c.execute(text(f'SET LOCAL ROLE "{role}"'))
        yield c
        trans.rollback()


# --- 자격증명 -----------------------------------------------------------------
def test_app_role_cannot_read_credentials_directly(app_conn) -> None:
    """이게 이 파일의 핵심. 앱 역할은 자격증명 표를 **직접 읽을 수 없어야** 한다."""
    from sqlalchemy.exc import ProgrammingError

    with pytest.raises(ProgrammingError):
        app_conn.execute(text("SELECT * FROM identity.user_credential")).all()


def test_app_role_cannot_dump_hashes_via_join(app_conn) -> None:
    """조인으로 우회하는 것도 막혀야 한다 — 권한은 표 단위로 걸려 있다."""
    from sqlalchemy.exc import ProgrammingError

    with pytest.raises(ProgrammingError):
        app_conn.execute(text("""
            SELECT u.username, c.password_hash
            FROM identity.app_user u JOIN identity.user_credential c ON c.user_id = u.id
        """)).all()


def test_login_function_returns_exactly_one_account(app_conn) -> None:
    """로그인은 자기가 누구인지 알기 전에 자격증명을 읽어야 한다. 그 통로는
    **아이디 하나당 한 행**만 준다 — 전량 덤프가 구조적으로 불가능하다."""
    rows = app_conn.execute(
        text("SELECT * FROM identity.credential_for_login(:u)"),
        {"u": "admin"}).all()
    assert len(rows) <= 1
    if rows:
        assert rows[0].algorithm == "pbkdf2_sha256"
        assert len(rows[0].password_hash) == 32     # SHA-256 출력
        assert len(rows[0].salt) >= 16


def test_login_function_does_not_leak_other_accounts(app_conn) -> None:
    """와일드카드·빈 값으로 전부 긁어오는 시도가 통하면 안 된다."""
    for probe in ("%", "", "' OR '1'='1"):
        rows = app_conn.execute(
            text("SELECT * FROM identity.credential_for_login(:u)"),
            {"u": probe}).all()
        assert rows == [], f"{probe!r} 로 자격증명이 나왔다"


def test_cannot_change_someone_elses_password(app_conn) -> None:
    """비밀번호 변경 통로도 자기 것만 — 함수 안에서 한 번 더 막는다."""
    from sqlalchemy.exc import InternalError, ProgrammingError

    app_conn.execute(text("SELECT set_config('app.current_user_id', '999001', true)"))
    with pytest.raises((InternalError, ProgrammingError)):
        app_conn.execute(text("""
            SELECT identity.set_credential(999002, 'pbkdf2_sha256', 600000,
                                           '\\x00'::bytea, '\\x00'::bytea)
        """))


# --- 계정 --------------------------------------------------------------------
def test_user_list_is_not_readable_wholesale(app_conn) -> None:
    """사용자 목록이 통째로 보일 이유가 없다. 자기 행만 보여야 한다."""
    app_conn.execute(text("SELECT set_config('app.current_user_id', '', true)"))
    n = app_conn.execute(text("SELECT count(*) FROM identity.app_user")).scalar_one()
    assert n == 0, f"컨텍스트 없이 {n}명이 보인다"


def test_audit_trail_stays_append_only_for_the_app(app_conn) -> None:
    """감사기록을 앱이 고칠 수 있으면 그 기록은 아무것도 증명하지 못한다."""
    from sqlalchemy.exc import InternalError, ProgrammingError

    app_conn.execute(text(
        "INSERT INTO identity.audit_event (actor, action) VALUES ('sec-test', 'probe')"))
    with pytest.raises((InternalError, ProgrammingError)):
        app_conn.execute(text(
            "UPDATE identity.audit_event SET action='x' WHERE actor='sec-test'"))


# --- 해시 파라미터 -------------------------------------------------------------
def test_password_hashing_meets_current_guidance() -> None:
    """반복수는 시간이 지나면 부족해진다. 값을 코드에 박아 두고 잊는 게 문제라
    검증으로 고정한다 — OWASP 는 PBKDF2-HMAC-SHA256 600,000회를 권한다."""
    from app.core import auth

    assert auth._ITER >= 600_000, f"반복수가 {auth._ITER:,} 회로 권장치 미달"
    assert auth._HASH_NAME == "sha256"
