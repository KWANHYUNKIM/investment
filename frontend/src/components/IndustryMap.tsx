"use client";

import { useEffect, useMemo, useState, ReactNode } from "react";
import {
  api,
  IndustryIndexItem,
  IndustryDetailResponse,
  IndustryMember,
  ThemeBucket,
  ThemeItem,
} from "@/lib/api";
import { GlobalMap } from "./GlobalMap";

const RED = "#c92a2a";
const BLUE = "#1971c2";

// group-header colour per research theme
const THEME_COLOR: Record<string, { bg: string; fg: string }> = {
  tech: { bg: "#a9d08e", fg: "#244d1a" },
  ma: { bg: "#9dc3e6", fg: "#1a3a5e" },
  deal: { bg: "#f4b084", fg: "#7a3a0c" },
  perf: { bg: "#c6e0b4", fg: "#2d5016" },
  strategy: { bg: "#d9d9d9", fg: "#333" },
  risk: { bg: "#f4b3b3", fg: "#7a1a1a" },
};

function marcap(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e12) return `${(v / 1e12).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조`;
  if (v >= 1e8) return `${(v / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}억`;
  return v.toLocaleString("ko-KR");
}

// op_profit / sales 등은 億원 단위 — 1만억 이상이면 兆로.
function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const neg = v < 0;
  const a = Math.abs(v);
  const s = a >= 10000 ? `${(a / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조` : `${Math.round(a).toLocaleString("ko-KR")}억`;
  return neg ? `-${s}` : s;
}

function pnlStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666" };
}

function retStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  const a = Math.min(Math.abs(v) / 40, 1) * 0.62;
  if (v > 0) return { backgroundColor: `rgba(224,49,49,${a})`, color: a > 0.4 ? "#fff" : RED };
  if (v < 0) return { backgroundColor: `rgba(28,126,214,${a})`, color: a > 0.4 ? "#fff" : BLUE };
  return { color: "#666" };
}

