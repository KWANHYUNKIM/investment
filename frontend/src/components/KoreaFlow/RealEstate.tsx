"use client";

import { useEffect, useState } from "react";
import { api, RealEstateTrades } from "@/lib/api";
import { retStyle } from "./shared";

export function RealEstateSection() {
  const [d, setD] = useState<RealEstateTrades | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .realestateTrades()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const maxAmt = d?.available ? Math.max(...d.monthly.map((m) => m.amount_eok || 0), 1) : 1;

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#217346] px-3 py-1.5">
        <span className="text-sm font-bold text-white">부동산 실거래 거래액·거래량 — 전국 아파트 매매</span>
        {d?.source && <span className="text-[11px] text-white/70">{d.source}</span>}
      </div>

      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">실거래 집계 중… <span className="text-[#bbb]">(최초 수십 초)</span></div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">
          {d?.reason ?? "부동산 실거래 데이터를 불러오지 못했습니다."}
        </div>
      ) : (
        <div className="p-3">
          {/* 헤드라인 */}
          <div className="mb-3 flex flex-wrap items-end gap-x-6 gap-y-1">
            <div>
              <div className="text-[11px] text-[#888]">최신 완성월 ({d.latest_label})</div>
              <div className="text-lg font-bold text-[#1f1f1f]">
                {d.latest_count?.toLocaleString("ko-KR")}건 <span className="text-[#217346]">· {eok(d.latest_amount_eok)}</span>
              </div>
            </div>
            {d.mom_count_pct != null && (
              <div>
                <div className="text-[11px] text-[#888]">전월 대비 거래량</div>
                <div className="text-base font-bold tabular-nums" style={retStyle(d.mom_count_pct)}>
                  {d.mom_count_pct > 0 ? "+" : ""}{d.mom_count_pct}%
                </div>
              </div>
            )}
            <span className="ml-auto text-[11px] text-[#aaa]">{d.scope} · 당월(잠정)은 신고기한 30일 탓에 미완성</span>
          </div>

          {/* 월별 거래대금 막대 */}
          <div className="mb-4 space-y-1">
            {d.monthly.map((m) => (
              <div key={m.ym} className="flex items-center gap-2 text-xs">
                <span className="w-16 shrink-0 tabular-nums text-[#666]">{m.label}{m.provisional ? "*" : ""}</span>
                <div className="relative h-4 flex-1 rounded bg-[#f0f0f0]">
                  <div
                    className="absolute left-0 top-0 h-4 rounded"
                    style={{ width: `${((m.amount_eok || 0) / maxAmt) * 100}%`, background: m.provisional ? "#bcd6c2" : "#3a9d5d" }}
                  />
                </div>
                <span className="w-28 shrink-0 text-right tabular-nums text-[#333]">{eok(m.amount_eok)} · {m.count.toLocaleString("ko-KR")}건</span>
              </div>
            ))}
            <p className="pt-0.5 text-[10px] text-[#aaa]">* 잠정(신고 진행중)</p>
          </div>

          {/* 시도별 거래대금 막대 — 완성 최신월 */}
          {(() => {
            const maxSido = Math.max(...d.by_sido.map((s) => s.amount_eok || 0), 1);
            return (
              <div className="mb-4">
                <div className="mb-1.5 text-xs font-bold text-[#244d1a]">
                  시도별 거래대금 (기준 {d.region_ym?.slice(0, 4)}.{d.region_ym?.slice(4)})
                </div>
                <div className="grid gap-x-6 gap-y-1 md:grid-cols-2">
                  {d.by_sido.map((s) => (
                    <div key={s.sido} className="flex items-center gap-2 text-xs">
                      <span className="w-24 shrink-0 truncate text-[#444]">{s.sido}</span>
                      <div className="relative h-3.5 flex-1 rounded bg-[#f0f0f0]">
                        <div className="absolute left-0 top-0 h-3.5 rounded bg-[#3a9d5d]" style={{ width: `${((s.amount_eok || 0) / maxSido) * 100}%` }} />
                      </div>
                      <span className="w-24 shrink-0 text-right tabular-nums text-[#333]">{eok(s.amount_eok)} <span className="text-[#aaa]">{s.count.toLocaleString("ko-KR")}건</span></span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* 상위 시군구 — 완성 최신월 */}
          <div>
            <div className="mb-1 text-xs font-bold text-[#244d1a]">거래대금 상위 시군구</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 sm:grid-cols-3">
              {d.top_sigungu.map((r) => (
                <div key={`${r.sido}-${r.region}`} className="flex items-center justify-between border-b border-[#f0f0f0] py-0.5 text-xs">
                  <span className="truncate text-[#444]" title={`${r.sido} ${r.region}`}>{r.region}</span>
                  <span className="shrink-0 tabular-nums text-[#333]">{eok(r.amount_eok)} <span className="text-[#aaa]">{r.count}건</span></span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

// 억 → 보기 좋은 단위 (1조=10,000억)
export function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 10000) return `${(v / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}조`;
  return `${Math.round(v).toLocaleString("ko-KR")}억`;
}
