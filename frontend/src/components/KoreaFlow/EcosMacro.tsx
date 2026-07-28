"use client";

import { useEffect, useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts";
import { api, EcosIndicator, EcosMacro } from "@/lib/api";
import { BLUE, Modal, RED, Stat, growthColor, retStyle } from "./shared";

export function EcosMacroSection() {
  const [d, setD] = useState<EcosMacro | null>(null);
  const [loading, setLoading] = useState(true);
  const [sel, setSel] = useState<EcosIndicator | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .ecosMacro()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      {sel && <EcosChartModal ind={sel} onClose={() => setSel(null)} />}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#1b5e3a] px-3 py-1.5">
        <span className="text-sm font-bold text-white">국내 돈 흐름 — 거시지표 (한국은행 ECOS)</span>
        <span className="text-[11px] text-white/70">M2 통화량 · 가계 빚 · 집값 · <span className="text-white/90">카드를 클릭하면 크게 보기</span></span>
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">거시지표 불러오는 중…</div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "거시지표를 불러오지 못했습니다."}</div>
      ) : (
        <div className="divide-y divide-[#eee]">
          {Array.from(new Set(d.indicators.map((i) => i.group))).map((g) => (
            <div key={g} className="p-2">
              <div className="mb-1 px-1 text-[11px] font-bold uppercase tracking-wide text-[#1b5e3a]">{g}</div>
              <div className="grid gap-px bg-[#eee] md:grid-cols-2 xl:grid-cols-3">
                {d.indicators.filter((i) => i.group === g).map((i) => (
                  <EcosCard key={i.key} ind={i} onOpen={() => setSel(i)} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// 전체 기간 누적 변화 텍스트: level=%, rate=%p, index=p, flow=억$
export function spanChange(ind: EcosIndicator): { text: string; up: boolean } {
  const s = ind.span;
  if (s.kind === "level") {
    const v = s.change_pct ?? 0;
    return { text: `${v > 0 ? "+" : ""}${v}%`, up: v >= 0 };
  }
  const v = s.change_delta ?? 0;
  const unit = s.kind === "rate" ? "%p" : s.kind === "flow" ? "억$" : "p";
  return { text: `${v > 0 ? "+" : ""}${v}${unit}`, up: v >= 0 };
}

export function EcosChartTip({ active, payload, label, kind }: { active?: boolean; payload?: { value: number }[]; label?: string; kind: string }) {
  if (!active || !payload || !payload.length) return null;
  const unit = kind === "rate" ? "%" : "";
  return (
    <div className="rounded border border-[#d0d0d0] bg-white px-2 py-1 text-[11px] shadow-sm">
      <div className="text-[#888]">{label}</div>
      <div className="font-bold tabular-nums text-[#1f1f1f]">{payload[0].value.toLocaleString("ko-KR")}{unit}</div>
    </div>
  );
}

export function EcosCard({ ind, onOpen }: { ind: EcosIndicator; onOpen: () => void }) {
  const chg = spanChange(ind);
  const color = chg.up ? RED : BLUE;
  // 100 기준선이 의미 있는 심리지수만 기준선 표시
  const showBase = ind.kind === "index";
  return (
    <div className="group cursor-pointer bg-white p-3 transition hover:bg-[#f7faf8]" onClick={onOpen} title="클릭하면 크게 보기">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold text-[#555]">{ind.label}</span>
        <span className="text-lg font-bold tabular-nums text-[#1f1f1f]">{ind.display}</span>
      </div>
      <div className="mt-0.5 flex items-center justify-between text-[10px]">
        <span className="text-[#aaa]">{ind.period} 기준</span>
        <span className="tabular-nums text-[#aaa]">
          {ind.span.from} → {ind.span.to} <span className="font-bold" style={{ color }}>{chg.text}</span>
        </span>
      </div>

      {/* 전체 기간 그래프 */}
      <div className="mt-1.5 h-28 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={ind.series} margin={{ top: 4, right: 6, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#f3f3f3" vertical={false} />
            <XAxis dataKey="t" tick={{ fill: "#bbb", fontSize: 9 }} minTickGap={48} interval="preserveStartEnd" tickLine={false} />
            <YAxis hide domain={["auto", "auto"]} />
            {showBase && <ReferenceLine y={100} stroke="#d0d0d0" strokeDasharray="3 3" />}
            <Tooltip content={<EcosChartTip kind={ind.kind} />} />
            <Line dataKey="v" stroke={color} dot={false} strokeWidth={1.4} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-1 flex items-center gap-2 text-xs">
        <span className="text-[#888]">{ind.yoy_label}</span>
        <span className="font-bold tabular-nums" style={retStyle(ind.yoy)}>
          {ind.yoy != null ? `${ind.yoy > 0 ? "+" : ""}${ind.yoy}%` : "—"}
        </span>
        {ind.mom != null && (
          <span className="text-[#aaa]">· MoM <span style={retStyle(ind.mom)}>{ind.mom > 0 ? "+" : ""}{ind.mom}%</span></span>
        )}
      </div>
      <p className="mt-1 text-[10px] leading-tight text-[#999]">{ind.desc}</p>
    </div>
  );
}

export function fmtNum(v: number): string {
  return Math.abs(v) >= 100 ? Math.round(v).toLocaleString("ko-KR") : v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

export function EcosChartModal({ ind, onClose }: { ind: EcosIndicator; onClose: () => void }) {
  const chg = spanChange(ind);
  const color = chg.up ? RED : BLUE;
  const showBase = ind.kind === "index";
  const vals = ind.series.map((p) => p.v);
  const min = Math.min(...vals), max = Math.max(...vals);
  const minPt = ind.series.find((p) => p.v === min);
  const maxPt = ind.series.find((p) => p.v === max);
  const unit = ind.kind === "rate" ? "%" : "";
  const chgColor = chg.up ? RED : BLUE;
  return (
    <Modal title={ind.label} sub={`${ind.span.from} ~ ${ind.span.to} · 전체 ${ind.span.n.toLocaleString("ko-KR")}개 구간 · 한국은행 ECOS`} onClose={onClose}>
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label={`현재 (${ind.period})`} value={ind.display} />
        <Stat label="전 구간 누적" value={chg.text} color={chgColor} />
        <Stat label={ind.yoy_label} value={ind.yoy != null ? `${ind.yoy > 0 ? "+" : ""}${ind.yoy}%` : "—"} color={ind.yoy != null ? growthColor(ind.yoy) : undefined} />
        <Stat label="최고" value={`${fmtNum(max)}${unit}`} color={RED} />
        <Stat label="최저" value={`${fmtNum(min)}${unit}`} color={BLUE} />
      </div>
      <div className="h-[420px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={ind.series} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid stroke="#eee" vertical={false} />
            <XAxis dataKey="t" tick={{ fill: "#888", fontSize: 11 }} minTickGap={60} interval="preserveStartEnd" />
            <YAxis orientation="right" width={58} tick={{ fill: "#888", fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => fmtNum(Number(v))} />
            {showBase && <ReferenceLine y={100} stroke="#c0c0c0" strokeDasharray="4 4" label={{ value: "100 중립", fontSize: 10, fill: "#999", position: "insideTopRight" }} />}
            {ind.kind === "flow" && <ReferenceLine y={0} stroke="#c0c0c0" />}
            <Tooltip content={<EcosChartTip kind={ind.kind} />} />
            <Line dataKey="v" stroke={color} dot={false} strokeWidth={1.8} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs leading-snug text-[#666]">{ind.desc}</p>
      {maxPt && minPt && (
        <p className="mt-1 text-[11px] text-[#999]">최고 {maxPt.t} · 최저 {minPt.t} · 시작 {ind.span.from} {fmtNum(ind.span.first)}{unit} → 현재 {fmtNum(ind.span.last)}{unit}</p>
      )}
    </Modal>
  );
}
