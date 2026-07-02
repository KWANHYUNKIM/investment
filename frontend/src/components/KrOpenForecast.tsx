"use client";

import { useEffect, useRef, useState } from "react";
import { api, Premarket, PremarketHistory, PremarketIndex } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";

function pctStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666", fontWeight: 700 };
}
function pct(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}
function biasColor(b?: string) {
  return b === "강세" ? RED : b === "약세" ? BLUE : "#666";
}
function trendColor(t?: string) {
  return t === "상승추세" ? RED : t === "하락추세" ? BLUE : "#888";
}

function Sparkline({ data, up }: { data: number[]; up: boolean }) {
  const w = 120, h = 34, pad = 2;
  if (data.length < 2) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const span = max - min || 1;
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (v - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const color = up ? RED : BLUE;
  return (
    <svg width={w} height={h} className="shrink-0">
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

function IndexCard({ idx }: { idx: PremarketIndex }) {
  const closes = idx.series.map((s) => s.close);
  const up = (idx.change_pct ?? 0) >= 0;
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-[#e5e5e5] bg-white px-3 py-2">
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-[#333]">{idx.label}</span>
          <span className="text-xs font-semibold" style={{ color: trendColor(idx.trend) }}>
            {idx.trend}
          </span>
        </div>
        <div className="mt-0.5 text-lg font-bold tabular-nums text-[#222]">
          {idx.close.toLocaleString("ko-KR")}
          <span className="ml-2 text-xs" style={pctStyle(idx.change_pct)}>{pct(idx.change_pct)}</span>
        </div>
        <div className="mt-0.5 flex gap-3 text-[10px] text-[#999]">
          <span>5일 <b style={pctStyle(idx.change_5d)}>{pct(idx.change_5d)}</b></span>
          <span>20일 <b style={pctStyle(idx.change_20d)}>{pct(idx.change_20d)}</b></span>
          <span>20일선대비 <b style={pctStyle(idx.vs_ma20_pct)}>{pct(idx.vs_ma20_pct)}</b></span>
        </div>
      </div>
      <Sparkline data={closes} up={up} />
    </div>
  );
}

function Sheet({ right, children }: { right: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold">개장 예측.xlsx</span>
        {right}
      </div>
      {children}
    </div>
  );
}

export function KrOpenForecast() {
  const [d, setD] = useState<Premarket | null>(null);
  const [hist, setHist] = useState<PremarketHistory | null>(null);
  const [err, setErr] = useState("");
  const [at, setAt] = useState("");
  const first = useRef(true);

  useEffect(() => {
    let alive = true;
    const load = () => {
      api
        .premarket()
        .then((r) => {
          if (!alive) return;
          setD(r);
          setAt(new Date().toLocaleTimeString("ko-KR", { hour12: false }));
        })
        .catch((e) => { if (alive && first.current) setErr(e?.message ?? "개장 예측을 불러오지 못했습니다."); })
        .finally(() => { first.current = false; });
      api.premarketHistory().then((h) => { if (alive) setHist(h); }).catch(() => {});
    };
    load();
    const id = setInterval(load, 120000); // 2분마다 갱신
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (err && !d)
    return <Sheet right={null}><div className="py-20 text-center text-sm text-rose-600">{err}</div></Sheet>;
  if (!d)
    return (
      <Sheet right={null}>
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
          간밤 글로벌·연동 지표 취합 중…
        </div>
      </Sheet>
    );

  const gaugePos = Math.max(0, Math.min(100, 50 + d.gauge / 2));
  const groups = Array.from(new Set(d.signals.map((s) => s.group)));
  const acc = hist?.accuracy;

  return (
    <Sheet right={<span className="text-xs text-white/80">{at && `업데이트 ${at}`}</span>}>
      <div className="max-h-[calc(100vh-190px)] overflow-y-auto p-4">
        {/* ── 결론 배너 ─────────────────────────────── */}
        <div className="mb-4 rounded-md border border-[#e5e5e5] bg-[#fafafa] p-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded px-3 py-1 text-lg font-bold text-white" style={{ background: biasColor(d.bias) }}>
              오늘 개장 {d.bias}
            </span>
            <span className="text-sm text-[#555]">
              예상 개장 갭{" "}
              <b style={pctStyle(d.expected_gap.low)}>{pct(d.expected_gap.low)}</b>
              {" ~ "}
              <b style={pctStyle(d.expected_gap.high)}>{pct(d.expected_gap.high)}</b>
              <span className="ml-2 text-[#999]">(가중 평균 {pct(d.weighted_pct, 2)})</span>
            </span>
            {acc?.rate != null && (
              <span className="ml-auto rounded bg-[#eef4f0] px-2.5 py-1 text-xs font-semibold text-[#217346]">
                누적 적중률 {acc.rate}% ({acc.hits}/{acc.total})
              </span>
            )}
          </div>
          <div className="mt-3">
            <div className="relative h-2.5 w-full rounded-full bg-gradient-to-r from-[#1971c2] via-[#e9e9e9] to-[#c92a2a]">
              <div className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full border-2 border-white bg-[#333] shadow"
                style={{ left: `calc(${gaugePos}% - 8px)` }} />
            </div>
            <div className="mt-1 flex justify-between text-[10px] text-[#999]">
              <span>약세(Risk-off)</span><span>중립</span><span>강세(Risk-on)</span>
            </div>
          </div>
        </div>

        {/* ── 코스피/코스닥 추세 ─────────────────────── */}
        {d.indices?.length > 0 && (
          <div className="mb-4">
            <div className="mb-1 text-xs font-semibold text-[#555]">코스피·코스닥 추세</div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {d.indices.map((i) => <IndexCard key={i.key} idx={i} />)}
            </div>
          </div>
        )}

        {/* ── Claude 서술 시나리오 ─────────────────────── */}
        {d.ai ? (
          <div className="mb-4 rounded-md border border-[#cfe3d6] bg-[#f2f8f4] p-4">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-semibold text-[#217346]">AI 시나리오 · {d.ai.one_liner}</span>
              <span className="text-[10px] text-[#8aa697]">{d.ai.model} · 신뢰도 {d.ai.confidence}</span>
            </div>
            <p className="whitespace-pre-line text-[13px] leading-relaxed text-[#334]">{d.ai.narrative}</p>
            {d.ai.sectors?.length > 0 && (
              <div className="mt-3">
                <div className="mb-1 text-xs font-semibold text-[#555]">주목 섹터·테마</div>
                <div className="flex flex-col gap-1">
                  {d.ai.sectors.map((s, i) => (
                    <div key={i} className="text-[12px] text-[#444]"><b className="text-[#217346]">{s.name}</b> — {s.view}</div>
                  ))}
                </div>
              </div>
            )}
            {d.ai.risks?.length > 0 && (
              <div className="mt-3">
                <div className="mb-1 text-xs font-semibold text-[#555]">개장 후 뒤집을 리스크</div>
                <ul className="list-inside list-disc text-[12px] text-[#a23]">
                  {d.ai.risks.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="mb-4 rounded-md border border-[#e5e5e5] bg-[#fbfbfb] p-3 text-xs text-[#888]">
            {d.ai_error
              ? `AI 서술 층 비활성 — ${d.ai_error}`
              : d.ai_enabled
                ? "AI 서술을 준비 중입니다."
                : "규칙 기반 예측만 표시 중입니다. Claude 서술 시나리오를 쓰려면 백엔드에 ANTHROPIC_API_KEY를 설정하세요."}
          </div>
        )}

        {/* ── 판단 근거 ─────────────────────────────── */}
        <div className="mb-4">
          <div className="mb-1 text-xs font-semibold text-[#555]">판단 근거 (영향 큰 순)</div>
          <ul className="flex flex-col gap-1">
            {d.drivers.map((v, i) => <li key={i} className="text-[12px] text-[#444]">· {v}</li>)}
          </ul>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* ── 간밤 지표 테이블 ─────────────────────── */}
          <div className="rounded-md border border-[#e5e5e5]">
            <div className="border-b border-[#e5e5e5] bg-[#f5f5f5] px-3 py-2 text-xs font-semibold text-[#555]">간밤 글로벌·연동 지표</div>
            {groups.map((g) => (
              <div key={g}>
                <div className="bg-[#fafafa] px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-[#999]">{g}</div>
                {d.signals.filter((s) => s.group === g).map((s) => (
                  <div key={s.key} className="flex items-center justify-between border-t border-[#f0f0f0] px-3 py-1.5 text-[12px]">
                    <span className="text-[#333]">{s.label}</span>
                    <span className="flex items-center gap-3">
                      <span style={pctStyle(s.change_pct)}>{pct(s.change_pct)}</span>
                      <span className="w-24 text-right text-[10px] text-[#999]">우리장 {pct(s.impact_pct)}</span>
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* ── 한국 ADR 테이블 ─────────────────────── */}
          <div className="rounded-md border border-[#e5e5e5]">
            <div className="flex items-center justify-between border-b border-[#e5e5e5] bg-[#f5f5f5] px-3 py-2 text-xs font-semibold text-[#555]">
              <span>미국 상장 한국 ADR (간밤 거래)</span>
              {d.adr_avg != null && <span style={pctStyle(d.adr_avg)}>평균 {pct(d.adr_avg)}</span>}
            </div>
            {d.adrs.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-[#aaa]">ADR 시세를 불러오지 못했습니다.</div>
            ) : (
              d.adrs.map((a) => (
                <div key={a.ticker} className="flex items-center justify-between border-t border-[#f0f0f0] px-3 py-1.5 text-[12px]">
                  <span className="text-[#333]">{a.name} <span className="text-[10px] text-[#aaa]">{a.ticker}</span></span>
                  <span style={pctStyle(a.change_pct)}>{pct(a.change_pct)}</span>
                </div>
              ))
            )}
            <div className="border-t border-[#f0f0f0] px-3 py-2 text-[10px] leading-relaxed text-[#999]">
              ADR은 간밤 미국 시장에서 거래된 한국 기업 주식이라, 오늘 개장 방향의 가장 직접적인 힌트입니다.
            </div>
          </div>
        </div>

        {/* ── 예측 성적표 (예측 vs 실제) ─────────────── */}
        <div className="mt-4 rounded-md border border-[#e5e5e5]">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#e5e5e5] bg-[#f5f5f5] px-3 py-2 text-xs font-semibold text-[#555]">
            <span>예측 성적표 — 매일 예측 vs 실제 개장</span>
            {acc && (
              <span className="text-[11px] font-normal text-[#777]">
                {acc.total > 0
                  ? `누적 ${acc.hits}/${acc.total} 적중 (${acc.rate}%) · 최근 ${acc.recent10_hits}/${acc.recent10_total}`
                  : "채점 대기 중"}
                {acc.pending > 0 && ` · 미채점 ${acc.pending}건`}
              </span>
            )}
          </div>
          {!hist || hist.records.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-[#aaa]">
              아직 기록된 예측이 없습니다. 매 세션 자동으로 예측을 저장하고, 다음 날 실제 개장과 대조해 채점합니다.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-[#eee] bg-[#fafafa] text-left text-[10px] uppercase tracking-wide text-[#999]">
                    <th className="px-3 py-1.5 font-semibold">기준일(종가)</th>
                    <th className="px-3 py-1.5 font-semibold">예측</th>
                    <th className="px-3 py-1.5 font-semibold">실제 개장(코스피/코스닥)</th>
                    <th className="px-3 py-1.5 font-semibold">적중</th>
                    <th className="px-3 py-1.5 font-semibold">이유</th>
                  </tr>
                </thead>
                <tbody>
                  {hist.records.map((r) => (
                    <tr key={r.based_on} className="border-t border-[#f2f2f2] align-top">
                      <td className="whitespace-nowrap px-3 py-1.5 text-[#666]">{r.based_on}</td>
                      <td className="px-3 py-1.5">
                        <span className="font-semibold" style={{ color: biasColor(r.prediction.bias) }}>{r.prediction.bias}</span>
                        <span className="ml-1 text-[10px] text-[#aaa]">{pct(r.prediction.weighted_pct)}</span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-1.5">
                        {r.actual ? (
                          <>
                            <span style={pctStyle(r.actual.kospi_gap)}>{pct(r.actual.kospi_gap)}</span>
                            <span className="mx-1 text-[#ccc]">/</span>
                            <span style={pctStyle(r.actual.kosdaq_gap)}>{pct(r.actual.kosdaq_gap)}</span>
                          </>
                        ) : (
                          <span className="text-[#bbb]">대기</span>
                        )}
                      </td>
                      <td className="px-3 py-1.5">
                        {r.graded ? (
                          <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold text-white ${r.hit ? "bg-[#2f9e44]" : "bg-[#c92a2a]"}`}>
                            {r.hit ? "적중" : "실패"}
                          </span>
                        ) : (
                          <span className="text-[10px] text-[#bbb]">—</span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 text-[11px] leading-relaxed text-[#555]">{r.reason ?? "다음 세션 개장 대기 중"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="mt-3 text-right text-[10px] text-[#bbb]">
          생성 {d.generated_at} · 확정 예언이 아닌 확률적 시나리오이며, 매 세션 자동 기록·채점됩니다.
        </div>
      </div>
    </Sheet>
  );
}
