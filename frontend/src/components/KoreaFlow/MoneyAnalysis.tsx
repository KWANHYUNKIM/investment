"use client";

import { useEffect, useState } from "react";
import { api, MoneyAnalysis, StructuralCountry, AssetLinkItem, Regime, RealRate } from "@/lib/api";
import { BLUE, RED, gpct, growthColor } from "./shared";

export function MoneyAnalysisSection() {
  const [d, setD] = useState<MoneyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .moneyAnalysis()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#143d28] px-3 py-1.5">
        <span className="text-sm font-bold text-white">통화량 심층분석 — 비교·판단용 파생지표</span>
        <span className="text-[11px] text-white/70">마샬케이·실질통화량·신용 / 돈의 행선지 / 실질금리·침체</span>
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">심층분석 계산 중… <span className="text-[#bbb]">(World Bank·자산시세 취합)</span></div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "심층분석 데이터를 불러오지 못했습니다."}</div>
      ) : (
        <div className="space-y-4 p-3">
          {/* A. 구조지표 — 분모를 붙인 비교 */}
          {d.structural.length > 0 && <StructuralBlock rows={d.structural} />}

          {/* B. 돈의 행선지 */}
          {d.asset_link && (
            <div>
              <div className="mb-1.5 text-xs font-bold text-[#244d1a]">돈의 행선지 — 통화량(M2)이 풀릴 때 어떤 자산이 반응했나</div>
              <p className="mb-2 text-[11px] leading-snug text-[#777]">{d.asset_link.narrative}</p>
              <div className="grid gap-3 sm:grid-cols-3">
                {d.asset_link.assets.map((a) => (
                  <AssetLinkCard key={a.key} a={a} />
                ))}
              </div>
              <p className="mt-1 text-[10px] text-[#aaa]">점선=한국 M2 · 실선=자산 (둘 다 시작연도=100 지수). 상관계수는 연 증가율 기준.</p>
            </div>
          )}

          {/* C. 레짐 — 실질금리·침체 */}
          {d.regime && <RegimeBlock r={d.regime} />}

          <p className="text-[10px] leading-tight text-[#aaa]">{d.note}</p>
          <p className="text-[10px] text-[#bbb]">출처: {d.source}</p>
        </div>
      )}
    </section>
  );
}

// 현재값을 평균 대비로 색칠 (높음=빨강=유동성 과다, 낮음=파랑)
export function vsAvgColor(latest: number | null, avg: number | null | undefined): string {
  if (latest == null || avg == null) return "#333";
  if (latest > avg * 1.05) return RED;
  if (latest < avg * 0.95) return BLUE;
  return "#333";
}

