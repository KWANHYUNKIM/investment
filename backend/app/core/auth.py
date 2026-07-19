"""회원가입/로그인 인증 (다중 사용자, 외부망 노출 대비).

의존성 없이 표준 라이브러리만 사용:
  - 비밀번호: PBKDF2-HMAC-SHA256(사용자별 랜덤 salt, 20만 회) 해시로 저장.
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
import os
import re
import secrets
import threading
import time

from fastapi import Header, HTTPException

from app.core.config import get_settings

_ITER = 200_000
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


def _path() -> str:
    return str(get_settings().data_dir / "auth.json")


def _load() -> dict:
    p = _path()
    if not os.path.exists(p):
        return {"secret": secrets.token_hex(32), "users": {}}
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        d.setdefault("secret", secrets.token_hex(32))
        d.setdefault("users", {})
        return d
    except Exception:
        return {"secret": secrets.token_hex(32), "users": {}}


def _save(d: dict) -> None:
    p = _path()
    tmp = f"{p}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass


def has_users() -> bool:
    return bool(_load().get("users"))


def user_exists(username: str) -> bool:
    return (username or "") in _load().get("users", {})


def _hash_pw(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, _ITER)


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
    d = _load()
    d.setdefault("codes", {})[email] = {"code": code, "exp": int(time.time()) + _CODE_TTL}
    _save(d)
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
    email = (email or "").strip().lower()
    d = _load()
    rec = d.get("codes", {}).get(email)
    if not rec or int(rec.get("exp", 0)) < time.time():
        return False
    ok = hmac.compare_digest(str(rec.get("code")), str(code or "").strip())
    if ok and consume:
        d["codes"].pop(email, None)
        _save(d)
    return ok


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
    d = _load()
    if username in d["users"]:
        raise HTTPException(400, "이미 존재하는 아이디입니다.")
    salt = secrets.token_bytes(16)
    d["users"][username] = {
        "salt": salt.hex(), "hash": _hash_pw(password, salt).hex(), "iter": _ITER,
        "email": email, "name": (name or "").strip(), "created": int(time.time()),
    }
    _save(d)
    return issue_token(username)


def verify_password(username: str, password: str) -> bool:
    u = _load().get("users", {}).get((username or "").strip())
    if not u:
        return False
    calc = _hash_pw(password, bytes.fromhex(u["salt"]))
    return hmac.compare_digest(calc.hex(), u.get("hash", ""))


def login(username: str, password: str) -> str:
    if not verify_password((username or "").strip(), password):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    return issue_token((username or "").strip())


def _mask(username: str) -> str:
    if len(username) <= 2:
        return username[0] + "*"
    return username[:2] + "*" * (len(username) - 2)


def find_ids_by_email(email: str) -> list[str]:
    email = (email or "").strip().lower()
    if not email:
        return []
    return [_mask(u) for u, v in _load().get("users", {}).items() if v.get("email") == email]


def reset_password(username: str, email: str, new_password: str, code: str = "") -> None:
    username, email = (username or "").strip(), (email or "").strip().lower()
    d = _load()
    u = d.get("users", {}).get(username)
    if not u or not u.get("email") or u.get("email") != email:
        raise HTTPException(401, "아이디와 이메일이 일치하지 않습니다.")
    if not verify_code(email, code):
        raise HTTPException(400, "이메일 인증코드가 올바르지 않거나 만료되었습니다.")
    if len(new_password or "") < 6:
        raise HTTPException(400, "새 비밀번호는 6자 이상이어야 합니다.")
    salt = secrets.token_bytes(16)
    u["salt"], u["hash"] = salt.hex(), _hash_pw(new_password, salt).hex()
    _save(d)


def change_password(username: str, old_password: str, new_password: str) -> None:
    if not verify_password(username, old_password):
        raise HTTPException(401, "현재 비밀번호가 올바르지 않습니다.")
    if len(new_password or "") < 6:
        raise HTTPException(400, "새 비밀번호는 6자 이상이어야 합니다.")
    d = _load()
    salt = secrets.token_bytes(16)
    d["users"][username]["salt"] = salt.hex()
    d["users"][username]["hash"] = _hash_pw(new_password, salt).hex()
    _save(d)


# --- 토큰 (stateless, HMAC 서명) -------------------------------------------
def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _secret() -> bytes:
    return bytes.fromhex(_load().get("secret", ""))


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


# --- FastAPI 의존성 --------------------------------------------------------
def require_auth(authorization: str = Header(default="")) -> str:
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization.strip()
    user = verify_token(token)
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user
