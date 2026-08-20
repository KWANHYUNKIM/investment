"""계정 저장소 — 파일과 PostgreSQL 두 벌, 같은 계약.

``auth.py`` 는 지금까지 ``data/auth.json`` 한 파일을 통째로 읽고 통째로 썼다. 그
방식의 문제는 저장 위치가 아니라 **모양**이다 — 한 번 읽으면 전 계정의 해시가
메모리에 올라온다. 코드 어디서든 실수 한 번이면 그게 로그나 응답에 실린다.

DB 판은 그 모양을 못 만든다. 필요한 동작마다 **좁은 통로**(SECURITY DEFINER 함수)만
열려 있어서, 전 계정 해시를 한 번에 가져오는 질의 자체가 존재하지 않는다.

두 판이 같은 계약을 지키므로 ``auth.py`` 의 흐름(검증·인증코드·재해시)은 그대로다.
되돌리는 것도 설정 한 줄이다.
"""
from __future__ import annotations

import hmac
import time
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json


def use_db() -> bool:
    """계정을 DB 에서 읽고 쓸지. 다른 도메인과 같은 스위치를 따른다."""
    return get_settings().budget_storage == "postgres"


# --- 파일 판 ----------------------------------------------------------------
def _path() -> str:
    return str(get_settings().data_dir / "auth.json")


def file_load() -> dict:
    import secrets
    return read_json(_path(), {"secret": secrets.token_hex(32), "users": {}})


def file_save(d: dict) -> None:
    write_json(_path(), d, compact=False, ensure_ascii=True, mode=0o600)


# --- DB 판 ------------------------------------------------------------------
def _exec(sql: str, params: dict | None = None):
    """앱 역할로 함수 하나를 부른다. 세션을 오래 들고 있지 않는다."""
    from app.db.session import get_sessionmaker

    s = get_sessionmaker()()
    try:
        role = get_settings().db_app_role
        if role:
            s.execute(text(f'SET LOCAL ROLE "{role}"'))
        res = s.execute(text(sql), params or {})
        rows = res.fetchall() if res.returns_rows else []
        s.commit()
        return rows
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# --- 공통 계약 --------------------------------------------------------------
def has_users() -> bool:
    if use_db():
        return bool(_exec("SELECT identity.has_any_user()")[0][0])
    return bool(file_load().get("users"))


def username_taken(username: str) -> bool:
    if use_db():
        return bool(_exec("SELECT identity.username_taken(:u)",
                          {"u": username})[0][0])
    return (username or "") in file_load().get("users", {})


def list_accounts() -> list[dict]:
    """관리자 목록. **해시는 어느 판에서도 나오지 않는다.**"""
    if use_db():
        rows = _exec("SELECT * FROM identity.list_accounts()")
        return [{"username": r.username, "email": r.email, "name": r.display_name,
                 "created": int(r.created_at.timestamp()) if r.created_at else None}
                for r in rows]
    users = file_load().get("users", {})
    return [{"username": u, "email": v.get("email"), "name": v.get("name"),
             "created": v.get("created")} for u, v in users.items()]


def credential(username: str) -> dict | None:
    """로그인용 자격증명 한 벌. 없으면 ``None``."""
    if use_db():
        rows = _exec("SELECT * FROM identity.credential_for_login(:u)", {"u": username})
        if not rows:
            return None
        r = rows[0]
        return {"user_id": r.user_id, "algorithm": r.algorithm,
                "iterations": r.iterations, "salt": bytes(r.salt),
                "hash": bytes(r.password_hash), "status": r.status}
    u = file_load().get("users", {}).get(username)
    if not u:
        return None
    return {"user_id": None, "algorithm": "pbkdf2_sha256",
            "iterations": int(u.get("iter") or 0),
            "salt": bytes.fromhex(u.get("salt", "")),
            "hash": bytes.fromhex(u.get("hash", "")), "status": "active"}


def create_account(username: str, email: str, name: str, *, algorithm: str,
                   iterations: int, salt: bytes, password_hash: bytes) -> None:
    if use_db():
        _exec("SELECT identity.create_account(:u, :e, :n, :a, :i, :s, :h)",
              {"u": username, "e": email or "", "n": name or "", "a": algorithm,
               "i": iterations, "s": salt, "h": password_hash})
        return
    d = file_load()
    d.setdefault("users", {})[username] = {
        "salt": salt.hex(), "hash": password_hash.hex(), "iter": iterations,
        "email": email, "name": name, "created": int(time.time()),
    }
    file_save(d)


