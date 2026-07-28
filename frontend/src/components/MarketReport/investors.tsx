"use client";

import { InvestorDriver, InvestorDay } from "@/lib/api";
import { manShares } from "@/lib/format";
import { BLUE, Block, RED, Th, eok, flowStyle } from "./shared";

// 현재(최근 거래일) 한 주체의 매매현황 타일.
export function InvestorTile({ label, amt, qty }: { label: string; amt: number | null; qty: number | null }) {
  const buy = (amt ?? 0) > 0;
  const sell = (amt ?? 0) < 0;
  const color = buy ? RED : sell ? BLUE : "#888";
  const action = amt == null ? "데이터 없음" : buy ? "순매수" : sell ? "순매도" : "보합";
  return (
    <div className="flex flex-col items-center rounded border px-3 py-3" style={{ borderColor: `${color}33`, background: `${color}0d` }}>
      <div className="text-sm font-bold text-[#3d2c66]">{label}</div>
      <div className="mt-1 rounded-full px-2.5 py-0.5 text-xs font-bold text-white" style={{ background: color }}>{action}</div>
      <div className="mt-1.5 text-xl font-bold tabular-nums" style={{ color }}>{eok(amt)}</div>
      {qty != null && <div className="text-[11px] tabular-nums text-[#999]">{manShares(qty)}주</div>}
    </div>
  );
}

export function InvestorTrendBlock({ trend, reportDate }: { trend: InvestorDay[]; reportDate?: string | null }) {
  if (!trend || trend.length === 0) return null;
  // 가장 최근 확정 거래일 = 현재 매매현황(수급은 마감 후 집계라 보통 1일 지연).
  const top = trend[0];
  const lag = reportDate && top.date !== reportDate;
  const led = (["foreign", "individual", "organ"] as const)
    .map((k) => ({ k, v: top[k] ?? 0, label: k === "foreign" ? "외국인" : k === "individual" ? "개인" : "기관" }))
    .filter((x) => x.v > 0)
    .sort((a, b) => b.v - a.v)[0];
  return (
    <Block label="투자자별 매매현황 (현재 · 일단위)" color="#b4a7d6" fg="#3d2c66">
      {/* 현재(최근 거래일) 매매현황 — 누가 매입/매도했나, 크게 */}
      <div className="border-b border-[#eee] bg-[#f6f3fb] px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-[13px] text-[#3d2c66]">
          <span className="rounded bg-[#3d2c66] px-2 py-0.5 text-xs font-bold text-white">현재 매매현황</span>
          <b>{top.date}</b> 기준 (집계 {top.stocks.toLocaleString("ko-KR")}종목)
          {led && <span>· <b>{led.label}</b> 순매수 주도</span>}
          {lag && <span className="text-[11px] text-[#999]">· 수급은 장 마감 후 집계 → 가장 최근 확정 거래일 기준 ({reportDate} 당일분은 마감 후 반영)</span>}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <InvestorTile label="외국인" amt={top.foreign} qty={top.foreign_qty} />
          <InvestorTile label="개인" amt={top.individual} qty={top.individual_qty} />
          <InvestorTile label="기관" amt={top.organ} qty={top.organ_qty} />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-[#ece7f6] text-[11px] text-[#3d2c66]">
              <th colSpan={5} className="border border-[#d0d0d0] px-2 py-1 text-left font-bold"> 일별 추이 (순매수 금액, 억원)</th>
            </tr>
            <tr className="bg-[#ece7f6] text-xs text-[#3d2c66]">
              <Th w="22%">일자</Th>
              <Th w="22%" right>외국인</Th>
              <Th w="22%" right>개인</Th>
              <Th w="22%" right>기관</Th>
              <Th w="12%" center>집계종목</Th>
            </tr>
          </thead>
          <tbody>
            {trend.map((d) => (
              <tr key={d.date} className="hover:bg-[#faf8ff]">
                <td className="border border-[#eee] px-2 py-1.5 font-medium text-[#1f1f1f]">{d.date}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums" style={flowStyle(d.foreign)}>{eok(d.foreign)}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums" style={flowStyle(d.individual)}>{eok(d.individual)}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums" style={flowStyle(d.organ)}>{eok(d.organ)}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-center tabular-nums text-[#888]">{d.stocks.toLocaleString("ko-KR")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-3 py-1.5 text-[11px] leading-relaxed text-[#999]">
        종목별 누적 수급(네이버)을 그날 종가와 곱해 시장 전체 <b>순매수 금액</b>으로 집계(개인/외국인/기관). 빨강=순매수(매입) · 파랑=순매도. <b>투자자별 매매(매수·매도)는 장 마감 후 집계되어 보통 1거래일 지연</b>되므로, 당일 가격은 있어도 그날 수급은 다음 날 확정됩니다 — 위 "현재 매매현황"은 가장 최근 확정 거래일 기준입니다. (KRX 기관 세부주체는 비공개 구간)
      </p>
    </Block>
  );
}

export function InvestorCells({ iv }: { iv?: InvestorDriver }) {
  const buy = iv?.action === "순매수";
  const sell = iv?.action === "순매도";
  const color = buy ? RED : sell ? BLUE : "#888";
  return (
    <>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center align-top">
        {iv && iv.action !== "데이터 없음" ? (
          <div className="leading-tight">
            <div className="font-bold" style={{ color }}>
              {iv.action}
            </div>
            {iv.qty != null && iv.qty !== 0 && (
              <div className="tabular-nums text-xs" style={{ color }}>
                {manShares(iv.qty)}주
              </div>
            )}
          </div>
        ) : (
          <span className="text-xs text-[#bbb]">—</span>
        )}
      </td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 align-top text-xs leading-relaxed text-[#444]">
        {iv && iv.reasons.length > 0 ? iv.reasons.join(" · ") : <span className="text-[#bbb]">—</span>}
      </td>
    </>
  );
}
