"use client";

import { useEffect, useMemo, useState } from "react";
import { api, CrisisSurvivors as CS, SurvivorRow } from "@/lib/api";

const GREEN = "#217346";
const GOLD = "#b8860b";

// 정규화 지수 배열 → SVG 폴리라인 (로그 스케일로 장기 상승 가독성↑)
function Spark({ data, w = 240, h = 56 }: { data: { date: string; v: number }[]; w?: number; h?: number }) {
  if (data.length < 2) return null;
  const vals = data.map((d) => Math.log(Math.max(d.v, 1)));
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = max - min || 1;
  const pts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((Math.log(Math.max(d.v, 1)) - min) / span) * (h - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none" style={{ height: h }}>
      <polyline points={pts} fill="none" stroke={GREEN} strokeWidth={1.6} />
    </svg>
  );
}

function ddColor(dd: number | null): string {
  if (dd == null) return "#bbb";
  if (dd <= -45) return "#c5221f";
  if (dd <= -25) return "#b06000";
  return "#8a8a3a";
}

function Card({ r }: { r: SurvivorRow }) {
  return (
    <div className="rounded-md border border-[#e5e5e5] bg-white p-3">
      <div className="flex items-baseline justify-between">
        <div>
          <span className="text-[13px] font-bold text-[#333]">{r.name}</span>
          <span className="ml-1 text-[10px] text-[#aaa]">{r.ticker}</span>
        </div>
        <span className="text-[15px] font-extrabold tabular-nums" style={{ color: GREEN }}>{r.multiple != null ? `${r.multiple}x` : "—"}</span>
      </div>
      {r.tier_label && <div className="text-[10px] text-[#8a6d1a]">👑 {r.tier_label} {r.years}년</div>}
      <div className="mt-1"><Spark data={r.index} /></div>
      <div className="mt-1 flex justify-between text-[10px] text-[#999]">
        <span>{r.index[0]?.date}</span>
        <span>연 {r.cagr != null ? `${r.cagr}%` : "—"}</span>
        <span>{r.index[r.index.length - 1]?.date}</span>
      </div>
      {/* 위기별 낙폭 + 배당 */}
      <div className="mt-2 grid grid-cols-3 gap-1">
        {r.crises.map((c) => (
          <div key={c.key} className="rounded bg-[#faf9f4] px-1.5 py-1 text-center">
            <div className="text-[9px] text-[#999]">{c.label.replace(/^\d+\s?/, "")}</div>
            <div className="text-[12px] font-bold tabular-nums" style={{ color: ddColor(c.drawdown) }}>{c.drawdown != null ? `${c.drawdown}%` : "—"}</div>
            <div className="text-[9px] font-semibold text-[#137333]">배당 {c.dividend}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CrisisSurvivors() {
  const [d, setD] = useState<CS | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => { api.crisisSurvivors().then(setD).catch((e) => setErr(e?.message ?? "불러오기 실패")); }, []);

  const bench = d?.benchmark;
  const survivors = useMemo(() => d?.survivors ?? [], [d]);

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">위기를 이겨낸 우상향 배당주 — 2000·2008·2020을 겪고도 성장 + 배당 증액</span>
      </div>
      {err ? (
        <div className="py-14 text-center text-sm text-rose-600">{err}</div>
      ) : !d ? (
        <div className="flex items-center gap-2 py-16 pl-4 text-sm text-[#888]"><span className="h-5 w-5 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" /> 장기 주가 취합 중… (최초 1회 다소 소요)</div>
      ) : (
        <div className="p-4">
          {/* 벤치마크(S&P500) 요약 */}
          {bench && (
            <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-1 rounded-md border border-[#e5e5e5] bg-[#f8faf9] px-4 py-2 text-[12px]">
              <span className="font-bold text-[#333]">기준: S&P500 (SPY)</span>
              <span className="text-[#888]">{d.start.slice(0, 4)}년 이후 <b style={{ color: GREEN }}>{bench.multiple}x</b> (연 {bench.cagr}%)</span>
              <span className="text-[#aaa]">→ 아래 배당주들은 위기마다 급락했지만 매번 회복하며 우상향했고, 그동안 배당을 계속 늘렸습니다.</span>
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {survivors.map((r) => <Card key={r.ticker} r={r} />)}
          </div>
          <div className="mt-3 text-[10px] leading-relaxed text-[#bbb]">{d.note}</div>
        </div>
      )}
    </div>
  );
}
