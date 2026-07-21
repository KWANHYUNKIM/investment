"use client";

import { useEffect, useMemo, useState } from "react";
import { api, EqBoard, EqRow } from "@/lib/api";

const KIND_COLOR: Record<string, string> = {
  "밑지고팜": "#e03131",
  "자본잠식": "#862e2e",
  "매출채권": "#d9480f",
  "상품매출": "#5c940d",
  "비지배지분": "#7048a8",
  "연결범위": "#1864ab",
  "일회성이익": "#c05621",
  "흑자전환": "#2b8a3e",
  "이전가격": "#0b7285",
  "처분이익": "#a61e4d",
};
const KIND_DESC: Record<string, string> = {
  "밑지고팜": "매출총이익률<0 — 매출원가가 매출액보다 큼(원가 이하 판매)",
  "자본잠식": "자본총계<자본금 — 원금(액면)을 까먹는 중(부분/완전 자본잠식)",
  "매출채권": "매출채권이 매출보다 빠르게 급증(밀어내기·가공매출·회수지연)",
  "상품매출": "제조사인데 상품매출 급증(통행/밀어내기 매출 의심)",
  "비지배지분": "연결 외형·자본은 크나 지배주주 실질 몫이 작음",
  "연결범위": "종속회사 편입으로 매출이 늘어 보임(유기적 성장 아님)",
  "일회성이익": "영업손실인데 순이익 흑자 등 영업외이익 의존",
  "흑자전환": "3년 연속 영업손실 후 흑자 전환(관리종목 회피·영업이익 조정 의심)",
  "이전가격": "연결은 손실인데 별도는 흑자(내부거래 이전가격 착시)",
  "처분이익": "자산 처분이익이 이익의 큰 부분(특수관계자 거래 점검)",
};

function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const e = v / 1e8;
  const s = e < 0 ? "-" : "";
  const a = Math.abs(e);
  return `${s}${a >= 10000 ? (a / 10000).toFixed(2) + "조" : a >= 1000 ? a.toLocaleString("ko-KR", { maximumFractionDigits: 0 }) + "억" : a.toFixed(0) + "억"}`;
}
function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;
}