export function Sparkline({ pts, color }: { pts: number[]; color: string }) {
  if (pts.length < 2) return null;
  const w = 120, h = 30, pad = 2;
  const min = Math.min(...pts), max = Math.max(...pts);
  const span = max - min || 1;
  const xs = (i: number) => pad + (i / (pts.length - 1)) * (w - 2 * pad);
  const ys = (v: number) => h - pad - ((v - min) / span) * (h - 2 * pad);
  const dPath = pts.map((v, i) => `${i === 0 ? "M" : "L"}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <path d={dPath} fill="none" stroke={color} strokeWidth={1.5} />
      <circle cx={xs(pts.length - 1)} cy={ys(pts[pts.length - 1])} r={2} fill={color} />
    </svg>
  );
}

// 두 시계열(M2 vs 자산, 둘 다 지수 100 기준)을 한 칸에 겹쳐 그림
export function DualSpark({ a, b, colorA, colorB }: { a: number[]; b: number[]; colorA: string; colorB: string }) {
  const all = [...a, ...b];
  if (all.length < 2) return null;
  const w = 150, h = 44, pad = 3;
  const min = Math.min(...all), max = Math.max(...all);
  const span = max - min || 1;
  const path = (pts: number[]) => {
    const xs = (i: number) => pad + (i / (pts.length - 1)) * (w - 2 * pad);
    const ys = (val: number) => h - pad - ((val - min) / span) * (h - 2 * pad);
    return pts.map((val, i) => `${i === 0 ? "M" : "L"}${xs(i).toFixed(1)},${ys(val).toFixed(1)}`).join(" ");
  };
  return (
    <svg width={w} height={h} className="overflow-visible">
      <path d={path(a)} fill="none" stroke={colorA} strokeWidth={1.3} strokeDasharray="3 2" />
      <path d={path(b)} fill="none" stroke={colorB} strokeWidth={1.6} />
    </svg>
  );
}

export function StructuralBlock({ rows }: { rows: StructuralCountry[] }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-bold text-[#244d1a]">구조지표 — 통화량에 ‘분모’를 붙여 비교 (World Bank, 연)</div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr className="bg-[#f0f0f0] text-[11px] text-[#444]">
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-left font-semibold">국가</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">마샬케이 M2/GDP<div className="font-normal text-[#999]">경제규모 대비 통화량</div></th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">유통속도 GDP/M2<div className="font-normal text-[#999]">돈이 도는 속도</div></th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">실질 통화량<div className="font-normal text-[#999]">명목−물가</div></th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">민간신용/GDP<div className="font-normal text-[#999]">레버리지</div></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.iso} className={c.iso === "KOR" ? "bg-[#f1f8f3]" : "hover:bg-[#fafafa]"}>
                <td className="border border-[#e6e6e6] px-2 py-1.5 font-bold text-[#1f1f1f]">{c.name}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <div className="text-right">
                      <div className="font-bold tabular-nums" style={{ color: vsAvgColor(c.marshall_k.latest, c.marshall_k.avg) }}>{c.marshall_k.latest}%</div>
                      <div className="text-[10px] text-[#999]">평균 {c.marshall_k.avg}% · {c.marshall_k.trend}</div>
                    </div>
                    <Sparkline pts={c.marshall_k.series.map((p) => p.v)} color={vsAvgColor(c.marshall_k.latest, c.marshall_k.avg)} />
                  </div>
                </td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums">
                  <div className="font-bold text-[#333]">{c.velocity.latest}</div>
                  <div className="text-[10px] text-[#999]">{c.velocity.trend}</div>
                </td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums">
                  <span className="font-bold" style={{ color: growthColor(c.real_m2.latest) }}>{gpct(c.real_m2.latest)}</span>
                  <div className="text-[10px] text-[#999]">{c.real_m2.latest_year}</div>
                </td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums">
                  <span className="font-bold text-[#333]">{c.credit_gdp.latest}%</span>
                  <div className="text-[10px] text-[#999]">평균 {c.credit_gdp.avg}%</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-[10px] leading-tight text-[#aaa]">
        마샬케이가 장기평균보다 높고 ‘상승’이면 경제규모 대비 돈이 과하게 풀린 상태(빨강). 유통속도가 낮아지면 푼 돈이 실물보다 자산에 고인다는 뜻. 실질 통화량이 −면 물가가 명목 증가를 갉아먹는 중.
      </p>
    </div>
  );
}

export function AssetLinkCard({ a }: { a: AssetLinkItem }) {
  const color = a.outpaced === "asset" ? RED : BLUE;
  return (
    <div className="rounded-lg border border-[#e0e0e0] bg-white p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-[#222]">{a.label}</span>
        <span className="text-[10px] text-[#aaa]">{a.from}~{a.to}</span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <DualSpark a={a.m2_series.map((p) => p.v)} b={a.series.map((p) => p.v)} colorA="#999" colorB={color} />
        {a.corr != null && (
          <div className="text-right">
            <div className="text-[10px] text-[#999]">M2 상관</div>
            <div className="text-base font-bold tabular-nums" style={{ color: a.corr > 0.3 ? RED : a.corr < -0.3 ? BLUE : "#666" }}>
              {a.corr > 0 ? "+" : ""}{a.corr}
            </div>
          </div>
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[11px]">
        <span className="text-[#666]">자산 <span className="font-bold" style={{ color: RED }}>{gpct(a.asset_total_ret)}</span></span>
        <span className="text-[#666]">M2 <span className="font-bold text-[#888]">{gpct(a.m2_total_ret)}</span></span>
      </div>
      <p className="mt-1 text-[10px] leading-tight text-[#999]">
        {a.outpaced === "asset" ? "통화 증가폭보다 더 올라 ‘돈의 행선지’ 신호" : "통화 증가폭에 못 미침"}
      </p>
    </div>
  );
}

export function RegimeBlock({ r }: { r: Regime }) {
  const rateCard = (label: string, x: RealRate | null) => {
    if (!x) return null;
    const stance = x.real > 0.5 ? "긴축" : x.real < -0.5 ? "완화" : "중립";
    const col = x.real > 0.5 ? BLUE : x.real < -0.5 ? RED : "#666"; // 완화(돈풀기)=빨강
    return (
      <div className="rounded border border-[#e6e6e6] bg-white p-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[#333]">{label} 실질금리</span>
          <span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: col }}>{stance}</span>
        </div>
        <div className="mt-1 text-lg font-bold tabular-nums" style={{ color: col }}>{x.real > 0 ? "+" : ""}{x.real}%p</div>
        <div className="text-[10px] text-[#999]">정책 {x.policy}% − 물가 {x.inflation ?? "—"}% <span className="text-[#bbb]">({x.period})</span></div>
      </div>
    );
  };
  return (
    <div>
      <div className="mb-1.5 text-xs font-bold text-[#244d1a]">레짐 — 실질금리(돈줄 방향)와 경기침체(NBER)</div>
      <div className="grid gap-2 sm:grid-cols-2">
        {rateCard("한국", r.kr)}
        {rateCard("미국", r.us)}
      </div>
      {r.recessions.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-[#888]">미국 침체기:</span>
          {r.recessions.map((s, i) => (
            <span key={i} className="rounded bg-[#eef0ef] px-1.5 py-0.5 text-[10px] tabular-nums text-[#555]">{s.start}~{s.end}</span>
          ))}
          <span className="ml-1 rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: r.us_recession_now ? RED : "#3a9d5d" }}>
            현재 {r.us_recession_now ? "침체" : "확장"}
          </span>
        </div>
      )}
      {r.narrative && <p className="mt-1.5 text-[11px] leading-snug text-[#666]">{r.narrative}</p>}
    </div>
  );
}
