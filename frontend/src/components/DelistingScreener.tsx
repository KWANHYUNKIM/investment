"use client";

import { useEffect, useMemo, useState } from "react";
import { api, DelistingBoard, DelistingRow } from "@/lib/api";

const LEVEL_STYLE: Record<number, { bg: string; fg: string; label: string }> = {
  3: { bg: "#fce4e4", fg: "#b02a37", label: "상폐위험" },
  2: { bg: "#fff0e0", fg: "#c05621", label: "관리위험" },
  1: { bg: "#fff9db", fg: "#8a6d00", label: "주의" },
};
const SEV_COLOR: Record<number, string> = { 3: "#b02a37", 2: "#c05621", 1: "#8a6d00" };
const KIND_COLOR: Record<string, string> = {
  "관리·상폐": "#b02a37",
  "감사·정정": "#c05621",
  "잠정실적": "#7048a8",
};

function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const e = v / 1e8;
  const s = e < 0 ? "-" : "";
  const a = Math.abs(e);
  return `${s}${a >= 1000 ? a.toLocaleString("ko-KR", { maximumFractionDigits: 0 }) : a.toFixed(1)}억`;
}
function dartUrl(rcept: string) {
  return `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${rcept}`;
}
function fmtDate(d: string) {
  return d && d.length === 8 ? `${d.slice(2, 4)}.${d.slice(4, 6)}.${d.slice(6, 8)}` : d;
}

export function DelistingScreener() {
  const [d, setD] = useState<DelistingBoard | null>(null);
  const [err, setErr] = useState("");
  const [level, setLevel] = useState<0 | 1 | 2 | 3>(0);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => {
    let alive = true;
    api.delistingRisk().then((r) => alive && setD(r)).catch((e) => alive && setErr(e?.message ?? "불러오기 실패"));
    return () => { alive = false; };
  }, []);

  const rows = useMemo(() => {
    if (!d) return [];
    const kw = q.trim();
    return d.rows.filter((r) => {
      if (level && r.level !== level) return false;
      if (kw && !(`${r.name}${r.ticker}`.includes(kw))) return false;
      return true;
    });
  }, [d, level, q]);

  function toggle(tk: string) {
    setOpen((prev) => {
      const n = new Set(prev);
      if (n.has(tk)) n.delete(tk); else n.add(tk);
      return n;
    });
  }

  const s = d?.summary ?? {};

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#b02a37] px-4 py-2 text-white">
        <span className="text-sm font-semibold">관리종목·상폐 경보.xlsx</span>
        {d && (
          <span className="text-xs text-white/85">
            {d.count}종목 위험 · 공시경보 {s["공시경보_종목"] ?? 0}종목
            {d.alerts_generated_at ? ` · 공시 ${d.alerts_generated_at}` : ""}
          </span>
        )}
      </div>

      {err && !d ? (
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      ) : !d ? (
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#e0c0c0] border-t-[#b02a37]" />
          재무요건·공시 스캔 중…
        </div>
      ) : (
        <>
          {/* 요약 + 필터 */}
          <div className="flex flex-wrap items-center gap-2 border-b border-[#eee] bg-[#faf7f7] px-3 py-2">
            {([[3, "상폐위험"], [2, "관리위험"], [1, "주의"], [0, "전체"]] as const).map(([lv, lb]) => {
              const active = level === lv;
              const st = LEVEL_STYLE[lv as number];
              const cnt = lv === 0 ? d.count : (s[lb] ?? 0);
              return (
                <button
                  key={lv}
                  onClick={() => setLevel(lv as 0 | 1 | 2 | 3)}
                  className="rounded-full px-3 py-1 text-[11px] font-semibold transition"
                  style={{
                    background: active ? (st?.fg ?? "#333") : (st?.bg ?? "#eee"),
                    color: active ? "#fff" : (st?.fg ?? "#555"),
                  }}
                >
                  {lb} {cnt}
                </button>
              );
            })}
            <span className="mx-1 text-[11px] text-[#b8a0a0]">
              지정 관리종목 {s["지정_관리종목"] ?? 0}
            </span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="종목명·코드 검색"
              className="ml-auto w-40 rounded border border-[#ddd] px-2 py-1 text-[12px] outline-none focus:border-[#b02a37]"
            />
          </div>

          <div className="max-h-[calc(100vh-240px)] overflow-auto">
            <table className="w-full text-[12px]">
              <thead className="sticky top-0 z-10 bg-[#f5f5f5] text-left text-[10px] uppercase tracking-wide text-[#999]">
                <tr className="border-b border-[#e5e5e5]">
                  <th className="px-3 py-2 font-semibold">#</th>
                  <th className="px-3 py-2 font-semibold">종목</th>
                  <th className="px-3 py-2 font-semibold">위험등급</th>
                  <th className="px-3 py-2 text-right font-semibold">영업손실</th>
                  <th className="px-3 py-2 text-right font-semibold">최근매출</th>
                  <th className="px-3 py-2 text-right font-semibold">영업이익</th>
                  <th className="px-3 py-2 text-right font-semibold">자본잠식</th>
                  <th className="px-3 py-2 font-semibold">사유 / 감사·정정 공시</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <RowView key={r.ticker} r={r} i={i} open={open.has(r.ticker)} onToggle={() => toggle(r.ticker)} />
                ))}
                {rows.length === 0 && (
                  <tr><td colSpan={8} className="py-16 text-center text-[#bbb]">해당 조건의 종목이 없습니다.</td></tr>
                )}
              </tbody>
            </table>
            <div className="px-3 py-2 text-[10px] leading-relaxed text-[#bbb]">{d.note} · 생성 {d.generated_at}</div>
          </div>
        </>
      )}
    </div>
  );
}

