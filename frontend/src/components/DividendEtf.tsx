"use client";

import { useEffect, useMemo, useState } from "react";
import { api, DividendEtfBoard, EtfGroup, SpDca } from "@/lib/api";

const GREEN = "#217346";
const RED = "#c0392b";

function won(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v).toLocaleString("ko-KR")}원`;
}

const CAT_COLOR: Record<string, string> = {
  배당성장: "#217346", 고배당: "#c0392b", 커버드콜인컴: "#8a5cf6", "S&P500": "#1971c2",
};

function EtfGroupTable({ g }: { g: EtfGroup }) {
  return (
    <div className="rounded-md border border-[#e5e5e5]">
      <div className="flex items-center justify-between border-b border-[#eee] px-3 py-1.5" style={{ background: "#f7f7f7" }}>
        <span className="text-[12px] font-bold" style={{ color: CAT_COLOR[g.category] ?? "#333" }}>{g.category}</span>
        <span className="text-[10px] text-[#999]">{g.count}개 · 평균 배당 {g.avg_yield ?? "—"}%</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead className="text-left text-[10px] uppercase tracking-wide text-[#999]">
            <tr className="border-b border-[#eee]">
              <th className="px-3 py-1.5">ETF</th>
              <th className="px-2 py-1.5 text-right">배당률</th>
              <th className="px-2 py-1.5 text-right">배당성장(5y)</th>
              <th className="px-2 py-1.5 text-right">보수</th>
              <th className="px-2 py-1.5 text-right">지급</th>
              <th className="px-3 py-1.5">전략</th>
            </tr>
          </thead>
          <tbody>
            {g.rows.map((e) => (
              <tr key={e.ticker} className="border-t border-[#f2f2f2] align-top hover:bg-[#f9f9f7]">
                <td className="px-3 py-1.5 whitespace-nowrap"><span className="font-bold text-[#333]">{e.ticker}</span><span className="ml-1 text-[9px] text-[#aaa]">{e.inception}~</span></td>
                <td className="px-2 py-1.5 text-right font-bold tabular-nums" style={{ color: RED }}>{e.yield != null ? `${e.yield}%` : "—"}</td>
                <td className="px-2 py-1.5 text-right tabular-nums" style={{ color: e.div_cagr_5y != null ? GREEN : "#ccc" }}>{e.div_cagr_5y != null ? `+${e.div_cagr_5y}%` : "—"}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-[#666]">{e.expense != null ? `${e.expense}%` : "—"}</td>
                <td className="px-2 py-1.5 text-right text-[10px] text-[#888]">{e.freq === "monthly" ? "매월" : "분기"}</td>
                <td className="px-3 py-1.5 text-[11px] text-[#666]">{e.strategy}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function DividendEtf() {
  const [d, setD] = useState<DividendEtfBoard | null>(null);
  const [err, setErr] = useState("");
  // S&P 적립 계산기
  const [monthly, setMonthly] = useState("500000");
  const [years, setYears] = useState("20");
  const [ret, setRet] = useState("10");
  const [dca, setDca] = useState<SpDca | null>(null);

  useEffect(() => { api.dividendEtf().then(setD).catch((e) => setErr(e?.message ?? "불러오기 실패")); }, []);

  const num = (s: string) => Number(s.replace(/,/g, "")) || 0;
  useEffect(() => {
    const m = num(monthly), y = num(years), r = num(ret) / 100;
    if (m <= 0 || y <= 0) { setDca(null); return; }
    const t = setTimeout(() => { api.spDca(m, y, r).then(setDca).catch(() => {}); }, 250);
    return () => clearTimeout(t);
  }, [monthly, years, ret]);

  const groups = useMemo(() => d?.groups ?? [], [d]);

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">배당 ETF · S&P500 적립형 — VIG · SCHD · DGRO 등 상품 비교 + 적립 계산기</span>
        {d?.as_of && <span className="text-[10px] text-white/80">기준 {d.as_of}</span>}
      </div>
      {err ? (
        <div className="py-14 text-center text-sm text-rose-600">{err}</div>
      ) : !d ? (
        <div className="flex items-center gap-2 py-16 pl-4 text-sm text-[#888]"><span className="h-5 w-5 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" /> ETF 불러오는 중…</div>
      ) : (
        <div className="flex flex-col gap-4 p-4">
          {/* S&P 적립 계산기 */}
          <div className="rounded-md border border-[#cfe0d6] bg-[#f2f8f4] p-3">
            <div className="text-[13px] font-bold text-[#217346]">S&P500 적립형 계산기 — 매월 적립 시 미래가치</div>
            <div className="mt-2 flex flex-wrap items-end gap-3">
              <label className="text-[11px] text-[#555]">월 적립액(원)
                <input value={Number(num(monthly)).toLocaleString("ko-KR")} onChange={(e) => setMonthly(e.target.value)}
                  className="mt-0.5 block w-32 rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-[#217346]" />
              </label>
              <label className="text-[11px] text-[#555]">기간(년)
                <input value={years} onChange={(e) => setYears(e.target.value)}
                  className="mt-0.5 block w-20 rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-[#217346]" />
              </label>
              <label className="text-[11px] text-[#555]">연 기대수익률(%)
                <input value={ret} onChange={(e) => setRet(e.target.value)}
                  className="mt-0.5 block w-20 rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-[#217346]" />
              </label>
            </div>
            {dca && (
              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
                <div><div className="text-[10px] text-[#999]">원금 합계</div><div className="text-[15px] font-bold tabular-nums text-[#555]">{won(dca.principal)}</div></div>
                <div><div className="text-[10px] text-[#999]">예상 평가액</div><div className="text-[17px] font-extrabold tabular-nums" style={{ color: GREEN }}>{won(dca.future_value)}</div></div>
                <div><div className="text-[10px] text-[#999]">투자수익</div><div className="text-[15px] font-bold tabular-nums" style={{ color: RED }}>+{won(dca.gain)}</div></div>
                <div><div className="text-[10px] text-[#999]">예상 연 배당</div><div className="text-[15px] font-bold tabular-nums text-[#217346]">{won(dca.est_annual_dividend)}</div></div>
              </div>
            )}
            <div className="mt-1.5 text-[10px] text-[#9a9a9a]">{dca?.note}</div>
          </div>

          {/* ETF 그룹 비교 */}
          <div className="flex flex-col gap-3">
            {groups.map((g) => <EtfGroupTable key={g.category} g={g} />)}
          </div>
          <div className="text-[10px] leading-relaxed text-[#bbb]">{d.note}</div>
        </div>
      )}
    </div>
  );
}