def rehash(username: str, *, algorithm: str, iterations: int, salt: bytes,
           password_hash: bytes) -> None:
    """로그인 성공 직후의 재해시. 아직 세션 컨텍스트가 없는 순간이라 통로가 따로 있다."""
    if use_db():
        _exec("SELECT identity.rehash_credential(:u, :a, :i, :s, :h)",
              {"u": username, "a": algorithm, "i": iterations,
               "s": salt, "h": password_hash})
        return
    d = file_load()
    u = d.get("users", {}).get(username)
    if not u:
        return
    u.update({"salt": salt.hex(), "hash": password_hash.hex(), "iter": iterations})
    file_save(d)


def reset_credential(username: str, email: str, *, algorithm: str, iterations: int,
                     salt: bytes, password_hash: bytes) -> bool:
    """아이디·이메일이 함께 맞을 때만 바꾼다. 맞지 않으면 ``False``."""
    if use_db():
        ok = _exec("SELECT identity.reset_credential(:u, :e, :a, :i, :s, :h)",
                   {"u": username, "e": email, "a": algorithm, "i": iterations,
                    "s": salt, "h": password_hash})[0][0]
        return bool(ok)
    d = file_load()
    u = d.get("users", {}).get(username)
    if not u or not u.get("email") or u.get("email") != email:
        return False
    u.update({"salt": salt.hex(), "hash": password_hash.hex(), "iter": iterations})
    file_save(d)
    return True


def find_usernames_by_email(email: str) -> list[str]:
    if use_db():
        return [r.username for r in
                _exec("SELECT * FROM identity.find_usernames_by_email(:e)", {"e": email})]
    return [u for u, v in file_load().get("users", {}).items()
            if v.get("email") == email]


def touch_login(username: str) -> None:
    if use_db():
        _exec("SELECT identity.touch_login(:u)", {"u": username})


# --- 이메일 인증코드 ----------------------------------------------------------
def put_code(email: str, code: str, ttl: int) -> None:
    """코드를 저장한다. DB 판은 **해시로** 둔다 — 표를 읽어도 코드를 알 수 없게."""
    if use_db():
        import hashlib
        _exec("""
            INSERT INTO identity.email_verification (email, code_hash, expires_at)
            VALUES (:e, :h, now() + make_interval(secs => :ttl))
        """, {"e": email, "h": hashlib.sha256(code.encode()).digest(), "ttl": ttl})
        return
    d = file_load()
    d.setdefault("codes", {})[email] = {"code": code, "exp": int(time.time()) + ttl}
    file_save(d)


def check_code(email: str, code: str, consume: bool = True) -> bool:
    if use_db():
        import hashlib
        digest = hashlib.sha256(str(code or "").strip().encode()).digest()
        rows = _exec("""
            SELECT id FROM identity.email_verification
            WHERE email = :e AND code_hash = :h
              AND consumed_at IS NULL AND expires_at > now()
            ORDER BY id DESC LIMIT 1
        """, {"e": email, "h": digest})
        if not rows:
            return False
        if consume:
            _exec("UPDATE identity.email_verification SET consumed_at = now() "
                  "WHERE id = :i", {"i": rows[0].id})
        return True

    d = file_load()
    rec = d.get("codes", {}).get(email)
    if not rec or int(rec.get("exp", 0)) < time.time():
        return False
    ok = hmac.compare_digest(str(rec.get("code")), str(code or "").strip())
    if ok and consume:
        d["codes"].pop(email, None)
        file_save(d)
    return ok


# --- 토큰 서명 키 ------------------------------------------------------------
def signing_secret() -> bytes:
    """토큰 서명 키.

    **DB 에 두지 않는다.** DB 가 뚫렸을 때 해시는 못 풀어도 서명 키가 같이 나가면
    아무 계정으로나 토큰을 위조할 수 있다. 키는 환경변수에 두어 DB 침해와 분리한다.

    ``AUTH_SECRET`` 이 없으면 기존 파일의 값을 쓴다 — 설정 전에 로그인이 통째로
    깨지지 않게. 외부에 열 때는 반드시 환경변수로 넣어야 한다.
    """
    s = get_settings()
    if s.auth_secret:
        return bytes.fromhex(s.auth_secret) if _is_hex(s.auth_secret) \
            else s.auth_secret.encode("utf-8")
    return bytes.fromhex(file_load().get("secret", ""))


def _is_hex(v: str) -> bool:
    try:
        bytes.fromhex(v)
        return True
    except ValueError:
        return False


__all__ = ["check_code", "create_account", "credential", "file_load", "file_save",
           "find_usernames_by_email", "has_users", "list_accounts", "put_code",
           "rehash", "reset_credential", "signing_secret", "touch_login",
           "use_db", "username_taken"]
