"use client";

import { useEffect, useState } from "react";
import { api, StockScoreBoard } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";

function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}
function pctStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666" };
}
function scoreBar(v: number | null | undefined) {
  const s = v ?? 0;
  const color = s >= 80 ? "#2f9e44" : s >= 60 ? "#94c973" : s >= 40 ? "#d9c25a" : "#c98a8a";
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-12 overflow-hidden rounded-full bg-[#eee]">
        <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, s))}%`, background: color }} />
      </div>
      <span className="w-6 text-right tabular-nums text-[11px] text-[#555]">{v ?? "—"}</span>
    </div>
  );
}

export function StockScore() {
  const [d, setD] = useState<StockScoreBoard | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    api.stockScore().then((r) => alive && setD(r)).catch((e) => alive && setErr(e?.message ?? "불러오기 실패"));
    return () => { alive = false; };
  }, []);

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">투자 점수.xlsx</span>
        {d && <span className="text-xs text-white/80">가치45%·모멘텀35%·수급20% · {d.count}종목 평가</span>}
      </div>
      {err && !d ? (
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      ) : !d ? (
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
          전 종목 점수 계산 중…
        </div>
      ) : (
        <div className="max-h-[calc(100vh-190px)] overflow-auto">
          <table className="w-full text-[12px]">
            <thead className="sticky top-0 z-10 bg-[#f5f5f5] text-left text-[10px] uppercase tracking-wide text-[#999]">
              <tr className="border-b border-[#e5e5e5]">
                <th className="px-3 py-2 font-semibold">#</th>
                <th className="px-3 py-2 font-semibold">종목</th>
                <th className="px-3 py-2 text-right font-semibold">현재가</th>
                <th className="px-3 py-2 text-right font-semibold">1개월</th>
                <th className="px-3 py-2 text-right font-semibold">PER</th>
                <th className="px-3 py-2 text-right font-semibold">ROE</th>
                <th className="px-3 py-2 font-semibold">가치</th>
                <th className="px-3 py-2 font-semibold">모멘텀</th>
                <th className="px-3 py-2 font-semibold">수급</th>
                <th className="px-3 py-2 font-semibold">종합</th>
              </tr>
            </thead>
            <tbody>
              {d.rows.map((r, i) => (
                <tr key={r.ticker} className="border-t border-[#f2f2f2] hover:bg-[#f8faf8]">
                  <td className="px-3 py-1.5 text-[#aaa]">{i + 1}</td>
                  <td className="px-3 py-1.5">
                    <span className="font-semibold text-[#333]">{r.name ?? r.ticker}</span>
                    <span className="ml-1 text-[10px] text-[#aaa]">{r.ticker}{r.sector ? ` · ${r.sector}` : ""}</span>
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-[#333]">{r.close?.toLocaleString("ko-KR") ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums font-semibold" style={pctStyle(r.ret_1m)}>{pct(r.ret_1m)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-[#666]">{r.per ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-[#666]">{r.roe != null ? `${r.roe}%` : "—"}</td>
                  <td className="px-3 py-1.5">{scoreBar(r.value_score)}</td>
                  <td className="px-3 py-1.5">{scoreBar(r.momentum_score)}</td>
                  <td className="px-3 py-1.5">{scoreBar(r.flow_score)}</td>
                  <td className="px-3 py-1.5">
                    <span className="rounded bg-[#eef4f0] px-2 py-0.5 text-[12px] font-bold tabular-nums text-[#217346]">{r.total_score}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-3 py-2 text-[10px] text-[#bbb]">{d.note} · 생성 {d.generated_at}</div>
        </div>
      )}
    </div>
  );
}
