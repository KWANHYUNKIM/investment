"use client";

import { useEffect, useState } from "react";
import { api, FundamentalsResponse } from "@/lib/api";
import type { PickedStock } from "./NewsPanel";

const ROWS: { key: string; label: string; suffix?: string }[] = [
  { key: "per", label: "PER", suffix: "배" },
  { key: "pbr", label: "PBR", suffix: "배" },
  { key: "roe", label: "ROE", suffix: "%" },
  { key: "div_yield", label: "배당", suffix: "%" },
  { key: "foreign_ratio", label: "외인소진율", suffix: "%" },
];

export function FundamentalsPanel({ stock }: { stock: PickedStock | null }) {
  const [data, setData] = useState<FundamentalsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!stock?.ticker) {
      setData(null);
      return;
    }
    let alive = true;
    setLoading(true);
    const load = () =>
      api
        .fundamentals(stock.ticker)
        .then((d) => alive && setData(d))
        .catch(() => alive && setData(null))
        .finally(() => alive && setLoading(false));
    load();
    const id = setInterval(load, 60000); // 변화 누적 반영
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [stock?.ticker]);

  if (!stock) return null;
  const lt = data?.latest;
  const ch = data?.change;

  return (
    <div className="shrink-0 border-b border-[#d0d0d0] bg-white">
      <div className="flex items-center justify-between border-b border-[#e6e6e6] bg-[#f0f4f0] px-3 py-1.5">
        <span className="text-xs font-bold text-[#244d1a]">펀더멘털 {ch ? "· 변화(Δ)" : ""}</span>
        {lt?.date && <span className="text-[10px] text-[#aaa]">{lt.date}</span>}
      </div>
      {loading && !data ? (
        <div className="py-3 text-center text-xs text-[#999]">불러오는 중…</div>
      ) : !lt ? (
        <div className="px-3 py-3 text-xs text-[#bbb]">펀더멘털 데이터가 아직 없습니다(크롤링 대기).</div>
      ) : (
        <div className="grid grid-cols-5 gap-px bg-[#eee] p-px text-center">
          {ROWS.map((r) => {
            const v = lt[r.key as keyof typeof lt] as number | null;
            const d = ch?.[r.key] ?? null;
            return (
              <div key={r.key} className="bg-white px-1 py-2">
                <div className="text-[10px] text-[#888]">{r.label}</div>
                <div className="text-xs font-bold tabular-nums text-[#333]">
                  {v == null ? "—" : `${v}${r.suffix ?? ""}`}
                </div>
                {d != null && d !== 0 && (
                  <div className={`text-[9px] tabular-nums ${d > 0 ? "text-[#c92a2a]" : "text-[#1971c2]"}`}>
                    {d > 0 ? "▲" : "▼"}{Math.abs(d)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
