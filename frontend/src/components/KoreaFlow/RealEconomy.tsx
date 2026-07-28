"use client";

import { useEffect, useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Legend } from "recharts";
import { api, EcosIndicator, RealEconomy, WorldIndicator } from "@/lib/api";
import { EcosCard, EcosChartModal } from "./EcosMacro";
import { Modal, Stat } from "./shared";

export function RealEconomySection() {
  const [d, setD] = useState<RealEconomy | null>(null);
  const [loading, setLoading] = useState(true);
  const [selK, setSelK] = useState<EcosIndicator | null>(null);
  const [selW, setSelW] = useState<WorldIndicator | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .realEconomy()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      {selK && <EcosChartModal ind={selK} onClose={() => setSelK(null)} />}
      {selW && <WorldIndicatorModal ind={selW} onClose={() => setSelW(null)} />}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#0f3d2e] px-3 py-1.5">
        <span className="text-sm font-bold text-white">실물경제 — 한국 & 세계</span>
        <span className="text-[11px] text-white/70">소비·투자·수출·고용·물가 (돈이 실제로 만들어내는 것)</span>
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">실물경제 지표 집계 중… <span className="text-[#bbb]">(World Bank·ECOS 취합)</span></div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "실물경제 데이터를 불러오지 못했습니다."}</div>
      ) : (
        <div className="space-y-4 p-3">
          {/* 한국 — ECOS 국민계정·고용 (EcosCard 재사용) */}
          {d.korea.length > 0 && (
            <div>
              <div className="mb-1.5 text-xs font-bold text-[#244d1a]">한국 — 국민계정·고용 (한국은행 ECOS, 실질·계절조정·분기) <span className="font-normal text-[#999]">· 카드 클릭하면 크게</span></div>
              <div className="grid gap-px bg-[#eee] md:grid-cols-2 xl:grid-cols-3">
                {d.korea.map((i) => (
                  <EcosCard key={i.key} ind={i} onOpen={() => setSelK(i)} />
                ))}
              </div>
            </div>
          )}

          {/* 세계 — World Bank 다국 비교 */}
          {d.world.length > 0 && (
            <div>
              <div className="mb-1.5 text-xs font-bold text-[#244d1a]">세계 비교 — 한·미·중·일·독·인도 + 세계집계 (World Bank, 연) <span className="font-normal text-[#999]">· 카드 클릭하면 크게</span></div>
              <div className="grid gap-3 md:grid-cols-2">
                {d.world.map((w) => (
                  <WorldIndicatorCard key={w.key} ind={w} onOpen={() => setSelW(w)} />
                ))}
              </div>
            </div>
          )}

          <p className="text-[10px] leading-tight text-[#aaa]">{d.note}</p>
          <p className="text-[10px] text-[#bbb]">출처: {d.source}</p>
        </div>
      )}
    </section>
  );
}

// 실물경제 — 국가별 색 (세계=검정, 한국=빨강 강조)
export const ENT_COLOR: Record<string, string> = {
  WLD: "#111111", KOR: "#c92a2a", USA: "#1971c2", CHN: "#e8590c", JPN: "#7048e8", DEU: "#2b8a3e", IND: "#c2255c",
};

export function mergeWorld(ind: WorldIndicator): Record<string, number>[] {
  const years = Array.from(new Set(ind.entities.flatMap((e) => e.series.map((p) => p.year)))).sort((a, b) => a - b);
  return years.map((y) => {
    const row: Record<string, number> = { year: y };
    ind.entities.forEach((e) => {
      const p = e.series.find((s) => s.year === y);
      if (p) row[e.iso] = p.v;
    });
    return row;
  });
}