export function IndustryMap() {
  const [view, setView] = useState<"kr" | "global">("kr");
  const [index, setIndex] = useState<IndustryIndexItem[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [detail, setDetail] = useState<IndustryDetailResponse | null>(null);
  const [loadingIdx, setLoadingIdx] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .industries()
      .then((r) => {
        setIndex(r.industries);
        if (r.industries[0]) setSelected(r.industries[0].industry);
      })
      .catch((e) => setErr(e?.message ?? "업종 목록을 불러오지 못했습니다."))
      .finally(() => setLoadingIdx(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoadingDetail(true);
    api
      .industry(selected)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false));
  }, [selected]);

  const filtered = useMemo(() => {
    const n = q.trim().toLowerCase();
    if (!n) return index;
    return index.filter(
      (g) => g.industry.toLowerCase().includes(n) || (g.leader ?? "").toLowerCase().includes(n),
    );
  }, [index, q]);

  if (err) return <div className="py-20 text-center text-sm text-rose-600">{err}</div>;

  const Toggle = (
    <div className="mb-2 inline-flex rounded-md border border-[#cfcfcf] bg-white p-0.5 text-xs font-semibold">
      <button
        onClick={() => setView("kr")}
        className={`rounded px-3 py-1 transition ${view === "kr" ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#eef6f0]"}`}
      >
         국내 업종
      </button>
      <button
        onClick={() => setView("global")}
        className={`rounded px-3 py-1 transition ${view === "global" ? "bg-[#1a3a5e] text-white" : "text-[#555] hover:bg-[#eef6ff]"}`}
      >
         글로벌 경쟁
      </button>
    </div>
  );

  if (view === "global")
    return (
      <div>
        {Toggle}
        <GlobalMap />
      </div>
    );

  return (
    <div>
      {Toggle}
      <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      {/* sheet title bar */}
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold"> 산업·경쟁지도.xlsx</span>
        <span className="text-xs text-white/80">
          {index.length}개 업종 · WICS(네이버 금융) 기준 · 기술·M&A·계약·실적·전략 취합
        </span>
      </div>

      <div className="flex min-h-[70vh]">
        {/* ── left: industry list ─────────────────────────────── */}
        <aside className="flex w-[330px] shrink-0 flex-col border-r border-[#d0d0d0] bg-[#fafafa]">
          <div className="border-b border-[#d0d0d0] bg-[#f3f2f1] p-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="업종·대표기업 검색"
              className="w-full rounded border border-[#bdbdbd] bg-white px-2.5 py-1.5 text-sm outline-none focus:border-[#217346]"
            />
          </div>
          <div className="grid grid-cols-[1fr_auto_auto] border-b border-[#d0d0d0] bg-[#f0f0f0] px-2 py-1 text-[11px] font-semibold text-[#555]">
            <span>업종 (대표기업)</span>
            <span className="px-2 text-right">기업수</span>
            <span className="text-right">평균%</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loadingIdx ? (
              <div className="py-10 text-center text-sm text-[#888]">불러오는 중…</div>
            ) : (
              filtered.map((g) => {
                const active = g.industry === selected;
                return (
                  <button
                    key={g.industry}
                    onClick={() => setSelected(g.industry)}
                    className={`grid w-full grid-cols-[1fr_auto_auto] items-center gap-1 border-b border-[#eee] px-2 py-1.5 text-left transition ${
                      active ? "bg-[#cfe3d3]" : "hover:bg-[#fff7e6]"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className={`block truncate text-[13px] ${active ? "font-bold text-[#217346]" : "text-[#1f1f1f]"}`}>
                        {g.industry}
                      </span>
                      <span className="block truncate text-[11px] text-[#999]">
                        {g.leader} · 영업익 <b className="text-[#555]">{eok(g.op_profit)}</b>
                        {g.op_margin != null ? ` (${g.op_margin}%)` : ""}
                      </span>
                    </span>
                    <span className="px-2 text-right text-xs tabular-nums text-[#555]">{g.count}</span>
                    <span
                      className="rounded px-1.5 py-0.5 text-right text-xs font-semibold tabular-nums"
                      style={retStyle(g.avg_change_pct)}
                    >
                      {g.avg_change_pct != null ? `${g.avg_change_pct > 0 ? "+" : ""}${g.avg_change_pct}` : "—"}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </aside>

        {/* ── right: selected industry detail ─────────────────── */}
        <main className="min-w-0 flex-1 overflow-x-auto bg-[#fafafa] p-4">
          {loadingDetail && !detail ? (
            <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
              <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
              업종 뉴스 분석 중… <span className="text-[#aaa]">(최초 수초)</span>
            </div>
          ) : !detail ? (
            <div className="py-24 text-center text-sm text-[#888]">좌측에서 업종을 선택하세요.</div>
          ) : (
            <Detail detail={detail} loading={loadingDetail} />
          )}
        </main>
      </div>
      </div>
    </div>
  );
}

function Detail({ detail, loading }: { detail: IndustryDetailResponse; loading: boolean }) {
  const g = detail.group;
  const r = detail.research;
  return (
    <div className="space-y-4">
      {/* heading + summary */}
      <div className="rounded border border-[#d0d0d0] bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-lg font-bold text-[#1f1f1f]">{g.industry}</h2>
          <span className="text-sm text-[#666]">
            경쟁군 <b className="text-[#217346]">{g.count}</b>개사 · 대표 {g.leader} · 합산시총 {marcap(g.market_cap)}
            {g.op_profit != null && (
              <>
                {" · 합산 영업이익 "}
                <b style={pnlStyle(g.op_profit)}>{eok(g.op_profit)}</b>
                {g.op_margin != null ? ` (영업이익률 ${g.op_margin}%` : ""}
                {g.op_count != null ? `${g.op_margin != null ? ", " : " ("}실적 ${g.op_count}개사)` : g.op_margin != null ? ")" : ""}
              </>
            )}
          </span>
          {loading && <span className="text-xs text-[#aaa]">뉴스 갱신 중…</span>}
        </div>
        {r?.summary && <p className="mt-2 text-sm leading-relaxed text-[#333]">{r.summary}</p>}
      </div>

      {/* member companies (competition group) */}
      <Block label="경쟁 기업 (시총순) · 영업이익 · 주요 제품/사업" color="#a9d08e" fg="#244d1a">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="bg-[#f0f0f0] text-xs text-[#444]">
                <Th w={34} center>#</Th>
                <Th w={150}>종목명</Th>
                <Th w={64} center>코드</Th>
                <Th w={92} right>시총</Th>
                <Th w={64} center>등락%</Th>
                <Th w={96} right>영업이익</Th>
                <Th w={64} center>이익률</Th>
                <Th w={70} center>전년比</Th>
                <Th>주요 제품/사업</Th>
              </tr>
            </thead>
            <tbody>
              {g.members.map((m, i) => (
                <MemberRow key={m.ticker} m={m} n={i + 1} />
              ))}
            </tbody>
          </table>
        </div>
      </Block>

      {/* research theme sheets */}
      {r ? (
        r.themes.filter((t) => t.count > 0).length === 0 ? (
          <div className="rounded border border-[#d0d0d0] bg-white px-4 py-6 text-center text-sm text-[#888]">
            분류된 업종 뉴스 이슈가 아직 없습니다. (스케줄러가 계속 수집·누적합니다)
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {r.themes
              .filter((t) => t.count > 0)
              .map((t) => (
                <ThemeSheet key={t.key} t={t} />
              ))}
          </div>
        )
      ) : (
        <div className="rounded border border-[#d0d0d0] bg-white px-4 py-6 text-center text-sm text-[#888]">
          이 업종의 뉴스 리서치를 불러오지 못했습니다.
        </div>
      )}
    </div>
  );
}

function MemberRow({ m, n }: { m: IndustryMember; n: number }) {
  return (
    <tr className="hover:bg-[#fff7e6]">
      <td className="border border-[#e6e6e6] bg-[#f0f0f0] px-1 text-center text-xs text-[#999]">{n}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 font-medium text-[#1155cc]">{m.name}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center font-mono text-xs text-[#555]">{m.ticker}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-right tabular-nums text-[#1f1f1f]">{marcap(m.market_cap)}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center font-bold tabular-nums" style={retStyle(m.change_pct)}>
        {m.change_pct != null ? `${m.change_pct > 0 ? "+" : ""}${m.change_pct}%` : "—"}
      </td>
      <td
        className="border border-[#e6e6e6] px-2 py-1.5 text-right font-semibold tabular-nums"
        style={pnlStyle(m.op_profit)}
        title={m.fy ? `${m.fy} 기준` : undefined}
      >
        {eok(m.op_profit)}
      </td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums text-[#555]">
        {m.op_margin != null ? `${m.op_margin}%` : "—"}
      </td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums" style={pnlStyle(m.op_yoy)}>
        {m.op_yoy != null ? `${m.op_yoy > 0 ? "+" : ""}${m.op_yoy}%` : "—"}
      </td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-xs text-[#555]">{m.products ?? "—"}</td>
    </tr>
  );
}

function ThemeSheet({ t }: { t: ThemeBucket }) {
  const c = THEME_COLOR[t.key] ?? { bg: "#d9d9d9", fg: "#333" };
  return (
    <Block label={`${t.label} · ${t.count}건`} color={c.bg} fg={c.fg}>
      <table className="w-full border-collapse text-[13px]">
        <tbody>
          {t.items.map((it, i) => (
            <ThemeRow key={`${it.link}-${i}`} it={it} />
          ))}
        </tbody>
      </table>
    </Block>
  );
}

function ThemeRow({ it }: { it: ThemeItem }) {
  return (
    <tr className="hover:bg-[#fff7e6]">
      <td className="w-[110px] border border-[#eee] px-2 py-1.5 align-top text-xs font-semibold text-[#333]">
        {it.company}
      </td>
      <td className="border border-[#eee] px-2 py-1.5 align-top">
        <a
          href={it.link ?? "#"}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[13px] leading-snug text-[#222] hover:text-[#1155cc] hover:underline"
        >
          {it.title}
        </a>
        {it.source && <span className="ml-1 text-[11px] text-[#999]">· {it.source}</span>}
      </td>
    </tr>
  );
}

function Block({ label, color, fg, children }: { label: string; color: string; fg: string; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
      <div className="border-b border-white px-3 py-1.5 text-sm font-bold" style={{ background: color, color: fg }}>
        {label}
      </div>
      {children}
    </section>
  );
}

function Th({ children, w, center, right }: { children?: ReactNode; w?: number; center?: boolean; right?: boolean }) {
  return (
    <th
      style={{ width: w }}
      className={`border border-[#d6d6d6] px-2 py-1.5 font-semibold ${center ? "text-center" : right ? "text-right" : "text-left"}`}
    >
      {children}
    </th>
  );
}
