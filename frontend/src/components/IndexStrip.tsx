"use client";

import { useEffect, useState } from "react";
import { api, CrossAssetLayer } from "@/lib/api";

// KR convention: red = up, blue = down (값 방향만 색, 나머지는 회색/초록 — 엑셀 톤).
const UP = "#c92a2a";
const DOWN = "#1971c2";

// 표시할 지수 (실시간 가능한 것). cross-asset에서 끌어온다.
const KEYS = ["kospi", "kosdaq", "nasdaq", "sp500", "dow", "nikkei", "shanghai", "hangseng", "dax", "ftse", "usdkrw"];
const LABEL: Record<string, string> = {
  kospi: "KOSPI", kosdaq: "KOSDAQ", nasdaq: "나스닥", sp500: "S&P500", dow: "다우",
  nikkei: "니케이", shanghai: "상하이", hangseng: "항셍", dax: "DAX", ftse: "FTSE", usdkrw: "원/달러",
};

function fmtVal(v: number | null, key: string): string {
  if (v == null) return "—";
  if (key === "usdkrw") return v.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function IndexStrip() {
  const [ca, setCa] = useState<CrossAssetLayer | null>(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => api.crossAsset().then((d) => { if (alive) { setCa(d); setLive(true); } }).catch(() => {});
    load();
    const id = setInterval(load, 30000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const byKey: Record<string, { value: number | null; change_pct: number | null }> = {};
  for (const g of ca?.groups ?? []) for (const a of g.assets) byKey[a.key] = { value: a.value, change_pct: a.change_pct };

  return (
    <div className="flex items-stretch gap-0 overflow-x-auto border-b border-[#d0d0d0] bg-[#f3f2f1] text-xs">
      <div className="flex shrink-0 items-center gap-1 border-r border-[#d0d0d0] bg-[#e8efe8] px-3 font-semibold text-[#217346]">
        <span className={`inline-block h-1.5 w-1.5 rounded-full ${live ? "animate-pulse bg-[#2f9e44]" : "bg-[#bbb]"}`} />
        실시간 지수
      </div>
      {KEYS.map((k) => {
        const a = byKey[k];
        const chg = a?.change_pct ?? null;
        const col = chg == null ? "#999" : chg > 0 ? UP : chg < 0 ? DOWN : "#666";
        return (
          <div key={k} className="flex shrink-0 items-baseline gap-1.5 border-r border-[#e2e2e2] px-3 py-1.5">
            <span className="text-[#666]">{LABEL[k] ?? k}</span>
            <span className="font-semibold tabular-nums text-[#333]">{fmtVal(a?.value ?? null, k)}</span>
            <span className="tabular-nums font-bold" style={{ color: col }}>
              {chg == null ? "" : `${chg > 0 ? "▲" : chg < 0 ? "▼" : ""}${Math.abs(chg)}%`}
            </span>
          </div>
        );
      })}
    </div>
  );
}