export function WorldTip({ active, payload, label, unit }: { active?: boolean; payload?: { dataKey: string; name: string; value: number; color: string }[]; label?: number; unit: string }) {
  if (!active || !payload || !payload.length) return null;
  const rows = payload.filter((p) => p.value != null).sort((a, b) => b.value - a.value);
  return (
    <div className="rounded border border-[#d0d0d0] bg-white px-2 py-1 text-[11px] shadow-sm">
      <div className="mb-0.5 font-bold text-[#666]">{label}년</div>
      {rows.map((p) => (
        <div key={p.dataKey} className="flex justify-between gap-3 tabular-nums">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-bold text-[#222]">{p.value}{unit}</span>
        </div>
      ))}
    </div>
  );
}

export function WorldLines({ ind, big }: { ind: WorldIndicator; big?: boolean }) {
  const zeroLine = ind.kind === "rate" || ind.kind === "ratio";
  return (
    <LineChart data={mergeWorld(ind)} margin={{ top: 6, right: big ? 16 : 6, bottom: 2, left: big ? 8 : 0 }}>
      <CartesianGrid stroke={big ? "#eee" : "#f3f3f3"} vertical={false} />
      <XAxis dataKey="year" tick={{ fill: big ? "#888" : "#bbb", fontSize: big ? 11 : 9 }} minTickGap={big ? 50 : 36} interval="preserveStartEnd" tickLine={false} />
      {big ? <YAxis orientation="right" width={46} tick={{ fill: "#888", fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => `${v}${ind.unit}`} /> : <YAxis hide domain={["auto", "auto"]} />}
      {zeroLine && <ReferenceLine y={0} stroke="#c8c8c8" />}
      <Tooltip content={<WorldTip unit={ind.unit} />} />
      {big && <Legend wrapperStyle={{ fontSize: 11 }} />}
      {ind.entities.map((e) => (
        <Line key={e.iso} dataKey={e.iso} name={e.name} stroke={ENT_COLOR[e.iso] ?? "#888"} dot={false}
          strokeWidth={e.iso === "WLD" ? 2.2 : big ? 1.6 : 1.3} strokeDasharray={e.iso === "WLD" ? "5 3" : undefined}
          connectNulls isAnimationActive={false} />
      ))}
    </LineChart>
  );
}

export function WorldIndicatorCard({ ind, onOpen }: { ind: WorldIndicator; onOpen: () => void }) {
  return (
    <div className="cursor-pointer rounded-lg border border-[#e0e0e0] bg-white p-3 transition hover:bg-[#f7faf8]" onClick={onOpen} title="클릭하면 크게 보기">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-bold text-[#222]">{ind.label}</span>
        {ind.world_latest != null && (
          <span className="text-[11px] text-[#888]">세계 <span className="font-bold text-[#111]">{ind.world_latest}{ind.unit}</span> <span className="text-[#bbb]">’{String(ind.world_year).slice(2)}</span></span>
        )}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
        {ind.entities.filter((e) => e.iso !== "WLD").map((e) => (
          <span key={e.iso} className="text-[11px] tabular-nums" style={{ color: ENT_COLOR[e.iso] ?? "#666" }}>
            <span className="font-semibold">{e.name}</span> {e.latest}{ind.unit}
          </span>
        ))}
      </div>
      <div className="mt-1.5 h-36 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <WorldLines ind={ind} />
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[10px] leading-tight text-[#999]">{ind.desc}</p>
    </div>
  );
}

export function WorldIndicatorModal({ ind, onClose }: { ind: WorldIndicator; onClose: () => void }) {
  return (
    <Modal title={ind.label} sub={`World Bank · 단위 ${ind.unit} · 한·미·중·일·독·인도${ind.world_latest != null ? " + 세계집계" : ""}`} onClose={onClose}>
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {ind.entities.map((e) => (
          <Stat key={e.iso} label={`${e.name} (${e.latest_year})`} value={`${e.latest}${ind.unit}`} color={ENT_COLOR[e.iso]} />
        ))}
      </div>
      <div className="h-[420px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <WorldLines ind={ind} big />
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs leading-snug text-[#666]">{ind.desc}</p>
    </Modal>
  );
}
