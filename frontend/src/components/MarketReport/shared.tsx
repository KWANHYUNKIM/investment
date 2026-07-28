"use client";

import { ReactNode } from "react";

// KR convention: red = up / buy, blue = down / sell.
export const RED = "#c92a2a";

export const BLUE = "#1971c2";

// Conditional-format heatmap for a percent move (mirrors the 전종목 grid).
export function retStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  const a = Math.min(Math.abs(v) / 40, 1) * 0.62;
  if (v > 0) return { backgroundColor: `rgba(224,49,49,${a})`, color: a > 0.4 ? "#fff" : RED };
  if (v < 0) return { backgroundColor: `rgba(28,126,214,${a})`, color: a > 0.4 ? "#fff" : BLUE };
  return { color: "#666" };
}

/* 투자자별 매매 동향 (일단위) — 시장 전체 순매수 금액(억원). 빨강=순매수, 파랑=순매도. */
export function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const s = Math.abs(v) >= 10000 ? `${(Math.abs(v) / 10000).toFixed(2)}조` : `${Math.abs(v).toLocaleString("ko-KR")}억`;
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s}`;
}

export function flowStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666", fontWeight: 700 };
}

export function fmtSigned(v: number | null): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}

/* ── worksheet frame ──────────────────────────────────────── */
export function Sheet({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold">
          {title}
        </span>
        {right}
      </div>
      {children}
    </div>
  );
}

/* a labelled spreadsheet block with a coloured group-header strip */
export function Block({ label, color, fg, children }: { label: string; color: string; fg: string; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
      <div className="border-b border-[#d0d0d0] bg-[#e8efe8] px-3 py-1.5 text-sm font-bold text-[#1f5132]">
        {label}
      </div>
      {children}
    </section>
  );
}

export function BreadthStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-[#888]">{label}</div>
      <div className="text-xl font-bold tabular-nums" style={{ color }}>
        {value.toLocaleString("ko-KR")}
      </div>
    </div>
  );
}

export function Th({ children, w, center, right }: { children?: ReactNode; w?: string; center?: boolean; right?: boolean }) {
  return (
    <th
      style={{ width: w }}
      className={`border border-[#d0d0d0] px-2 py-1.5 font-semibold ${center ? "text-center" : right ? "text-right" : "text-left"}`}
    >
      {children}
    </th>
  );
}

export function GroupTh({
  children,
  span = 1,
  w,
  bg,
  fg,
}: {
  children?: ReactNode;
  span?: number;
  w?: number;
  bg: string;
  fg: string;
}) {
  return (
    <th
      colSpan={span}
      style={{ width: w, background: bg, color: fg }}
      className="border border-white px-2 py-1 text-center text-xs font-bold"
    >
      {children}
    </th>
  );
}

export function ColTh({ children, w, center, right }: { children?: ReactNode; w: number; center?: boolean; right?: boolean }) {
  return (
    <th
      style={{ width: w }}
      className={`border border-[#d6d6d6] px-2 py-1.5 font-semibold ${center ? "text-center" : right ? "text-right" : "text-left"}`}
    >
      {children}
    </th>
  );
}

/* small reusable digest bullet list (대표 내용 — 여러 매체 취합) */
export function DigestList({ lines, color = "#9dc3e6" }: { lines: string[]; color?: string }) {
  if (!lines || lines.length === 0) return null;
  return (
    <ul className="space-y-0.5">
      {lines.map((line, i) => (
        <li key={i} className="flex gap-1.5 text-[12px] leading-snug text-[#555]">
          <span style={{ color }}>·</span>
          <span>{line}</span>
        </li>
      ))}
    </ul>
  );
}

/* shared news list (used by the macro 국내/해외 columns) */
export function NewsList({ items, dot }: { items: { title: string; link: string; source: string }[]; dot: string }) {
  return (
    <ul className="divide-y divide-[#eee]">
      {items.map((a, i) => (
        <li key={i}>
          <a
            href={a.link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-2 px-3 py-1.5 text-sm text-[#333] hover:bg-[#fff7e6]"
          >
            <span className="mt-0.5" style={{ color: dot }}>›</span>
            <span className="flex-1">
              {a.title}
              <span className="ml-1.5 text-xs text-[#999]">{a.source}</span>
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

/* 거래원 sheet — which brokerage houses (창구) drove each stock's trade.
   외국계 창구 매수/매도는 외국인 수급의 대용 지표로 읽힌다. */
