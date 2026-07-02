"use client";

import { useEffect, useState } from "react";
import { api, DividendsBoard as DB } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";

function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return `${(v / 1e12).toFixed(1)}조`;
  if (a >= 1e8) return `${Math.round(v / 1e8).toLocaleString("ko-KR")}억`;
  return Math.round(v).toLocaleString("ko-KR");
}

export function DividendsBoard() {
  const [d, setD] = useState<DB | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    api.dividends().then((r) => alive && setD(r)).catch((e) => alive && setErr(e?.message ?? "불러오기 실패"));
    return () => { alive = false; };
  }, []);

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">배당·실적.xlsx</span>
      </div>
      {err && !d ? (
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      ) : !d ? (
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
          배당·실적 취합 중…
        </div>
      ) : (
        <div className="max-h-[calc(100vh-190px)] overflow-auto p-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* 고배당 */}
            <div className="rounded-md border border-[#e5e5e5]">
              <div className="border-b border-[#e5e5e5] bg-[#f5f5f5] px-3 py-2 text-xs font-semibold text-[#555]">
                고배당 종목 (배당수익률 상위)
              </div>
              <table className="w-full text-[12px]">
                <thead className="text-left text-[10px] uppercase tracking-wide text-[#999]">
                  <tr className="border-b border-[#eee]">
                    <th className="px-3 py-1.5">종목</th>
                    <th className="px-3 py-1.5 text-right">배당수익률</th>
                    <th className="px-3 py-1.5 text-right">PER</th>
                    <th className="px-3 py-1.5 text-right">ROE</th>
                  </tr>
                </thead>
                <tbody>
                  {d.dividends.map((r) => (
                    <tr key={r.ticker} className="border-t border-[#f2f2f2]">
                      <td className="px-3 py-1.5">
                        <span className="font-semibold text-[#333]">{r.name ?? r.ticker}</span>
                        <span className="ml-1 text-[10px] text-[#aaa]">{r.sector ?? ""}</span>
                      </td>
                      <td className="px-3 py-1.5 text-right font-bold tabular-nums" style={{ color: RED }}>{r.div_yield}%</td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-[#666]">{r.per ?? "—"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-[#666]">{r.roe != null ? `${r.roe}%` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 실적 개선 */}
            <div className="rounded-md border border-[#e5e5e5]">
              <div className="border-b border-[#e5e5e5] bg-[#f5f5f5] px-3 py-2 text-xs font-semibold text-[#555]">
                실적 개선 종목 (영업이익 전년比 증가율)
              </div>
              <table className="w-full text-[12px]">
                <thead className="text-left text-[10px] uppercase tracking-wide text-[#999]">
                  <tr className="border-b border-[#eee]">
                    <th className="px-3 py-1.5">종목</th>
                    <th className="px-3 py-1.5 text-right">영업이익 YoY</th>
                    <th className="px-3 py-1.5 text-right">영업이익률</th>
                    <th className="px-3 py-1.5 text-right">기준</th>
                  </tr>
                </thead>
                <tbody>
                  {d.earnings.map((r) => (
                    <tr key={r.ticker} className="border-t border-[#f2f2f2]">
                      <td className="px-3 py-1.5">
                        <span className="font-semibold text-[#333]">{r.name ?? r.ticker}</span>
                        <span className="ml-1 text-[10px] text-[#aaa]">{r.sector ?? ""}</span>
                      </td>
                      <td className="px-3 py-1.5 text-right font-bold tabular-nums" style={{ color: r.op_yoy >= 0 ? RED : BLUE }}>
                        {r.op_yoy > 0 ? "+" : ""}{r.op_yoy}%
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-[#666]">{r.op_margin != null ? `${r.op_margin}%` : "—"}</td>
                      <td className="px-3 py-1.5 text-right text-[10px] text-[#aaa]">{r.period?.slice(0, 7)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="mt-3 text-[10px] leading-relaxed text-[#bbb]">{d.note}</div>
        </div>
      )}
    </div>
  );
}
