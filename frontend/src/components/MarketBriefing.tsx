"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Briefing, BriefSignal } from "@/lib/api";

const UP = "#c0392b";   // 한국식: 상승=빨강
const DOWN = "#1c64c4"; // 하락=파랑
const cColor = (v: number | null | undefined) => (v == null ? "#666" : v > 0 ? UP : v < 0 ? DOWN : "#666");
const pct = (v: number | null | undefined) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);

const KEY_ORDER: { key: string; label: string }[] = [
  { key: "sp500", label: "S&P 500" }, { key: "nasdaq", label: "나스닥" },
  { key: "sox", label: "반도체(SOX)" }, { key: "vix", label: "VIX" },
  { key: "usdkrw", label: "원/달러" }, { key: "wti", label: "WTI 유가" },
];

function biasColor(b: string | null): string {
  if (!b) return "#666";
  if (b.includes("강세")) return UP;
  if (b.includes("약세")) return DOWN;
  return "#e8890c";
}

export function MarketBriefing() {
  const [d, setD] = useState<Briefing | null>(null);
  const [market, setMarket] = useState<"auto" | "kr" | "us">("auto");
  const [busy, setBusy] = useState(false);

  const load = useCallback((m: "auto" | "kr" | "us") => {
    setBusy(true);
    api.briefing(m).then(setD).catch(() => {}).finally(() => setBusy(false));
  }, []);
  useEffect(() => { load(market); }, [market, load]);

  const sig = (k: string): BriefSignal | undefined => d?.signals.find((s) => s.key === k);
  const n = d?.narrative;
  const o = d?.outlook;

  return (
    <div className="flex flex-col gap-4">
      {/* 헤더 */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#d0d0d0] bg-white px-4 py-3 shadow-sm">
        <div>
          <div className="text-base font-bold text-[#1f1f1f]">장전 브리핑</div>
          <div className="text-[11px] text-[#888]">개장 전, 밤사이 있었던 일들을 브리핑하고 오늘 흐름을 분석합니다</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex overflow-hidden rounded border border-[#cdcdcd] text-xs">
            {(["auto", "kr", "us"] as const).map((m) => (
              <button key={m} onClick={() => setMarket(m)}
                className={`px-2.5 py-1 ${market === m ? "bg-[#217346] font-semibold text-white" : "bg-white text-[#555] hover:bg-[#f0f0f0]"}`}>
                {m === "auto" ? "자동" : m === "kr" ? "한국장" : "미국장"}
              </button>
            ))}
          </div>
          <button onClick={() => load(market)} disabled={busy} className="rounded bg-[#217346] px-3 py-1 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">{busy ? "불러오는 중…" : "↻"}</button>
        </div>
      </div>

      {!d ? (
        <div className="py-16 text-center text-sm text-[#888]">브리핑 준비 중…</div>
      ) : (
        <>
          {/* 브리핑 서술 */}
          <div className="rounded-md border border-[#cfe3d6] bg-[#f2f8f4] p-4 shadow-sm">
            <div className="mb-1 flex items-center gap-2">
              <span className="rounded bg-[#217346] px-1.5 py-0.5 text-[10px] font-bold text-white">{d.market_label}</span>
              <span className="text-[10px] text-[#888]">{n?.source && n.source !== "rule" ? `AI ${n.source}` : "규칙 기반"} · {d.generated_at}</span>
            </div>
            <h3 className="text-base font-bold text-[#1f3d2a]">{n?.headline}</h3>
            {n?.one_liner && <p className="mt-0.5 text-sm text-[#245]">{n.one_liner}</p>}
            {n?.recap && n.recap.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1 text-[13px] leading-relaxed text-[#333]">
                {n.recap.map((r, i) => <li key={i}>• {r}</li>)}
              </ul>
            )}
            {n?.outlook && (
              <div className="mt-2 rounded bg-white/70 p-2 text-[13px] leading-relaxed text-[#1f3d2a]"><b>오늘 전망 </b>{n.outlook}</div>
            )}
            {n?.risks && n.risks.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">{n.risks.map((r, i) => <span key={i} className="rounded bg-[#fdf3f3] px-1.5 py-0.5 text-[10px] text-[#a33]">⚠ {r}</span>)}</div>
            )}
          </div>

          {/* 전일 지표 요약 */}
          <div className="rounded-md border border-[#d0d0d0] bg-white p-3 shadow-sm">
            <div className="mb-2 text-sm font-bold text-[#217346]">전일 해외 마감 · 핵심 지표</div>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
              {KEY_ORDER.map(({ key, label }) => {
                const s = sig(key);
                return (
                  <div key={key} className="rounded border border-[#eee] bg-[#fafafa] px-2 py-2 text-center">
                    <div className="text-[10px] text-[#888]">{label}</div>
                    <div className="text-sm font-bold tabular-nums" style={{ color: cColor(s?.change_pct) }}>{pct(s?.change_pct ?? null)}</div>
                  </div>
                );
              })}
            </div>
            {(d.extras?.gold || d.extras?.btc) && (
              <div className="mt-2 flex gap-2 text-[11px]">
                {d.extras?.gold && <span className="rounded bg-[#fff8e8] px-2 py-1">금 <b style={{ color: cColor(d.extras.gold.change_pct) }}>{pct(d.extras.gold.change_pct ?? null)}</b></span>}
                {d.extras?.btc && <span className="rounded bg-[#fff0e8] px-2 py-1">비트코인 <b style={{ color: cColor(d.extras.btc.change_pct) }}>{pct(d.extras.btc.change_pct ?? null)}</b></span>}
              </div>
            )}
            {d.adrs.length > 0 && (
              <div className="mt-2">
                <div className="mb-1 text-[11px] font-semibold text-[#555]">한국 ADR (간밤 뉴욕 거래)</div>
                <div className="flex flex-wrap gap-1">
                  {d.adrs.map((a) => (
                    <span key={a.name} className="rounded bg-[#f5f7f5] px-1.5 py-0.5 text-[10px]">{a.name} <b style={{ color: cColor(a.change_pct) }}>{pct(a.change_pct)}</b></span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 오늘 전망(수치) */}
          {o && (
            <div className="rounded-md border border-[#d0d0d0] bg-white p-3 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-bold text-[#217346]">오늘 전망 — {o.market}</span>
                {o.bias && <span className="rounded px-2 py-0.5 text-xs font-bold text-white" style={{ background: biasColor(o.bias) }}>{o.bias}</span>}
              </div>
              <div className="flex flex-wrap items-center gap-4 text-xs">
                {o.gauge != null && (
                  <div>방향 게이지 <b className="tabular-nums" style={{ color: cColor(o.gauge) }}>{o.gauge.toFixed(0)}</b> <span className="text-[10px] text-[#aaa]">(-100~+100)</span></div>
                )}
                {(o.expected_gap?.low != null || o.expected_gap?.high != null) && (
                  <div>예상 갭 <b className="tabular-nums" style={{ color: cColor(((o.expected_gap.low ?? 0) + (o.expected_gap.high ?? 0)) / 2) }}>{o.expected_gap.low}% ~ {o.expected_gap.high}%</b></div>
                )}
              </div>
              {o.drivers.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">{o.drivers.slice(0, 8).map((x, i) => <span key={i} className="rounded bg-[#eef4f0] px-1.5 py-0.5 text-[10px] text-[#245]">{x}</span>)}</div>
              )}
              <div className="mt-1.5 text-[10px] text-[#999]">{o.basis}</div>
            </div>
          )}

          {/* 전일 주요 뉴스 */}
          <div className="rounded-md border border-[#d0d0d0] bg-white p-3 shadow-sm">
            <div className="mb-2 text-sm font-bold text-[#217346]">전일 주요 뉴스 · 이야기들</div>
            {d.stories.length === 0 ? (
              <div className="py-4 text-center text-xs text-[#999]">불러온 뉴스가 없습니다.</div>
            ) : (
              <ul className="flex flex-col gap-1">
                {d.stories.map((s, i) => (
                  <li key={i} className="flex items-baseline gap-2 text-[12px] leading-snug">
                    <span className="mt-0.5 shrink-0 rounded bg-[#eef4f0] px-1.5 text-[9px] text-[#245]">{s.topic}</span>
                    <a href={s.link} target="_blank" rel="noreferrer" className="text-[#333] hover:text-[#1971c2] hover:underline">{s.title}</a>
                    {s.source && <span className="shrink-0 text-[9px] text-[#aaa]">{s.source}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="text-[10px] leading-relaxed text-[#bbb]">{d.note}</div>
        </>
      )}
    </div>
  );
}
