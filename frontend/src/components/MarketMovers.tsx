"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, Movers, MoversHistoryItem, Mover, MoverSector } from "@/lib/api";

const GREEN = "#c0392b"; // 한국식: 상승=빨강
const BLUE = "#1c64c4";  // 하락=파랑

function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return `${(v / 1e12).toFixed(1)}조`;
  if (a >= 1e8) return `${Math.round(v / 1e8).toLocaleString("ko-KR")}억`;
  if (a >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만`;
  return `${Math.round(v).toLocaleString("ko-KR")}`;
}
const pct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
const cColor = (v: number) => (v > 0 ? GREEN : v < 0 ? BLUE : "#666");

function StockCard({ m }: { m: Mover }) {
  return (
    <div className="rounded-lg border border-[#e8e8e8] bg-white p-2.5">
      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-1.5">
          <span className="text-sm font-bold text-[#1f1f1f]">{m.name}</span>
          <span className="text-[10px] text-[#999]">{m.sector}</span>
        </div>
        <span className="text-sm font-bold tabular-nums" style={{ color: cColor(m.change_pct) }}>{pct(m.change_pct)}</span>
      </div>
      <div className="mt-0.5 flex items-center justify-between text-[10px] text-[#888]">
        <span>{Math.round(m.close).toLocaleString("ko-KR")}원</span>
        <span>거래대금 {eok(m.value)}원</span>
      </div>
      {m.news.length > 0 ? (
        <ul className="mt-1.5 flex flex-col gap-0.5 border-t border-[#f2f2f2] pt-1.5">
          {m.news.slice(0, 4).map((n, i) => (
            <li key={i} className="text-[11px] leading-snug">
              <a href={n.link} target="_blank" rel="noreferrer" className="text-[#245] hover:text-[#1971c2] hover:underline">· {n.title}</a>
              {n.source && <span className="ml-1 text-[9px] text-[#aaa]">{n.source}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-1.5 border-t border-[#f2f2f2] pt-1.5 text-[10px] text-[#bbb]">관련 뉴스를 찾지 못했습니다.</div>
      )}
    </div>
  );
}

function SectorRow({ s, maxAbs }: { s: MoverSector; maxAbs: number }) {
  const w = Math.max(3, (Math.abs(s.avg_change_pct) / maxAbs) * 100);
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-28 shrink-0 truncate text-right text-[#444]" title={s.sector}>{s.sector}</span>
      <div className="relative h-3.5 flex-1 rounded bg-[#f0f0f0]">
        <div className="absolute inset-y-0 rounded" style={{ width: `${w}%`, background: cColor(s.avg_change_pct), left: s.avg_change_pct >= 0 ? 0 : "auto", right: s.avg_change_pct < 0 ? 0 : "auto" }} />
      </div>
      <span className="w-14 shrink-0 text-right font-bold tabular-nums" style={{ color: cColor(s.avg_change_pct) }}>{pct(s.avg_change_pct)}</span>
      <span className="hidden w-24 shrink-0 truncate text-[9px] text-[#999] sm:inline">{s.leaders.map((l) => l.name).join(", ")}</span>
    </div>
  );
}

export function MarketMovers() {
  const [d, setD] = useState<Movers | null>(null);
  const [hist, setHist] = useState<MoversHistoryItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [showHist, setShowHist] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback((refresh = false) => {
    setBusy(true);
    api.movers(refresh).then(setD).catch(() => {}).finally(() => setBusy(false));
    api.moversHistory(60).then((r) => setHist(r.items)).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    timer.current = setInterval(() => load(false), 60000); // 60초마다 자동 갱신
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [load]);

  const maxSec = d ? Math.max(1, ...[...d.sectors_up, ...d.sectors_down].map((s) => Math.abs(s.avg_change_pct))) : 1;

  return (
    <div className="flex flex-col gap-4">
      {/* 헤더 */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#d0d0d0] bg-white px-4 py-3 shadow-sm">
        <div>
          <div className="text-base font-bold text-[#1f1f1f]">급등락 원인 규명</div>
          <div className="text-[11px] text-[#888]">급등/급락 종목·업종을 자동 감지하고 관련 뉴스로 원인을 찾습니다 · 60초 자동 갱신</div>
        </div>
        <div className="flex items-center gap-3">
          {d?.breadth && (
            <div className="text-xs">
              <span className="font-bold" style={{ color: GREEN }}>▲{d.breadth.advancers}</span>
              <span className="mx-1 text-[#ccc]">/</span>
              <span className="font-bold" style={{ color: BLUE }}>▼{d.breadth.decliners}</span>
              <span className="ml-1 text-[10px] text-[#aaa]">(거래대금 10억↑ {d.count}종목)</span>
            </div>
          )}
          {d && <span className="text-[10px] text-[#aaa]">{d.generated_at}</span>}
          <button onClick={() => load(true)} disabled={busy} className="rounded bg-[#217346] px-3 py-1 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">{busy ? "분석 중…" : "↻ 새로고침"}</button>
        </div>
      </div>

      {!d ? (
        <div className="py-16 text-center text-sm text-[#888]">분석 중…</div>
      ) : (
        <>
          {/* AI 종합 원인 */}
          {d.ai?.overall ? (
            <div className="rounded-md border border-[#cfe3d6] bg-[#f2f8f4] p-4 shadow-sm">
              <div className="mb-1 flex items-center gap-2">
                <span className="rounded bg-[#217346] px-1.5 py-0.5 text-[10px] font-bold text-white">AI 종합</span>
                {d.ai.model && <span className="text-[9px] text-[#aaa]">{d.ai.model}</span>}
              </div>
              <p className="text-sm leading-relaxed text-[#1f3d2a]">{d.ai.overall}</p>
              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {d.ai.losers_cause && <div className="rounded bg-white/70 p-2 text-[11px] leading-relaxed text-[#245]"><b style={{ color: BLUE }}>급락 원인</b> · {d.ai.losers_cause}</div>}
                {d.ai.gainers_cause && <div className="rounded bg-white/70 p-2 text-[11px] leading-relaxed text-[#245]"><b style={{ color: GREEN }}>급등 원인</b> · {d.ai.gainers_cause}</div>}
              </div>
              {d.ai.drivers && d.ai.drivers.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">{d.ai.drivers.map((x, i) => <span key={i} className="rounded bg-[#eef4f0] px-1.5 py-0.5 text-[10px] text-[#245]">{x}</span>)}</div>
              )}
            </div>
          ) : (
            <div className="rounded-md border border-[#f0e6c9] bg-[#fdfaf0] px-4 py-2 text-[11px] text-[#7a5f10]">
              AI 종합 원인은 선택 기능입니다. 백엔드 <code className="rounded bg-white px-1">ANTHROPIC_API_KEY</code> 설정 시, 아래 뉴스를 근거로 원인을 한두 문장으로 요약합니다. 지금은 종목별 관련 뉴스로 원인을 확인하세요.
            </div>
          )}

          {/* 업종 히트맵 */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-md border border-[#d0d0d0] bg-white p-3 shadow-sm">
              <div className="mb-2 text-sm font-bold" style={{ color: BLUE }}>하락 주도 업종</div>
              <div className="flex flex-col gap-1">{d.sectors_down.map((s) => <SectorRow key={s.sector} s={s} maxAbs={maxSec} />)}</div>
            </div>
            <div className="rounded-md border border-[#d0d0d0] bg-white p-3 shadow-sm">
              <div className="mb-2 text-sm font-bold" style={{ color: GREEN }}>상승 주도 업종</div>
              <div className="flex flex-col gap-1">{d.sectors_up.map((s) => <SectorRow key={s.sector} s={s} maxAbs={maxSec} />)}</div>
            </div>
          </div>

          {/* 급락 / 급등 종목 + 원인 뉴스 */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div>
              <div className="mb-2 border-l-4 pl-2 text-sm font-bold" style={{ borderColor: BLUE, color: BLUE }}>급락 종목 · 원인</div>
              <div className="flex flex-col gap-2">{d.losers.map((m) => <StockCard key={m.ticker} m={m} />)}</div>
            </div>
            <div>
              <div className="mb-2 border-l-4 pl-2 text-sm font-bold" style={{ borderColor: GREEN, color: GREEN }}>급등 종목 · 원인</div>
              <div className="flex flex-col gap-2">{d.gainers.map((m) => <StockCard key={m.ticker} m={m} />)}</div>
            </div>
          </div>

          {/* 원인 이력 */}
          <div className="rounded-md border border-[#d0d0d0] bg-white shadow-sm">
            <button onClick={() => setShowHist((v) => !v)} className="flex w-full items-center justify-between px-4 py-2 text-sm font-semibold text-[#217346]">
              <span>원인 이력 (자동 기록 {hist.length}건)</span>
              <span className="text-xs text-[#888]">{showHist ? "접기 ▲" : "펼치기 ▼"}</span>
            </button>
            {showHist && (
              <div className="max-h-96 overflow-y-auto border-t border-[#eee]">
                {hist.length === 0 ? (
                  <div className="px-4 py-6 text-center text-xs text-[#999]">아직 기록이 없습니다. 스케줄러가 장중 15분마다 자동으로 급등락·원인을 기록합니다.</div>
                ) : hist.map((h, i) => (
                  <div key={i} className="border-b border-[#f2f2f2] px-4 py-2 text-[11px]">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[#555]">{h.generated_at}</span>
                      {h.breadth && <span className="text-[10px] text-[#aaa]"><span style={{ color: GREEN }}>▲{h.breadth.advancers}</span> <span style={{ color: BLUE }}>▼{h.breadth.decliners}</span></span>}
                    </div>
                    <div className="mt-0.5 flex flex-wrap gap-x-3 text-[10px]">
                      {h.losers[0] && <span style={{ color: BLUE }}>급락 {h.losers.map((x) => `${x.name}(${pct(x.change_pct)})`).join(", ")}</span>}
                      {h.gainers[0] && <span style={{ color: GREEN }}>급등 {h.gainers.map((x) => `${x.name}(${pct(x.change_pct)})`).join(", ")}</span>}
                    </div>
                    {(h.overall || h.losers_cause) && <div className="mt-0.5 text-[10px] leading-relaxed text-[#666]">{h.overall || h.losers_cause}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="text-[10px] leading-relaxed text-[#bbb]">{d.note}</div>
        </>
      )}
    </div>
  );
}