function RowView({ r, i, open, onToggle }: { r: DelistingRow; i: number; open: boolean; onToggle: () => void }) {
  const st = LEVEL_STYLE[r.level];
  const hasAlerts = r.alerts.length > 0;
  return (
    <>
      <tr
        className="border-t border-[#f2f2f2] align-top hover:bg-[#fdf8f8]"
        style={{ cursor: hasAlerts ? "pointer" : "default" }}
        onClick={hasAlerts ? onToggle : undefined}
      >
        <td className="px-3 py-2 text-[#c0a0a0]">{i + 1}</td>
        <td className="px-3 py-2">
          <div className="font-semibold text-[#333]">{r.name}</div>
          <div className="text-[10px] text-[#aaa]">
            {r.ticker} · {r.market}
            {r.dept ? ` · ${r.dept}` : ""}
            {r.tech_special ? " · 기술특례" : ""}
          </div>
        </td>
        <td className="px-3 py-2">
          <span
            className="inline-block rounded px-2 py-0.5 text-[11px] font-bold"
            style={{ background: st?.bg, color: st?.fg }}
          >
            {r.level_name}
          </span>
          {r.designated && (
            <div className="mt-1 text-[10px] font-semibold text-[#b02a37]">● {r.designated} 지정</div>
          )}
        </td>
        <td className="px-3 py-2 text-right tabular-nums">
          {r.consec_op_loss > 0 ? (
            <span className="font-semibold" style={{ color: r.consec_op_loss >= 4 ? "#b02a37" : "#c05621" }}>
              {r.consec_op_loss}년
            </span>
          ) : <span className="text-[#ccc]">—</span>}
        </td>
        <td className="px-3 py-2 text-right tabular-nums text-[#555]">{eok(r.latest_sales)}</td>
        <td className="px-3 py-2 text-right tabular-nums" style={{ color: (r.latest_op ?? 0) < 0 ? "#1971c2" : "#333" }}>
          {eok(r.latest_op)}
        </td>
        <td className="px-3 py-2 text-right tabular-nums" style={{ color: (r.impair_rate ?? 0) >= 50 ? "#b02a37" : "#999" }}>
          {r.impair_rate != null && r.impair_rate > 0 ? `${r.impair_rate}%` : "—"}
        </td>
        <td className="px-3 py-2">
          <div className="flex flex-wrap gap-1">
            {r.reasons.map((rs, k) => (
              <span
                key={k}
                className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                style={{ background: "#f4eeee", color: SEV_COLOR[rs.sev] ?? "#666" }}
              >
                {rs.text}
              </span>
            ))}
          </div>
          {hasAlerts && (
            <div className="mt-1 flex items-center gap-1 text-[10px] font-semibold" style={{ color: KIND_COLOR[r.alerts[0].kind] ?? "#a33" }}>
              <span>📄 {fmtDate(r.alerts[0].date)} {r.alerts[0].report_nm}</span>
              {r.alerts.length > 1 && <span className="text-[#bbb]">외 {r.alerts.length - 1}건 {open ? "▲" : "▼"}</span>}
            </div>
          )}
        </td>
      </tr>
      {open && hasAlerts && (
        <tr className="bg-[#fbf6f6]">
          <td />
          <td colSpan={7} className="px-3 pb-3 pt-1">
            <div className="rounded border border-[#eadede] bg-white p-2">
              <div className="mb-1 text-[10px] font-semibold text-[#b02a37]">감사·실적 정정 및 관리종목 관련 공시 (DART)</div>
              <ul className="flex flex-col gap-0.5">
                {r.alerts.map((a) => (
                  <li key={a.rcept_no} className="flex items-center gap-2 text-[11px]">
                    <span className="w-14 shrink-0 tabular-nums text-[#999]">{fmtDate(a.date)}</span>
                    <span
                      className="w-16 shrink-0 rounded px-1 py-0.5 text-center text-[9px] font-semibold text-white"
                      style={{ background: KIND_COLOR[a.kind] ?? "#999" }}
                    >
                      {a.kind}
                    </span>
                    <a
                      href={dartUrl(a.rcept_no)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[#1971c2] hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {a.report_nm}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
