"use client";

import { useEffect, useRef, useState } from "react";
import { api, LivePulse as LivePulseData, MacroDriver, PulseFlowItem } from "@/lib/api";

// KR convention: red = 긍정/상승, blue = 부정/하락.
const RED = "#c92a2a";
const BLUE = "#1971c2";

function toneColor(t?: string): string {
  return t === "긍정" ? RED : t === "부정" ? BLUE : "#666";
}
const REGION_FLAG: Record<string, string> = { 국내: "🇰🇷", 해외: "🌐" };

export function LivePulse() {
  const [d, setD] = useState<LivePulseData | null>(null);
  const [live, setLive] = useState(false);
  const [err, setErr] = useState("");
  const [refreshedAt, setRefreshedAt] = useState<string>("");
  const first = useRef(true);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .livePulse()
        .then((r) => {
          if (!alive) return;
          setD(r);
          setLive(true);
          setErr("");
          const now = new Date();
          setRefreshedAt(now.toLocaleTimeString("ko-KR", { hour12: false }));
        })
        .catch((e) => {
          if (alive && first.current) setErr(e?.message ?? "실시간 시황을 불러오지 못했습니다.");
        })
        .finally(() => {
          first.current = false;
        });
    load();
    const id = setInterval(load, 30000); // 30초마다 실시간 갱신
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (err && !d)
    return (
      <Sheet title="실시간 시황.xlsx" right={null}>
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      </Sheet>
    );
  if (!d)
    return (
      <Sheet title="실시간 시황.xlsx" right={null}>
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
          시황·분석 글 취합 중…
        </div>
      </Sheet>
    );

  const p = d.pulse;
  const vColor = toneColor(p.tone);
  // score gauge: -100..100 → 0..100% (50% = 중립)
  const gauge = Math.max(0, Math.min(100, 50 + p.score / 2));

  return (
    <Sheet
      title="실시간 시황.xlsx"
      right={
        <span className="flex items-center gap-1.5 text-xs font-bold" style={{ color: live ? "#bff5cf" : "#ddd" }}>
          <span className={`inline-block h-2 w-2 rounded-full ${live ? "animate-pulse" : ""}`} style={{ background: live ? "#7ee2a0" : "#bbb" }} />
          LIVE {refreshedAt && <span className="font-normal text-white/70">갱신 {refreshedAt}</span>}
        </span>
      }
    >
      <div className="space-y-5 bg-[#fafafa] p-4">
        {/* ── pulse verdict banner ───────────────────────────── */}
        <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
          <div className="flex flex-wrap items-center gap-3 border-b border-[#eee] px-4 py-3">
            <span className="rounded-full px-4 py-1.5 text-base font-bold text-white" style={{ background: vColor }}>
              {p.verdict}
            </span>
            <span className="text-sm text-[#444]">{p.narrative}</span>
            <span className="ml-auto text-xs text-[#999]">
              취합 {d.pool_size}건 · 기준 {d.as_of?.slice(11)}
            </span>
          </div>
          {/* sentiment gauge */}
          <div className="px-4 py-3">
            <div className="mb-1 flex items-center justify-between text-xs text-[#888]">
              <span style={{ color: BLUE }}>약세 ◀ 부정 {p.neg}</span>
              <span className="font-bold" style={{ color: vColor }}>
                심리 점수 {p.score > 0 ? "+" : ""}{p.score}
              </span>
              <span style={{ color: RED }}>긍정 {p.pos} ▶ 강세</span>
            </div>
            <div className="relative h-3 w-full overflow-hidden rounded-full border border-[#e0e0e0] bg-gradient-to-r from-[#1971c2] via-[#e9e9e9] to-[#c92a2a]">
              <div className="absolute top-[-3px] h-[18px] w-[3px] rounded bg-[#1f1f1f]" style={{ left: `calc(${gauge}% - 1.5px)` }} />
            </div>
            <div className="mt-1 text-[11px] text-[#aaa]">중립 {p.neutral}건 · 시황/전망/전략/수급 류 기사 기준 (Google News)</div>
          </div>
        </section>

        {/* ── what's driving the market ──────────────────────── */}
        {d.drivers.length > 0 && (
          <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
            <div className="border-b border-[#d0d0d0] bg-[#9dc3e6] px-3 py-1.5 text-sm font-bold text-[#1a3a5e]">
              🚦 시장을 끌고 있는 이슈 (실시간)
            </div>
            <div className="grid gap-px bg-[#eee] sm:grid-cols-2 xl:grid-cols-3">
              {d.drivers.slice(0, 9).map((dr) => (
                <DriverCard key={dr.theme} dr={dr} />
              ))}
            </div>
          </section>
        )}

        {/* ── live flow feed (시간순) ─────────────────────────── */}
        <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-[#d0d0d0] bg-[#217346] px-3 py-1.5 text-sm font-bold text-white">
            <span>📰 실시간 흐름 — 시황·분석 (최신순)</span>
            <span className="text-xs font-normal text-white/70">30초마다 자동 갱신</span>
          </div>
          <ul className="divide-y divide-[#f0f0f0]">
            {d.flow.map((it, i) => (
              <FlowRow key={`${it.title}-${i}`} it={it} />
            ))}
          </ul>
        </section>

        <p className="px-1 text-center text-[11px] leading-relaxed text-[#999]">
          시황·전망·전략·수급 류 기사(국내·해외)를 실시간 취합해 전반 분위기와 흐름을 읽어낸 <b className="text-[#666]">규칙 기반 요약</b>이며, 투자 권유가 아닙니다. 분위기는 헤드라인의 긍정/부정 키워드 집계로 추정합니다.
        </p>
      </div>
    </Sheet>
  );
}

function DriverCard({ dr }: { dr: MacroDriver }) {
  const c = toneColor(dr.direction);
  const top = dr.headlines[0];
  return (
    <div className="bg-white p-3">
      <div className="flex items-center gap-2">
        <span className="text-[13px] font-bold text-[#1f1f1f]">{dr.theme}</span>
        <span className="rounded px-1.5 py-0.5 text-[11px] font-bold text-white" style={{ background: c }}>
          {dr.direction}
        </span>
        <span className="ml-auto text-[11px] text-[#999]">{dr.count}건</span>
      </div>
      {top && (
        <a href={top.link ?? "#"} target="_blank" rel="noopener noreferrer" className="mt-1 block text-[12px] leading-snug text-[#555] hover:text-[#1155cc] hover:underline">
          {top.title}
          {top.source && <span className="ml-1 text-[11px] text-[#aaa]">· {top.source}</span>}
        </a>
      )}
    </div>
  );
}

function FlowRow({ it }: { it: PulseFlowItem }) {
  const c = toneColor(it.lean);
  return (
    <li className="px-3 py-2 hover:bg-[#fff7e6]">
      <div className="flex items-start gap-2.5">
        <span className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: c }} title={it.lean} />
        <div className="min-w-0 flex-1">
          <a href={it.link ?? "#"} target="_blank" rel="noopener noreferrer" className="text-[14px] font-medium leading-snug text-[#1f1f1f] hover:text-[#1155cc] hover:underline">
            {it.title}
          </a>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-[#999]">
            {it.ago && <span className="font-semibold text-[#217346]">{it.ago}</span>}
            {it.region && <span>{REGION_FLAG[it.region] ?? ""} {it.region}</span>}
            {it.source && <span>· {it.source}</span>}
            <span style={{ color: c }}>· {it.lean}</span>
          </div>
          {it.cluster.length > 0 && (
            <ul className="mt-1 space-y-0.5 border-l-2 border-[#e6e6e6] pl-2">
              {it.cluster.map((line, i) => (
                <li key={i} className="text-[12px] leading-snug text-[#777]">· {line}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </li>
  );
}

function Sheet({ title, right, children }: { title: string; right: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold">
          <span className="text-base">📡</span> {title}
        </span>
        {right}
      </div>
      {children}
    </div>
  );
}
