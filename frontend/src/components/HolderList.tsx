"use client";

import { useEffect, useState } from "react";
import { api, HoldersResponse } from "@/lib/api";
import type { PickedStock } from "./NewsPanel";

export function HolderList({ stock }: { stock: PickedStock | null }) {
  const [data, setData] = useState<HoldersResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!stock?.ticker) {
      setData(null);
      return;
    }
    let alive = true;
    setLoading(true);
    api
      .holders(stock.ticker)
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [stock?.ticker]);

  if (!stock) return null;

  return (
    <div className="shrink-0 border-b border-[#d0d0d0] bg-white">
      <div className="flex items-center justify-between border-b border-[#e6e6e6] bg-[#f0f4f0] px-3 py-1.5">
        <span className="text-xs font-bold text-[#244d1a]">대량보유 주주 (5%+ · DART)</span>
        {data && <span className="text-[10px] text-[#aaa]">{data.holders.length}곳</span>}
      </div>
      {loading && !data ? (
        <div className="py-3 text-center text-xs text-[#999]">공시 조회 중…</div>
      ) : !data?.available ? (
        <div className="px-3 py-3 text-xs text-[#bbb]">{data?.reason ?? "DART 키 미설정"}</div>
      ) : data.holders.length === 0 ? (
        <div className="px-3 py-3 text-xs text-[#bbb]">{data.reason ?? "5% 이상 보유 공시가 없습니다."}</div>
      ) : (
        <ul className="max-h-40 overflow-y-auto">
          {data.holders.map((h, i) => (
            <li key={`${h.name}-${i}`} className="flex items-center justify-between border-b border-[#f2f2f2] px-3 py-1.5 text-xs last:border-0">
              <span className="min-w-0 flex-1 truncate text-[#333]" title={h.name}>
                {h.name}
                {h.date && <span className="ml-1 text-[10px] text-[#bbb]">{h.date.slice(2)}</span>}
              </span>
              <span className="ml-2 shrink-0 font-semibold tabular-nums text-[#244d1a]">
                {h.ratio != null ? `${h.ratio}%` : "—"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
