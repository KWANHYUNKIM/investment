"use client";

import { useEffect, useState } from "react";
import { api, InvestorRow } from "@/lib/api";
import { manShares, toneClass } from "@/lib/format";
import type { PickedStock } from "./NewsPanel";

export function InvestorFlow({ stock }: { stock: PickedStock | null }) {
  const [rows, setRows] = useState<InvestorRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!stock?.ticker) {
      setRows([]);
      return;
    }
    let alive = true;
    const load = async () => {
      setLoading(true);
      try {
        const r = await api.investors(stock.ticker);
        if (alive) setRows(r.rows);
      } catch {
        if (alive) setRows([]);
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 60000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [stock?.ticker]);

  if (!stock) return null;

  const latest = rows[0];

  return (
    <div className="shrink-0 border-b border-[#d0d0d0] bg-white">
      <div className="flex items-center justify-between border-b border-[#e6e6e6] bg-[#f0f4f0] px-3 py-1.5">
        <span className="text-xs font-bold text-[#244d1a]">투자자별 매매동향</span>
        {latest?.foreign_ratio != null && (
          <span className="text-[11px] text-[#666]">
            외국인보유 <b className="text-[#333]">{latest.foreign_ratio}%</b>
          </span>
        )}
      </div>

      {loading && rows.length === 0 ? (
        <div className="py-4 text-center text-xs text-[#999]">매매동향 불러오는 중…</div>
      ) : rows.length === 0 ? (
        <div className="py-4 text-center text-xs text-[#bbb]">매매동향 데이터가 없습니다.</div>
      ) : (
        <>
          {/* latest day net-buy summary */}
          <div className="grid grid-cols-3 gap-px bg-[#eee] p-px">
            <Box label="개인" v={latest.individual} />
            <Box label="외국인" v={latest.foreign} />
            <Box label="기관" v={latest.organ} />
          </div>
          <div className="px-3 pb-1 pt-1 text-[10px] text-[#999]">{latest.date} 순매수 (주) · 빨강 매수 / 파랑 매도</div>

          {/* cumulative net-buy over the fetched window */}
          {(() => {
            const cum = rows.reduce(
              (a, r) => ({
                individual: a.individual + (r.individual ?? 0),
                foreign: a.foreign + (r.foreign ?? 0),
                organ: a.organ + (r.organ ?? 0),
              }),
              { individual: 0, foreign: 0, organ: 0 },
            );
            return (
              <div className="flex items-center gap-2 border-y border-[#eee] bg-[#fafafa] px-3 py-1.5 text-[11px]">
                <span className="text-[#888]">최근 {rows.length}일 누적</span>
                <span className="ml-auto">개인 <b className={toneClass(cum.individual)}>{manShares(cum.individual)}</b></span>
                <span>외국인 <b className={toneClass(cum.foreign)}>{manShares(cum.foreign)}</b></span>
                <span>기관 <b className={toneClass(cum.organ)}>{manShares(cum.organ)}</b></span>
              </div>
            );
          })()}

          {/* recent days mini table */}
          <table className="w-full text-[11px] tabular-nums">
            <thead>
              <tr className="text-[#888]">
                <th className="px-2 py-1 text-left font-medium">날짜</th>
                <th className="px-2 py-1 text-right font-medium">개인</th>
                <th className="px-2 py-1 text-right font-medium">외국인</th>
                <th className="px-2 py-1 text-right font-medium">기관</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 7).map((r) => (
                <tr key={r.date} className="border-t border-[#f0f0f0]">
                  <td className="px-2 py-1 text-left text-[#777]">{r.date.slice(5)}</td>
                  <td className={`px-2 py-1 text-right ${toneClass(r.individual)}`}>{manShares(r.individual)}</td>
                  <td className={`px-2 py-1 text-right ${toneClass(r.foreign)}`}>{manShares(r.foreign)}</td>
                  <td className={`px-2 py-1 text-right ${toneClass(r.organ)}`}>{manShares(r.organ)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function Box({ label, v }: { label: string; v: number | null }) {
  const sells = v != null && v < 0;
  return (
    <div className="bg-white px-2 py-2 text-center">
      <div className="text-[10px] text-[#888]">{label}</div>
      <div className={`text-sm font-bold tabular-nums ${toneClass(v)}`}>{manShares(v)}</div>
      <div className="text-[9px] text-[#aaa]">{v == null ? "" : sells ? "순매도" : "순매수"}</div>
    </div>
  );
}
