"use client";

import { useEffect, useState } from "react";
import { api, RealEstateRent } from "@/lib/api";
import { retStyle } from "./shared";

export function RentSection() {
  const [d, setD] = useState<RealEstateRent | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .realestateRent()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const maxCnt = d?.available ? Math.max(...d.monthly.map((m) => m.count || 0), 1) : 1;

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#217346] px-3 py-1.5">
        <span className="text-sm font-bold text-white">부동산 전월세 실거래 — 전국 아파트</span>
        {d?.source && <span className="text-[11px] text-white/70">{d.source}</span>}
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">전월세 실거래 집계 중…</div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "전월세 실거래 데이터를 불러오지 못했습니다."}</div>
      ) : (
        <div className="p-3">
          {/* 헤드라인 */}
          <div className="mb-3 flex flex-wrap items-end gap-x-6 gap-y-1">
            <div>
              <div className="text-[11px] text-[#888]">최신 완성월 ({d.latest_label}) 전월세 거래</div>
              <div className="text-lg font-bold tabular-nums text-[#1f1f1f]">{d.latest_count?.toLocaleString("ko-KR")}건</div>
            </div>
            <div>
              <div className="text-[11px] text-[#888]">월세 비중</div>
              <div className="text-base font-bold tabular-nums text-[#b8860b]">{d.latest_wolse_ratio ?? "—"}%</div>
            </div>
            <div>
              <div className="text-[11px] text-[#888]">평균 전세보증금</div>
              <div className="text-base font-bold tabular-nums text-[#217346]">{d.latest_avg_jeonse_eok != null ? `${d.latest_avg_jeonse_eok}억` : "—"}</div>
            </div>
            {d.mom_count_pct != null && (
              <div>
                <div className="text-[11px] text-[#888]">전월 대비 거래량</div>
                <div className="text-base font-bold tabular-nums" style={retStyle(d.mom_count_pct)}>{d.mom_count_pct > 0 ? "+" : ""}{d.mom_count_pct}%</div>
              </div>
            )}
            <span className="ml-auto text-[11px] text-[#aaa]">전세=초록 · 월세=주황 · 당월(잠정) 미완성</span>
          </div>

          {/* 월별 전세/월세 적층 막대 */}
          <div className="mb-4 space-y-1">
            {d.monthly.map((m) => {
              const tot = m.count || 1;
              const jw = ((m.jeonse || 0) / tot) * 100;
              const ww = ((m.wolse || 0) / tot) * 100;
              const scale = ((m.count || 0) / maxCnt) * 100;
              return (
                <div key={m.ym} className="flex items-center gap-2 text-xs">
                  <span className="w-16 shrink-0 tabular-nums text-[#666]">{m.label}{m.provisional ? "*" : ""}</span>
                  <div className="relative h-4 flex-1 rounded bg-[#f3f3f3]">
                    <div className="absolute left-0 top-0 flex h-4 overflow-hidden rounded" style={{ width: `${scale}%` }}>
                      <div className="h-4 bg-[#3a9d5d]" style={{ width: `${jw}%` }} />
                      <div className="h-4 bg-[#e0a93b]" style={{ width: `${ww}%` }} />
                    </div>
                  </div>
                  <span className="w-40 shrink-0 text-right tabular-nums text-[#333]">
                    {m.count.toLocaleString("ko-KR")}건 <span className="text-[#aaa]">월세{m.wolse_ratio ?? "—"}%·전세{m.avg_jeonse_eok ?? "—"}억</span>
                  </span>
                </div>
              );
            })}
            <p className="pt-0.5 text-[10px] text-[#aaa]">* 잠정(신고 진행중) · 월세 비중↑ = 전세의 월세화</p>
          </div>

          {/* 시도별 — 완성 최신월 */}
          <div>
            <div className="mb-1 text-xs font-bold text-[#244d1a]">시도별 전월세 (기준 {d.region_ym?.slice(0, 4)}.{d.region_ym?.slice(4)})</div>
            <div className="grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-2">
              {d.by_sido.slice(0, 12).map((s) => (
                <div key={s.sido} className="flex items-center justify-between border-b border-[#f0f0f0] py-0.5 text-xs">
                  <span className="text-[#444]">{s.sido}</span>
                  <span className="tabular-nums text-[#333]">{s.count.toLocaleString("ko-KR")}건 <span className="text-[#b8860b]">월세{s.wolse_ratio ?? "—"}%</span> <span className="text-[#217346]">전세{s.avg_jeonse_eok ?? "—"}억</span></span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
