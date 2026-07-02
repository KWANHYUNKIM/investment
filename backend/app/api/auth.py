"""회원가입/로그인/찾기 API (공개 라우터 — 인증 없이 접근)."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
def status():
    return {"has_users": auth.has_users()}


@router.post("/send-code")
def send_code(email: str = Body(..., embed=True)):
    """이메일로 인증코드 발송(회원가입·비번찾기 공용). SMTP 미설정 시 dev_code 반환."""
    return auth.send_code(email)


@router.post("/register")
def register(username: str = Body(...), password: str = Body(...),
             email: str = Body(default=""), name: str = Body(default=""), code: str = Body(default="")):
    """회원가입(이메일 인증코드 필요) → 토큰 반환."""
    token = auth.register(username, password, email, name, code)
    return {"token": token, "username": username}


@router.post("/login")
def login(username: str = Body(...), password: str = Body(...)):
    token = auth.login(username, password)
    return {"token": token, "username": username}


@router.post("/find-id")
def find_id(email: str = Body(..., embed=True)):
    """이메일로 아이디 찾기 (일부 가림 처리)."""
    return {"usernames": auth.find_ids_by_email(email)}


@router.post("/reset-password")
def reset_password(username: str = Body(...), email: str = Body(...),
                   new_password: str = Body(...), code: str = Body(default="")):
    """아이디+이메일 일치 & 이메일 인증코드 확인 시 비밀번호 재설정."""
    auth.reset_password(username, email, new_password, code)
    return {"ok": True}


@router.get("/me")
def me(user: str = Depends(auth.require_auth)):
    return {"username": user}


@router.post("/change-password")
def change_password(old_password: str = Body(...), new_password: str = Body(...),
                    user: str = Depends(auth.require_auth)):
    auth.change_password(user, old_password, new_password)
    return {"ok": True}
