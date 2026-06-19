"use client";

import { useEffect, useMemo, useState } from "react";
import { api, FutureTheme as FT, FutureThemeIndexItem, FutureThemeMember, FutureThemesStatus } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";

function retStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  const a = Math.min(Math.abs(v) / 40, 1) * 0.62;
  if (v > 0) return { backgroundColor: `rgba(224,49,49,${a})`, color: a > 0.4 ? "#fff" : RED };
  if (v < 0) return { backgroundColor: `rgba(28,126,214,${a})`, color: a > 0.4 ? "#fff" : BLUE };
  return { color: "#666" };
}
function leanColor(l?: string) {
  return l === "긍정" ? RED : l === "부정" ? BLUE : "#666";
}
// market_cap(원) → 조/억
function cap(v: number | null | undefined): string {
  if (v == null || v === 0) return "—";
  if (v >= 1e12) return `${(v / 1e12).toFixed(1)}조`;
  if (v >= 1e8) return `${Math.round(v / 1e8).toLocaleString("ko-KR")}억`;
  return v.toLocaleString("ko-KR");
}
function won(v: number | null | undefined): string {
  return v == null ? "—" : `₩${v.toLocaleString("ko-KR")}`;
}
function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v}%`;
}

export function FutureTheme() {
  const [themes, setThemes] = useState<FutureThemeIndexItem[]>([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<FT | null>(null);
  const [status, setStatus] = useState<FutureThemesStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .futureThemes()
      .then((r) => {
        setThemes(r.themes);
        if (r.themes[0]) setSelected(r.themes[0].key);
      })
      .catch((e) => setErr(e?.message ?? "미래 성장테마를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
    api.futureThemesStatus().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    setDetail(null);
    api.futureTheme(selected).then(setDetail).catch(() => setDetail(null));
  }, [selected]);

  if (err) return <div className="py-20 text-center text-sm text-rose-600">{err}</div>;

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#217346] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold">미래 성장테마.xlsx</span>
        {status?.running ? (
          <span className="flex items-center gap-1.5 text-xs" title={`마지막 갱신 ${status.last_run ?? "—"} · 누적 스냅샷 ${status.snapshot_dates?.length ?? 0}일 · ${Math.round((status.interval_sec ?? 1800) / 60)}분 주기`}>
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[#7ee2a0]" />
            <span className="font-bold text-[#bff5cf]">자동 크롤링 중</span>
            <span className="text-white/70">
              {Math.round((status.interval_sec ?? 1800) / 60)}분 주기 · 누적 {status.snapshot_dates?.length ?? 0}일
              {status.last_run && ` · 갱신 ${status.last_run.slice(11, 16)}`}
            </span>
          </span>
        ) : (
          <span className="text-xs text-white/80">지금 시대가 구축 중인 산업 + 종목 미래가치 (뉴스 실시간 취합)</span>
        )}
      </div>

      <div className="flex min-h-[72vh]">
        {/* left: theme list */}
        <aside className="flex w-[320px] shrink-0 flex-col border-r border-[#d0d0d0] bg-[#faf9fc]">
          <div className="border-b border-[#d0d0d0] bg-[#eef0ee] px-3 py-1.5 text-[11px] font-semibold text-[#1f5132]">
            메가트렌드 (모멘텀순)
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loading ? (
              <div className="py-10 text-center text-sm text-[#888]">불러오는 중…</div>
            ) : (
              themes.map((t) => {
                const active = t.key === selected;
                return (
                  <button
                    key={t.key}
                    onClick={() => setSelected(t.key)}
                    className={`flex w-full flex-col gap-0.5 border-b border-[#eee] px-3 py-2 text-left transition ${
                      active ? "bg-[#e3efe7]" : "hover:bg-[#eef3ee]"
                    }`}
                  >
                    <span className="flex items-center gap-1.5">
                      <span className={`text-[13px] ${active ? "font-bold text-[#1f5132]" : "text-[#1f1f1f]"}`}>{t.label}</span>
                      <span className="ml-auto text-[10px] font-bold" style={{ color: leanColor(t.lean) }}>{t.lean}</span>
                    </span>
                    <span className="flex items-center gap-2 text-[10px] text-[#999]">
                      <span>뉴스 {t.news_count}건</span>
                      <span>· 종목 {t.member_count}</span>
                      {t.beaten_count > 0 && <span style={{ color: BLUE }}>· 후보 {t.beaten_count}</span>}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </aside>

        {/* right: detail */}
        <main className="min-w-0 flex-1 overflow-y-auto bg-[#fafafa] p-4">
          {!detail ? (
            <div className="py-24 text-center text-sm text-[#888]">테마를 선택하세요.</div>
          ) : (
            <ThemeDetail t={detail} />
          )}
        </main>
      </div>
    </div>
  );
}

function ThemeDetail({ t }: { t: FT }) {
  const beaten = useMemo(() => t.members.filter((m) => m.beaten), [t.members]);
  return (
    <div className="space-y-4">
      {/* header */}
      <div className="rounded border border-[#d0d0d0] bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-lg font-bold text-[#1f1f1f]">{t.label}</h2>
          <span className="rounded px-1.5 py-0.5 text-[11px] font-bold text-white" style={{ background: leanColor(t.news.lean) }}>
            뉴스 {t.news.lean}
          </span>
        </div>
        <p className="mt-1.5 text-sm leading-relaxed text-[#444]">{t.desc}</p>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[#666]">
          <span>실시간 뉴스 <b className="text-[#1f5132]">{t.news.count}</b>건 (긍정 {t.news.pos} · 부정 {t.news.neg})</span>
          <span>매핑 종목 <b className="text-[#1f5132]">{t.member_count}</b></span>
          <span style={{ color: BLUE }}>지금 빠진 미래가치 후보 <b>{t.beaten_count}</b></span>
        </div>
      </div>

      {/* what's being built — news */}
      <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
        <div className="border-b border-[#d0d0d0] bg-[#e8efe8] px-3 py-1.5 text-sm font-bold text-[#1f5132]">
          지금 무엇이 구축·투자되고 있나 (실시간 뉴스)
        </div>
        {t.news.digest.length > 0 && (
          <div className="border-b border-[#eee] bg-[#f1f5f1] px-3 py-2">
            <div className="mb-1 text-[11px] font-bold text-[#1f5132]">대표 내용 (여러 매체 취합)</div>
            <ul className="space-y-0.5">
              {t.news.digest.map((d, i) => (
                <li key={i} className="flex gap-1.5 text-[12px] leading-snug text-[#555]"><span className="text-[#9aa39a]">·</span><span>{d}</span></li>
              ))}
            </ul>
          </div>
        )}
        <ul className="divide-y divide-[#f0f0f0]">
          {t.news.headlines.map((h, i) => (
            <li key={i}>
              <a href={h.link || "#"} target="_blank" rel="noopener noreferrer" className="flex items-start gap-2 px-3 py-1.5 text-sm text-[#333] hover:bg-[#f1f5f1]">
                <span className="mt-0.5 text-[#9aa39a]">›</span>
                <span className="flex-1">{h.title}<span className="ml-1.5 text-xs text-[#999]">{h.source}</span></span>
              </a>
            </li>
          ))}
          {t.news.headlines.length === 0 && <li className="px-3 py-3 text-sm text-[#999]">관련 뉴스가 충분히 취합되지 않았습니다.</li>}
        </ul>
      </section>

      {/* future-value candidates (beaten/blue stocks) */}
      {beaten.length > 0 && (
        <section className="overflow-hidden rounded border border-[#9cc0e8] bg-white shadow-sm">
          <div className="border-b border-[#9cc0e8] bg-[#dcebfb] px-3 py-1.5 text-sm font-bold text-[#1a3a5e]" style={{ background: "#e3edf9" }}>
            지금 빠졌지만 미래가치 후보 — 이 테마 속 하락(파란) 종목 {beaten.length}개
          </div>
          <MemberTable rows={beaten} highlightBeaten={false} />
          <p className="px-3 py-1.5 text-[11px] leading-relaxed text-[#999]">
            이 테마(미래 성장 산업)에 속하지만 최근 3개월 하락했거나 고점 대비 25%+ 빠진 종목들 — 테마가 구조적으로 성장하면 <b>미래가치 재평가 후보</b>가 될 수 있습니다. (투자 권유 아님)
          </p>
        </section>
      )}

      {/* all members */}
      <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
        <div className="border-b border-[#d0d0d0] bg-[#a9d08e] px-3 py-1.5 text-sm font-bold text-[#244d1a]">
          테마 매핑 종목 (시총순) — 총 {t.members.length}개
        </div>
        <MemberTable rows={t.members} highlightBeaten />
        <p className="px-3 py-1.5 text-[11px] leading-relaxed text-[#999]">
          종목은 업종(WICS)·주요제품·기업명에 테마 키워드가 매칭된 결과입니다(자동 추출이라 일부 부정확할 수 있음). 빨강=상승·파랑=하락. 파란 배경 = 미래가치 후보(최근 하락).
        </p>
      </section>
    </div>
  );
}

function MemberTable({ rows, highlightBeaten }: { rows: FutureThemeMember[]; highlightBeaten: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="bg-[#f0f0f0] text-xs text-[#444]">
            <th className="min-w-[150px] border border-[#e0e0e0] px-2 py-1.5 text-left font-semibold">종목</th>
            <th className="w-24 border border-[#e0e0e0] px-2 py-1.5 text-left font-semibold">제품/사업</th>
            <th className="w-20 border border-[#e0e0e0] px-2 py-1.5 text-right font-semibold">시총</th>
            <th className="w-24 border border-[#e0e0e0] px-2 py-1.5 text-right font-semibold">현재가</th>
            <th className="w-16 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">등락%</th>
            <th className="w-16 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">1개월</th>
            <th className="w-16 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">3개월</th>
            <th className="w-16 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">1년</th>
            <th className="w-20 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">고점대비</th>
            <th className="w-14 border border-[#e0e0e0] px-2 py-1.5 text-right font-semibold">PER</th>
            <th className="w-14 border border-[#e0e0e0] px-2 py-1.5 text-right font-semibold">PBR</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.ticker} className={highlightBeaten && m.beaten ? "bg-[#eef4fb]" : "hover:bg-[#fff7e6]"}>
              <td className="border border-[#eee] px-2 py-1.5">
                <span className="font-medium text-[#1f1f1f]">{m.name ?? m.ticker}</span>
                <span className="ml-1 font-mono text-[11px] text-[#999]">{m.ticker}</span>
                {m.beaten && <span className="ml-1 rounded bg-[#d7e6f7] px-1 text-[9px] font-bold text-[#1a3a5e]">미래가치 후보</span>}
              </td>
              <td className="border border-[#eee] px-2 py-1.5 text-[11px] text-[#777]">{(m.products ?? m.wics_sector ?? "—")?.slice(0, 18)}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums text-[#333]">{cap(m.market_cap)}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums text-[#333]">{won(m.close)}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-center font-bold tabular-nums" style={retStyle(m.change_pct)}>{pct(m.change_pct)}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-center tabular-nums" style={retStyle(m.ret_1m)}>{pct(m.ret_1m)}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-center tabular-nums" style={retStyle(m.ret_3m)}>{pct(m.ret_3m)}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-center tabular-nums" style={retStyle(m.ret_12m)}>{pct(m.ret_12m)}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-center tabular-nums" style={retStyle(m.pct_from_high)}>{pct(m.pct_from_high)}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums text-[#555]">{m.per ?? "—"}</td>
              <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums text-[#555]">{m.pbr ?? "—"}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={11} className="border border-[#eee] px-3 py-4 text-center text-sm text-[#999]">매핑된 종목이 없습니다.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
