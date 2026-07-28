"use client";

import { useEffect, useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts";
import { api, MoneySupply, MoneyCountry, MoneyCrisis } from "@/lib/api";
import { BLUE, Modal, RED, Stat, gpct, growthColor } from "./shared";

export function MoneySupplySection() {
  const [d, setD] = useState<MoneySupply | null>(null);
  const [loading, setLoading] = useState(true);
  const [selC, setSelC] = useState<MoneyCountry | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .moneySupply()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      {selC && <CountryChartModal c={selC} onClose={() => setSelC(null)} />}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#1b5e3a] px-3 py-1.5">
        <span className="text-sm font-bold text-white">통화량 — 과거 위기·해외 주요국 비교</span>
        <span className="text-[11px] text-white/70">지금 풀린 돈을 IMF·금융위기·코로나, 그리고 미·중·일과 견줌</span>
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">통화량 비교 집계 중…</div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "통화량 비교 데이터를 불러오지 못했습니다."}</div>
      ) : (
        <div className="space-y-4 p-3">
          {/* 헤드라인 + 판정 */}
          {d.headline && (
            <div className="rounded border border-[#e6e6e6] bg-[#f8faf9] p-3">
              <div className="flex flex-wrap items-end gap-x-6 gap-y-1">
                <div>
                  <div className="text-[11px] text-[#888]">한국 M2 통화량 ({d.headline.kr_m2_period})</div>
                  <div className="text-lg font-bold tabular-nums text-[#1f1f1f]">{d.headline.kr_m2_display ?? "—"}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#888]">한국 전년동월比</div>
                  <div className="text-base font-bold tabular-nums" style={{ color: growthColor(d.headline.kr_m2_yoy) }}>{gpct(d.headline.kr_m2_yoy)}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#888]">미국 M2 전년동월比</div>
                  <div className="text-base font-bold tabular-nums" style={{ color: growthColor(d.headline.us_m2_yoy) }}>{gpct(d.headline.us_m2_yoy)}</div>
                </div>
                {d.verdict?.avg_20y != null && (
                  <div>
                    <div className="text-[11px] text-[#888]">한국 장기평균(’02~)</div>
                    <div className="text-base font-bold tabular-nums text-[#555]">{gpct(d.verdict.avg_20y)}</div>
                  </div>
                )}
              </div>
              {d.verdict && (
                <p className="mt-2 text-sm font-medium text-[#333]">
                  <span className="mr-1.5 rounded px-1.5 py-0.5 text-xs font-bold text-white" style={{ background: d.verdict.stance.includes("확대") ? RED : d.verdict.stance.includes("둔화") ? BLUE : "#888" }}>
                    {d.verdict.stance}
                  </span>
                  {d.verdict.narrative}
                </p>
              )}
            </div>
          )}

          {/* 해외 주요국 통화량 증가율 */}
          <div>
            <div className="mb-1.5 text-xs font-bold text-[#244d1a]">해외 주요국 통화량(M2) 증가율 — 국가 간 동일 기준(World Bank, 연%) <span className="font-normal text-[#999]">· 카드 클릭하면 크게</span></div>
            <div className="grid gap-px bg-[#eee] sm:grid-cols-2 lg:grid-cols-4">
              {d.countries.map((c) => (
                <CountryCard key={c.iso} c={c} onOpen={() => setSelC(c)} />
              ))}
            </div>
          </div>

          {/* 과거 경제위기 때 통화량 */}
          <div>
            <div className="mb-1.5 text-xs font-bold text-[#244d1a]">과거 경제위기 때 통화량은 어떻게 움직였나</div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {d.crises.map((c) => (
                <CrisisCard key={c.key} c={c} />
              ))}
            </div>
          </div>

          <p className="text-[10px] leading-tight text-[#aaa]">{d.note}</p>
          <p className="text-[10px] text-[#bbb]">출처: {d.source}</p>
        </div>
      )}
    </section>
  );
}

export function toneColor(t?: string): string {
  return t === "hot" ? RED : t === "cold" ? BLUE : t === "mixed" ? "#b8860b" : "#666";
}

export function MoneyGrowthTip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: number }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded border border-[#d0d0d0] bg-white px-2 py-1 text-[11px] shadow-sm">
      <span className="text-[#888]">{label}년 </span>
      <span className="font-bold tabular-nums" style={{ color: growthColor(payload[0].value) }}>{gpct(payload[0].value)}</span>
    </div>
  );
}

