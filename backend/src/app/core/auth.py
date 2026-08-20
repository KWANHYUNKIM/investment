"""회원가입/로그인 인증 (다중 사용자, 외부망 노출 대비).

의존성 없이 표준 라이브러리만 사용:
  - 비밀번호: PBKDF2-HMAC-SHA256(사용자별 랜덤 salt, 60만 회) 해시로 저장.
    반복수는 저장해 두고 검증에 그 값을 쓴다. 로그인에 성공하면 현재 기준으로
    조용히 다시 해시하므로, 기준을 올려도 기존 사용자가 잠기지 않는다.
  - 토큰: HMAC-SHA256 서명 stateless 토큰(payload.signature, 만료 포함), 공용 secret.
  - 저장: ``data/auth.json`` = {secret, users:{username:{salt,hash,iter,email,name,created}}}.

아이디/비번 '찾기'는 가입 시 등록한 이메일 일치로 처리(메일 발송 서버가 없으므로).
재무 데이터는 사용자별로 분리 저장한다(budget.py / watchlist.py 의 user 인자).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time

from fastapi import Depends, Header, HTTPException

from app.core.config import get_settings
from app.core import auth_store as _store

# PBKDF2-HMAC-SHA256 반복수. OWASP 권장치(2023~)가 600,000회다.
#
# 이 값은 시간이 지나면 부족해진다 — 하드웨어가 빨라지면 대입도 빨라지기 때문이다.
# 그래서 숫자를 올리는 것만으로 끝내지 않고, **로그인에 성공할 때 조용히 다시
# 해시한다**(_maybe_rehash). 사용자가 비밀번호를 재설정하지 않아도 옛 해시가
# 자연히 사라진다. 알고리즘 이름을 함께 저장해 두는 것도 같은 이유다 — 언젠가
# argon2 로 옮길 때 전 사용자를 한 번에 초기화시키지 않으려면 그 칸이 필요하다.
_HASH_NAME = "sha256"
_ITER = 600_000
_TTL = 7 * 24 * 3600
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CODE_TTL = 600  # 인증코드 유효 10분


# --- 무차별 대입/남용 방지 rate limit (in-memory sliding window) --------------
# 공개 URL 노출 시 인증 계열(코드발송·로그인·재설정) 엔드포인트를 무제한 호출하지
# 못하게 막는다. 프록시 뒤라 IP가 신뢰불가라 식별자(이메일/아이디)와 전역 버킷 기준.
_rate_lock = threading.Lock()
_rate_hits: dict[str, list[float]] = {}


def rate_limit(bucket: str, max_hits: int, window: int) -> None:
    """bucket 키로 window(초) 안에 max_hits 회를 넘으면 429를 던진다."""
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate_hits.get(bucket, []) if now - t < window]
        if len(hits) >= max_hits:
            retry = int(window - (now - hits[0])) + 1
            raise HTTPException(429, f"요청이 너무 많습니다. 약 {retry}초 후 다시 시도하세요.")
        hits.append(now)
        _rate_hits[bucket] = hits
        if len(_rate_hits) > 5000:  # 메모리 누수 방지: 만료된 버킷 청소
            for k in list(_rate_hits):
                fresh = [t for t in _rate_hits[k] if now - t < window]
                if fresh:
                    _rate_hits[k] = fresh
                else:
                    del _rate_hits[k]


# 저장소는 ``auth_store`` 가 고른다 — 파일(기존) 또는 PostgreSQL.
#
# DB 판으로 가면 **전 계정 해시를 한 번에 가져오는 질의 자체가 없다.** 동작마다 좁은
# 통로(SECURITY DEFINER 함수)만 열려 있어서, 코드가 실수해도 덤프가 안 만들어진다.
def _path() -> str:
    return _store._path()


def _load() -> dict:
    """파일 판 전용. 남아 있는 이유는 되돌릴 수 있어야 하기 때문이다."""
    return _store.file_load()


def _save(d: dict) -> None:
    _store.file_save(d)


def has_users() -> bool:
    return _store.has_users()


def user_exists(username: str) -> bool:
    return _store.username_taken((username or "").strip())


def list_users() -> list[dict]:
    """관리자 목록. **해시는 어느 판에서도 나오지 않는다.**"""
    out = []
    for u in _store.list_accounts():
        name = u["username"]
        out.append({**u, "is_admin": is_admin(name)})
    out.sort(key=lambda x: x.get("created") or 0)
    return out


def _hash_pw(password: str, salt: bytes, iterations: int | None = None) -> bytes:
    """반복수를 인자로 받는다 — 옛 해시를 검증하려면 **그때 쓰던 값**이 필요하다.

    기본값만 쓰면 반복수를 올리는 순간 기존 사용자가 전부 로그인 불가가 된다.
    """
    return hashlib.pbkdf2_hmac(_HASH_NAME, (password or "").encode("utf-8"), salt,
                               int(iterations or _ITER))


# --- 이메일 인증코드 -------------------------------------------------------
def _send_email(to: str, subject: str, body: str) -> bool:
    """SMTP 설정이 있으면 발송, 없으면 False(개발모드)."""
    import smtplib
    from email.message import EmailMessage

    s = get_settings()
    if not s.smtp_host or not s.smtp_password:
        return False  # 앱 비밀번호 미설정 → 개발모드(코드 화면 표시)
    sender = s.smtp_from or s.smtp_user
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(s.smtp_host, int(s.smtp_port or 587), timeout=15) as server:
        server.starttls()
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.send_message(msg)
    return True


def send_code(email: str) -> dict:
    """이메일로 6자리 인증코드 발송. 반환에 email_configured(발송여부),
    미설정이면 dev_code(테스트용) 포함."""
    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "올바른 이메일 주소를 입력하세요.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    _store.put_code(email, code, _CODE_TTL)
    try:
        sent = _send_email(email, "[투자 자산 관리] 인증코드",
                           f"인증코드: {code}\n\n10분 안에 입력해 주세요. 본인이 요청하지 않았다면 무시하세요.")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"이메일 발송 실패: {str(e)[:120]}")
    s = get_settings()
    out = {"sent": bool(sent), "email_configured": bool(s.smtp_host and s.smtp_password)}
    # dev_code 는 명시적으로 켠 로컬 개발에서만 노출. 공개 배포에서 노출하면
    # 이메일 인증이 무력화되어 send-code→reset-password 로 계정 탈취가 가능하다.
    if not sent and s.auth_expose_dev_code:
        out["dev_code"] = code
    return out


def verify_code(email: str, code: str, consume: bool = True) -> bool:
    return _store.check_code((email or "").strip().lower(), code, consume)


# --- 회원가입 / 로그인 -----------------------------------------------------
def register(username: str, password: str, email: str = "", name: str = "", code: str = "") -> str:
    username = (username or "").strip()
    email = (email or "").strip().lower()
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, "아이디는 영문/숫자/_/-/. 3~20자여야 합니다.")
    if len(password or "") < 6:
        raise HTTPException(400, "비밀번호는 6자 이상이어야 합니다.")
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "회원가입에는 유효한 이메일이 필요합니다.")
    if not verify_code(email, code):
        raise HTTPException(400, "이메일 인증코드가 올바르지 않거나 만료되었습니다.")
    if _store.username_taken(username):
        raise HTTPException(400, "이미 존재하는 아이디입니다.")
    salt = secrets.token_bytes(16)
    try:
        _store.create_account(username, email, (name or "").strip(),
                              algorithm="pbkdf2_sha256", iterations=_ITER,
                              salt=salt, password_hash=_hash_pw(password, salt))
    except Exception as e:  # noqa: BLE001
        # 중복은 DB 제약이 마지막으로 한 번 더 잡는다 — 두 요청이 동시에 들어와도 뚫리지 않게.
        if "username_taken" in str(e) or "uq_app_user" in str(e):
            raise HTTPException(400, "이미 존재하는 아이디입니다.") from e
        raise
    return issue_token(username)


def verify_password(username: str, password: str) -> bool:
    """저장된 반복수로 검증하고, 그 값이 현재 기준보다 낮으면 조용히 다시 해시한다.

    재해시를 로그인 시점에 하는 이유: 평문 비밀번호를 손에 쥐고 있는 순간이 여기뿐이다.
    저장된 것은 해시라 반복수만 올려 다시 계산할 수가 없다.
    """
    username = (username or "").strip()
    cred = _store.credential(username)
    if not cred:
        # 없는 아이디에도 같은 시간을 쓴다 — 응답 속도로 아이디 존재 여부가 새면
        # 그 자체가 정보 노출이다.
        _hash_pw(password, b"\x00" * 16)
        return False
    if cred.get("status") not in (None, "active"):
        return False
    stored_iter = int(cred.get("iterations") or _ITER)
    calc = _hash_pw(password, cred["salt"], stored_iter)
    if not hmac.compare_digest(calc, cred["hash"]):
        return False
    if stored_iter < _ITER:
        _maybe_rehash(username, password)
    return True


def _maybe_rehash(username: str, password: str) -> None:
    """옛 반복수로 저장된 해시를 현재 기준으로 다시 만든다. 실패해도 로그인은 성공."""
    try:
        salt = secrets.token_bytes(16)
        _store.rehash(username, algorithm="pbkdf2_sha256", iterations=_ITER,
                      salt=salt, password_hash=_hash_pw(password, salt, _ITER))
    except Exception:  # noqa: BLE001
        # 재해시는 보안 개선이지 로그인의 전제가 아니다 — 실패해도 막지 않는다.
        pass


def login(username: str, password: str) -> str:
    username = (username or "").strip()
    if not verify_password(username, password):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    try:
        _store.touch_login(username)      # 기록 실패가 로그인을 막지는 않는다
    except Exception:  # noqa: BLE001
        pass
    return issue_token(username)


def _mask(username: str) -> str:
    if len(username) <= 2:
        return username[0] + "*"
    return username[:2] + "*" * (len(username) - 2)


def find_ids_by_email(email: str) -> list[str]:
    email = (email or "").strip().lower()
    if not email:
        return []
    return [_mask(u) for u in _store.find_usernames_by_email(email)]


def reset_password(username: str, email: str, new_password: str, code: str = "") -> None:
    username, email = (username or "").strip(), (email or "").strip().lower()
    if len(new_password or "") < 6:
        raise HTTPException(400, "새 비밀번호는 6자 이상이어야 합니다.")
    # 인증코드를 **먼저** 확인한다. 아이디·이메일 대조를 먼저 하면 그 응답 차이로
    # 어떤 조합이 존재하는지 알아낼 수 있다.
    if not verify_code(email, code):
        raise HTTPException(400, "이메일 인증코드가 올바르지 않거나 만료되었습니다.")
    salt = secrets.token_bytes(16)
    ok = _store.reset_credential(username, email, algorithm="pbkdf2_sha256",
                                 iterations=_ITER, salt=salt,
                                 password_hash=_hash_pw(new_password, salt))
    if not ok:
        raise HTTPException(401, "아이디와 이메일이 일치하지 않습니다.")


def change_password(username: str, old_password: str, new_password: str) -> None:
    if not verify_password(username, old_password):
        raise HTTPException(401, "현재 비밀번호가 올바르지 않습니다.")
    if len(new_password or "") < 6:
        raise HTTPException(400, "새 비밀번호는 6자 이상이어야 합니다.")
    salt = secrets.token_bytes(16)
    _store.rehash(username, algorithm="pbkdf2_sha256", iterations=_ITER,
                  salt=salt, password_hash=_hash_pw(new_password, salt))


# --- 토큰 (stateless, HMAC 서명) -------------------------------------------
def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _secret() -> bytes:
    """토큰 서명 키. **DB 에 두지 않는다** — DB 가 뚫려도 토큰을 위조할 수 없게."""
    return _store.signing_secret()


def issue_token(username: str) -> str:
    payload = json.dumps({"u": username, "exp": int(time.time()) + _TTL}, separators=(",", ":")).encode()
    p = _b64e(payload)
    sig = _b64e(hmac.new(_secret(), p.encode(), hashlib.sha256).digest())
    return f"{p}.{sig}"


def verify_token(token: str) -> str | None:
    if not token or "." not in token:
        return None
    p, sig = token.split(".", 1)
    expected = _b64e(hmac.new(_secret(), p.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        data = json.loads(_b64d(p))
    except Exception:
        return None
    if int(data.get("exp", 0)) < time.time():
        return None
    u = data.get("u")
    return u if user_exists(u) else None


# --- 관리자 --------------------------------------------------------------
def admin_users() -> set[str]:
    raw = get_settings().admin_usernames or ""
    return {u.strip() for u in raw.split(",") if u.strip()}


def is_admin(username: str) -> bool:
    return (username or "").strip() in admin_users()


# --- FastAPI 의존성 --------------------------------------------------------
def require_auth(authorization: str = Header(default="")) -> str:
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization.strip()
    user = verify_token(token)
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user


def require_admin(user: str = Depends(require_auth)) -> str:
    if not is_admin(user):
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return user