export function EarningsQuality() {
  const [d, setD] = useState<EqBoard | null>(null);
  const [err, setErr] = useState("");
  const [kind, setKind] = useState<string>("");
  const [q, setQ] = useState("");

  useEffect(() => {
    let alive = true;
    api.earningsQuality().then((r) => alive && setD(r)).catch((e) => alive && setErr(e?.message ?? "불러오기 실패"));
    return () => { alive = false; };
  }, []);

  const rows = useMemo(() => {
    if (!d) return [];
    const kw = q.trim();
    return d.rows.filter((r) => {
      if (kind && !r.flags.some((f) => f.kind === kind)) return false;
      if (kw && !`${r.name}${r.ticker}`.includes(kw)) return false;
      return true;
    });
  }, [d, kind, q]);

  const s = d?.summary ?? {};

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#5f3dc4] px-4 py-2 text-white">
        <span className="text-sm font-semibold">회계 착시 탐지.xlsx</span>
        {d && <span className="text-xs text-white/85">{d.count}종목 · 연결범위·비지배지분·일회성이익·처분이익</span>}
      </div>

      {err && !d ? (
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      ) : !d ? (
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d6c9f0] border-t-[#5f3dc4]" />
          연결 재무제표·손익 분석 중…
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 border-b border-[#eee] bg-[#f8f6fd] px-3 py-2">
            {(["", "밑지고팜", "자본잠식", "매출채권", "상품매출", "비지배지분", "연결범위", "일회성이익", "흑자전환", "이전가격", "처분이익"] as const).map((k) => {
              const active = kind === k;
              const c = k ? KIND_COLOR[k] : "#555";
              const cnt = k ? (s[k] ?? 0) : d.count;
              return (
                <button
                  key={k || "all"}
                  onClick={() => setKind(k)}
                  title={k ? KIND_DESC[k] : "전체"}
                  className="rounded-full px-3 py-1 text-[11px] font-semibold transition"
                  style={{ background: active ? c : "#efeaf7", color: active ? "#fff" : c }}
                >
                  {k || "전체"} {cnt}
                </button>
              );
            })}
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="종목명·코드 검색"
              className="ml-auto w-40 rounded border border-[#ddd] px-2 py-1 text-[12px] outline-none focus:border-[#5f3dc4]"
            />
          </div>

          <div className="max-h-[calc(100vh-240px)] overflow-auto">
            <table className="w-full text-[12px]">
              <thead className="sticky top-0 z-10 bg-[#f5f5f5] text-left text-[10px] uppercase tracking-wide text-[#999]">
                <tr className="border-b border-[#e5e5e5]">
                  <th className="px-3 py-2 font-semibold">#</th>
                  <th className="px-3 py-2 font-semibold">종목</th>
                  <th className="px-3 py-2 text-right font-semibold">매출(전년比)</th>
                  <th className="px-3 py-2 text-right font-semibold">영업이익</th>
                  <th className="px-3 py-2 text-right font-semibold">순이익</th>
                  <th className="px-3 py-2 text-right font-semibold">매출총이익률</th>
                  <th className="px-3 py-2 text-right font-semibold">자본잠식률</th>
                  <th className="px-3 py-2 text-right font-semibold">비지배지분</th>
                  <th className="px-3 py-2 font-semibold">착시 신호</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => <RowView key={r.ticker} r={r} i={i} />)}
                {rows.length === 0 && (
                  <tr><td colSpan={9} className="py-16 text-center text-[#bbb]">해당 조건의 종목이 없습니다.</td></tr>
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

function RowView({ r, i }: { r: EqRow; i: number }) {
  return (
    <tr className="border-t border-[#f2f2f2] align-top hover:bg-[#faf8fe]">
      <td className="px-3 py-2 text-[#bbb]">{i + 1}</td>
      <td className="px-3 py-2">
        <div className="font-semibold text-[#333]">{r.name}</div>
        <div className="text-[10px] text-[#aaa]">{r.ticker}{r.latest_year ? ` · ${r.latest_year}` : ""}</div>
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-[#555]">
        {eok(r.rev)}
        {r.rev_yoy != null && (
          <span className="ml-1 text-[10px]" style={{ color: r.rev_yoy >= 40 ? "#c05621" : "#999" }}>{pct(r.rev_yoy)}</span>
        )}
      </td>
      <td className="px-3 py-2 text-right tabular-nums" style={{ color: (r.op ?? 0) < 0 ? "#1971c2" : "#333" }}>{eok(r.op)}</td>
      <td className="px-3 py-2 text-right tabular-nums" style={{ color: (r.ni ?? 0) < 0 ? "#1971c2" : "#333" }}>{eok(r.ni)}</td>
      <td className="px-3 py-2 text-right tabular-nums font-semibold" style={{ color: r.gross_margin == null ? "#ccc" : r.gross_margin < 0 ? "#e03131" : r.gross_margin < 5 ? "#d9480f" : "#777" }}>
        {r.gross_margin != null ? `${r.gross_margin}%` : "—"}
      </td>
      <td className="px-3 py-2 text-right tabular-nums font-semibold" style={{ color: r.cap_impair_rate == null || r.cap_impair_rate <= 0 ? "#ccc" : r.cap_impair_rate >= 50 ? "#862e2e" : "#c05621" }}>
        {r.cap_impair_rate != null && r.cap_impair_rate > 0 ? `${r.cap_impair_rate}%` : "—"}
      </td>
      <td className="px-3 py-2 text-right tabular-nums" style={{ color: (r.minor_eq_ratio ?? 0) >= 50 ? "#7048a8" : "#777" }}>
        {r.minor_eq_ratio != null ? `${r.minor_eq_ratio}%` : "—"}
      </td>
      <td className="px-3 py-2">
        <div className="flex flex-col gap-1">
          {r.flags.map((f, k) => (
            <div key={k} className="flex items-start gap-1.5">
              <span
                className="mt-[1px] shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold text-white"
                style={{ background: KIND_COLOR[f.kind] ?? "#999" }}
              >
                {f.kind}
              </span>
              <span className="text-[11px] leading-snug text-[#555]">{f.text}</span>
            </div>
          ))}
        </div>
      </td>
    </tr>
  );
}
