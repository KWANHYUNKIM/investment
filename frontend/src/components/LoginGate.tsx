"use client";

import { useEffect, useState } from "react";
import { api, getToken, setToken } from "@/lib/api";

type Mode = "loading" | "authed" | "login" | "register" | "findId" | "resetPw";

const input =
  "mt-1 block w-full rounded border border-[#cdcdcd] px-3 py-2 text-sm outline-none focus:border-[#217346]";

export function LoginGate({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<Mode>("loading");
  const [f, setF] = useState({ username: "", password: "", password2: "", email: "", name: "", code: "" });
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [codeSent, setCodeSent] = useState(false);

  const sendCode = async () => {
    setErr(""); setInfo("");
    if (!f.email.trim()) { setErr("이메일을 먼저 입력하세요."); return; }
    setBusy(true);
    try {
      const r = await api.authSendCode(f.email.trim());
      setCodeSent(true);
      setInfo(r.dev_code
        ? `개발 모드(SMTP 미설정): 인증코드 ${r.dev_code} — 배포 시 이메일로 발송됩니다.`
        : "이메일로 인증코드를 보냈습니다. 10분 안에 입력하세요.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "코드 발송 실패");
    } finally {
      setBusy(false);
    }
  };

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((p) => ({ ...p, [k]: e.target.value }));
  const go = (m: Mode) => { setErr(""); setInfo(""); setMode(m); };

  useEffect(() => {
    setMode(getToken() ? "authed" : "login");
    const onExpired = () => setMode("login");
    window.addEventListener("auth-expired", onExpired);
    return () => window.removeEventListener("auth-expired", onExpired);
  }, []);

  const submit = async () => {
    setErr(""); setInfo("");
    setBusy(true);
    try {
      if (mode === "login") {
        const r = await api.authLogin(f.username.trim(), f.password);
        setToken(r.token); setMode("authed");
      } else if (mode === "register") {
        if (f.password !== f.password2) throw new Error("비밀번호가 일치하지 않습니다.");
        const r = await api.authRegister(f.username.trim(), f.password, f.email.trim(), f.name.trim(), f.code.trim());
        setToken(r.token); setMode("authed");
      } else if (mode === "findId") {
        const r = await api.authFindId(f.email.trim());
        setInfo(r.usernames.length ? `가입된 아이디: ${r.usernames.join(", ")}` : "해당 이메일로 가입된 아이디가 없습니다.");
      } else if (mode === "resetPw") {
        if (f.password !== f.password2) throw new Error("새 비밀번호가 일치하지 않습니다.");
        await api.authResetPassword(f.username.trim(), f.email.trim(), f.password, f.code.trim());
        setInfo("비밀번호가 변경되었습니다. 로그인해 주세요.");
        setF((p) => ({ ...p, password: "", password2: "" }));
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "실패했습니다.");
    } finally {
      setBusy(false);
    }
  };

  if (mode === "authed") return <>{children}</>;
  if (mode === "loading")
    return (
      <div className="flex h-screen items-center justify-center bg-[#fafafa]">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
      </div>
    );

  const title = { login: "로그인", register: "회원가입", findId: "아이디 찾기", resetPw: "비밀번호 찾기" }[mode];
  const cta = { login: "로그인", register: "가입하기", findId: "아이디 찾기", resetPw: "비밀번호 변경" }[mode];

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f3f2f1] p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-xl border border-[#d0d0d0] bg-white shadow">
        <div className="bg-[#217346] px-5 py-4 text-white">
          <div className="text-lg font-bold">투자 자산 관리</div>
          <div className="text-xs text-white/80">{title}</div>
        </div>
        <div className="flex flex-col gap-3 p-5">
          {/* 아이디 (로그인/회원가입/비번찾기) */}
          {mode !== "findId" && (
            <label className="text-xs text-[#555]">아이디
              <input value={f.username} onChange={set("username")} autoComplete="username"
                onKeyDown={(e) => e.key === "Enter" && submit()} className={input} />
            </label>
          )}
          {/* 이름 (회원가입) */}
          {mode === "register" && (
            <label className="text-xs text-[#555]">이름 (선택)
              <input value={f.name} onChange={set("name")} className={input} />
            </label>
          )}
          {/* 이메일 (회원가입/아이디찾기/비번찾기) */}
          {(mode === "register" || mode === "findId" || mode === "resetPw") && (
            <label className="text-xs text-[#555]">이메일{mode === "register" && " (아이디·비번 찾기에 사용)"}
              <input type="email" value={f.email} onChange={set("email")} autoComplete="email"
                onKeyDown={(e) => e.key === "Enter" && submit()} className={input} />
            </label>
          )}
          {/* 이메일 인증코드 (회원가입/비번찾기) */}
          {(mode === "register" || mode === "resetPw") && (
            <label className="text-xs text-[#555]">이메일 인증코드
              <div className="mt-1 flex gap-2">
                <input value={f.code} onChange={set("code")} inputMode="numeric" placeholder="6자리"
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                  className="min-w-0 flex-1 rounded border border-[#cdcdcd] px-3 py-2 text-sm outline-none focus:border-[#217346]" />
                <button type="button" onClick={sendCode} disabled={busy}
                  className="shrink-0 rounded border border-[#217346] px-3 py-2 text-xs font-semibold text-[#217346] hover:bg-[#eef6f0] disabled:opacity-50">
                  {codeSent ? "재발송" : "코드 받기"}
                </button>
              </div>
            </label>
          )}
          {/* 비밀번호 (로그인/회원가입/비번찾기) */}
          {mode !== "findId" && (
            <label className="text-xs text-[#555]">
              {mode === "resetPw" ? "새 비밀번호" : "비밀번호"}{(mode === "register" || mode === "resetPw") && " (6자 이상)"}
              <input type="password" value={f.password} onChange={set("password")}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                onKeyDown={(e) => e.key === "Enter" && submit()} className={input} />
            </label>
          )}
          {(mode === "register" || mode === "resetPw") && (
            <label className="text-xs text-[#555]">비밀번호 확인
              <input type="password" value={f.password2} onChange={set("password2")}
                onKeyDown={(e) => e.key === "Enter" && submit()} className={input} />
            </label>
          )}

          {err && <div className="text-xs text-rose-600">{err}</div>}
          {info && <div className="rounded bg-[#eef4f0] px-2 py-1.5 text-xs text-[#217346]">{info}</div>}

          <button onClick={submit} disabled={busy}
            className="mt-1 rounded bg-[#217346] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
            {busy ? "처리 중…" : cta}
          </button>

          {/* 하단 링크 */}
          <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 pt-1 text-xs text-[#666]">
            {mode !== "login" && <button onClick={() => go("login")} className="hover:text-[#217346] hover:underline">로그인</button>}
            {mode !== "register" && <button onClick={() => go("register")} className="hover:text-[#217346] hover:underline">회원가입</button>}
            {mode !== "findId" && <button onClick={() => go("findId")} className="hover:text-[#217346] hover:underline">아이디 찾기</button>}
            {mode !== "resetPw" && <button onClick={() => go("resetPw")} className="hover:text-[#217346] hover:underline">비밀번호 찾기</button>}
          </div>
        </div>
      </div>
    </div>
  );
}
