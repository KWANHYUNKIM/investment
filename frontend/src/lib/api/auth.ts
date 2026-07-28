// 인증 — 로그인·회원가입·비밀번호 찾기·내 정보

import { request } from "./client";

export interface Health {
  status: string;
  data_dir: string;
}

// ── 관리자 ────────────────────────────────────────────────────────────────
export interface Me { username: string; is_admin: boolean; }

export const authApi = {
  health: () => request<Health>("/api/health"),
  authLogin: (username: string, password: string) =>
    request<{ token: string; username: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  authSendCode: (email: string) =>
    request<{ sent: boolean; email_configured: boolean; dev_code?: string }>("/api/auth/send-code", { method: "POST", body: JSON.stringify({ email }) }),
  authRegister: (username: string, password: string, email: string, name: string, code: string) =>
    request<{ token: string; username: string }>("/api/auth/register", { method: "POST", body: JSON.stringify({ username, password, email, name, code }) }),
  authFindId: (email: string) =>
    request<{ usernames: string[] }>("/api/auth/find-id", { method: "POST", body: JSON.stringify({ email }) }),
  authResetPassword: (username: string, email: string, new_password: string, code: string) =>
    request<{ ok: boolean }>("/api/auth/reset-password", { method: "POST", body: JSON.stringify({ username, email, new_password, code }) }),
  me: () => request<Me>("/api/auth/me"),
  track: (view: string) => request<{ ok: boolean }>("/api/track", { method: "POST", body: JSON.stringify({ view }) }),
};