export function CountryCard({ c, onOpen }: { c: MoneyCountry; onOpen: () => void }) {
  const color = toneColor(c.tone);
  return (
    <div className="cursor-pointer bg-white p-3 transition hover:bg-[#f7faf8]" onClick={onOpen} title="클릭하면 크게 보기">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-[#333]">{c.name} <span className="font-normal text-[#aaa]">({c.currency})</span></span>
        <span className="text-[10px] text-[#aaa]">{c.avg_years}</span>
      </div>
      <div className="mt-1 flex items-end justify-between gap-2">
        <div className="text-lg font-bold tabular-nums" style={{ color }}>{gpct(c.latest)}<span className="ml-1 text-[10px] font-normal text-[#aaa]">{c.latest_year}</span></div>
        <div className="text-right text-[10px] text-[#aaa]">평균 {gpct(c.avg)}</div>
      </div>
      {/* 전체 기간 통화량 증가율 그래프 */}
      <div className="mt-1 h-24 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={c.series} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#f3f3f3" vertical={false} />
            <XAxis dataKey="year" tick={{ fill: "#bbb", fontSize: 9 }} minTickGap={40} interval="preserveStartEnd" tickLine={false} />
            <YAxis hide domain={["auto", "auto"]} />
            <ReferenceLine y={0} stroke="#d0d0d0" />
            <Tooltip content={<MoneyGrowthTip />} />
            <Line dataKey="growth" stroke={color} dot={false} strokeWidth={1.4} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-[#999]">
        <span>최고 <span className="font-bold" style={{ color: RED }}>{gpct(c.max)}</span> <span className="text-[#bbb]">’{String(c.max_year).slice(2)}</span></span>
        <span>최저 <span className="font-bold" style={{ color: BLUE }}>{gpct(c.min)}</span> <span className="text-[#bbb]">’{String(c.min_year).slice(2)}</span></span>
      </div>
    </div>
  );
}

export function CountryChartModal({ c, onClose }: { c: MoneyCountry; onClose: () => void }) {
  const color = toneColor(c.tone);
  return (
    <Modal title={`${c.name} 통화량(M2) 증가율`} sub={`${c.avg_years} · 광의통화 전년比 증가율(%) · World Bank`} onClose={onClose}>
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label={`최신 (${c.latest_year})`} value={gpct(c.latest)} color={color} />
        <Stat label="기간 평균" value={gpct(c.avg)} />
        <Stat label={`최고 (’${String(c.max_year).slice(2)})`} value={gpct(c.max)} color={RED} />
        <Stat label={`최저 (’${String(c.min_year).slice(2)})`} value={gpct(c.min)} color={BLUE} />
      </div>
      <div className="h-[420px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={c.series} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid stroke="#eee" vertical={false} />
            <XAxis dataKey="year" tick={{ fill: "#888", fontSize: 11 }} minTickGap={40} interval="preserveStartEnd" />
            <YAxis orientation="right" width={48} tick={{ fill: "#888", fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => `${v}%`} />
            <ReferenceLine y={0} stroke="#c0c0c0" />
            <Tooltip content={<MoneyGrowthTip />} />
            <Line dataKey="growth" stroke={color} dot={{ r: 2, fill: color }} strokeWidth={1.8} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-[11px] leading-snug text-[#777]">
        증가율이 높을수록 통화량이 빠르게 늘어난(유동성 확대) 해. 1997 외환위기·2008 금융위기·2020 코로나 같은 구간의 굴곡이 보인다.
      </p>
    </Modal>
  );
}

export function GrowthChips({ label, pts }: { label: string; pts: { year: number; growth: number | null }[] | null }) {
  if (!pts || pts.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 text-[11px]">
      <span className="text-[#999]">{label}</span>
      {pts.map((p) => (
        <span key={p.year} className="rounded bg-[#f1f1f1] px-1.5 py-0.5 tabular-nums">
          ’{String(p.year).slice(2)} <span className="font-bold" style={{ color: growthColor(p.growth) }}>{gpct(p.growth)}</span>
        </span>
      ))}
    </div>
  );
}

export function CrisisCard({ c }: { c: MoneyCrisis }) {
  const accent = toneColor(c.tone);
  return (
    <div className="flex flex-col rounded-lg border border-[#e0e0e0] bg-white p-3" style={{ borderTop: `3px solid ${accent}` }}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-bold text-[#222]">{c.name}</span>
        <span className="shrink-0 text-[11px] font-semibold tabular-nums text-[#888]">{c.period}</span>
      </div>
      <div className="text-[11px] text-[#aaa]">{c.scope}</div>
      <div className="mt-1.5 text-sm font-bold" style={{ color: accent }}>{c.headline}</div>
      <div className="mt-1.5 space-y-1">
        <GrowthChips label="한국 M2" pts={c.kr_growth} />
        <GrowthChips label="미국 M2" pts={c.us_growth} />
      </div>
      <p className="mt-2 text-xs leading-snug text-[#555]">{c.narrative}</p>
      <p className="mt-1.5 border-t border-[#f0f0f0] pt-1.5 text-[11px] leading-snug text-[#7a6a00]">
        <span className="font-bold">교훈 </span>{c.lesson}
      </p>
      {c.data_note && <p className="mt-1 text-[10px] text-[#bbb]">※ {c.data_note}</p>}
    </div>
  );
}
