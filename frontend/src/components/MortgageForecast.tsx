"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

function num(s: string): number { return Number((s || "").replace(/,/g, "")) || 0; }
function won(v: number): string { return `${Math.round(v).toLocaleString("ko-KR")}원`; }
function eok(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e8) return `${(v / 1e8).toFixed(a % 1e8 === 0 ? 0 : 1)}억`;
  if (a >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만`;
  return `${Math.round(v).toLocaleString("ko-KR")}`;
}

type Method = "equal_payment" | "equal_principal"; // 원리금균등 / 원금균등

// 월별 상환 시뮬레이션. rateAt(m) = 해당 월의 연이율(%). 금리가 바뀌면(변동금리 재산정)
// 원리금균등은 매월 남은 잔액·잔여개월로 상환액을 다시 계산해 자동 반영한다.
function amortize(P: number, rateAt: (m: number) => number, nMonths: number, method: Method) {
  let bal = P;
  let totalInterest = 0;
  const monthly: number[] = [];
  for (let m = 0; m < nMonths; m++) {
    const r = rateAt(m) / 1200;
    const remaining = nMonths - m;
    const interest = bal * r;
    let principal: number;
    if (method === "equal_payment") {
      const pay = r > 0 ? (bal * r) / (1 - Math.pow(1 + r, -remaining)) : bal / remaining;
      principal = pay - interest;
    } else {
      principal = P / nMonths;
    }
    bal -= principal;
    totalInterest += interest;
    monthly.push(principal + interest);
  }
  return { monthly, totalInterest, totalPaid: P + totalInterest };
}

// 시나리오 금리 경로: applyYear 부터 24개월에 걸쳐 delta(%p) 만큼 서서히 반영 후 유지
function ratePath(base: number, delta: number, applyYear: number) {
  const start = applyYear * 12;
  const ramp = 24;
  return (m: number) => base + delta * Math.min(1, Math.max(0, (m - start) / ramp));
}

const SCENARIOS = [
  { key: "up", label: "인상", color: "#c0392b" },
  { key: "flat", label: "동결", color: "#868e96" },
  { key: "down", label: "인하", color: "#1c6fd6" },
] as const;

export function MortgageForecast() {
  const [amount, setAmount] = useState("300000000");   // 대출금액
  const [rate, setRate] = useState("4.2");             // 현재 주담대 금리(%)
  const [years, setYears] = useState("30");            // 기간(년)
  const [method, setMethod] = useState<Method>("equal_payment");
  const [up, setUp] = useState("1.5");                 // 인상폭(%p)
  const [down, setDown] = useState("1.0");             // 인하폭(%p)
  const [applyYear, setApplyYear] = useState("1");     // 금리변동 시작 시점(년)
  const [ecosRate, setEcosRate] = useState<number | null>(null); // 실시간 주담대 금리(ECOS)
  const rateTouched = useRef(false);

  // 실제 주택담보대출 금리(한국은행 ECOS)를 기본값으로 — 사용자가 아직 안 만졌을 때만 반영
  useEffect(() => {
    api.ecosMacro().then((m) => {
      const ind = m.indicators?.find((i) => i.key === "mortgage_rate");
      const v = ind?.span?.last;
      if (typeof v === "number" && v > 0) {
        setEcosRate(Math.round(v * 100) / 100);
        if (!rateTouched.current) setRate(String(Math.round(v * 100) / 100));
      }
    }).catch(() => {});
  }, []);

  const result = useMemo(() => {
    const P = num(amount);
    const base = Number(rate) || 0;
    const n = (Number(years) || 1) * 12;
    const ay = Number(applyYear) || 0;
    const deltas = { up: Number(up) || 0, flat: 0, down: -(Number(down) || 0) };
    if (P <= 0 || base <= 0) return null;

    const sims = SCENARIOS.map((s) => {
      const d = deltas[s.key];
      const sim = amortize(P, ratePath(base, d, ay), n, method);
      return { ...s, delta: d, ...sim };
    });

    // 연도별 월상환액(각 해 첫 달) — 그래프용
    const chart: Record<string, number>[] = [];
    for (let y = 0; y <= Number(years); y++) {
      const mi = Math.min(n - 1, y * 12);
      const row: Record<string, number> = { year: y };
      sims.forEach((s) => { row[s.key] = Math.round(s.monthly[mi]); });
      chart.push(row);
    }
    const first = Math.round(sims[0].monthly[0]);
    return { sims, chart, first, P, base };
  }, [amount, rate, years, method, up, down, applyYear]);

  const chipCls = "rounded bg-[#eef4f0] px-1.5 py-0.5 text-[10px] text-[#217346] hover:bg-[#d7e8dd]";

  return (
    <Card
      title="모기지(주담대) 금리 시나리오 예측"
      subtitle="기준금리가 오르내리면 내 월상환액·총이자가 어떻게 바뀌는지 — 변동금리 기준"
    >
      {/* 입력 */}
      <div className="grid grid-cols-1 gap-x-5 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-xs text-[#555]">대출금액
          <input value={Number(num(amount)).toLocaleString("ko-KR")}
            onChange={(e) => setAmount(e.target.value.replace(/[^\d]/g, ""))}
            inputMode="numeric"
            className="mt-0.5 block w-full rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-[#217346]" />
          <div className="mt-0.5 flex items-center justify-between">
            <div className="flex gap-1">
              {[["2억", 2e8], ["3억", 3e8], ["5억", 5e8], ["7억", 7e8]].map(([l, v]) => (
                <button key={l as string} type="button" onClick={() => setAmount(String(v))} className={chipCls}>{l}</button>
              ))}
            </div>
            <span className="text-[10px] font-semibold text-[#217346]">= {eok(num(amount))}원</span>
          </div>
        </label>

        <label className="block text-xs text-[#555]">
          <span className="flex items-center justify-between">현재 주담대 금리<b className="tabular-nums text-[#217346]">{rate}%</b></span>
          <input type="range" min={2} max={9} step={0.1} value={Number(rate) || 2}
            onChange={(e) => { rateTouched.current = true; setRate(e.target.value); }} className="mt-1 block w-full accent-[#217346]" />
          {ecosRate != null && (
            <button type="button" onClick={() => { rateTouched.current = true; setRate(String(ecosRate)); }}
              className="mt-0.5 text-[10px] text-[#217346] hover:underline">
              한국은행 실측 주담대 {ecosRate}% 적용 ↺
            </button>
          )}
        </label>

        <label className="block text-xs text-[#555]">
          <span className="flex items-center justify-between">대출기간<b className="tabular-nums text-[#217346]">{years}년</b></span>
          <input type="range" min={5} max={40} step={1} value={Number(years) || 5}
            onChange={(e) => setYears(e.target.value)} className="mt-1 block w-full accent-[#217346]" />
        </label>

        <div className="text-xs text-[#555]">상환방식
          <div className="mt-0.5 flex overflow-hidden rounded border border-[#cdcdcd] text-[12px]">
            {([["equal_payment", "원리금균등"], ["equal_principal", "원금균등"]] as [Method, string][]).map(([m, l]) => (
              <button key={m} onClick={() => setMethod(m)}
                className={`flex-1 py-1 ${method === m ? "bg-[#217346] font-semibold text-white" : "bg-white text-[#555]"}`}>{l}</button>
            ))}
          </div>
        </div>

        <label className="block text-xs text-[#555]">
          <span className="flex items-center justify-between">인상 시 +<b className="tabular-nums text-[#c0392b]">{up}%p</b></span>
          <input type="range" min={0} max={4} step={0.1} value={Number(up) || 0}
            onChange={(e) => setUp(e.target.value)} className="mt-1 block w-full accent-[#c0392b]" />
        </label>

        <label className="block text-xs text-[#555]">
          <span className="flex items-center justify-between">인하 시 −<b className="tabular-nums text-[#1c6fd6]">{down}%p</b> · 반영시점 {applyYear}년</span>
          <input type="range" min={0} max={4} step={0.1} value={Number(down) || 0}
            onChange={(e) => setDown(e.target.value)} className="mt-1 block w-full accent-[#1c6fd6]" />
          <input type="range" min={0} max={Math.max(1, Number(years) - 1)} step={1} value={Number(applyYear) || 0}
            onChange={(e) => setApplyYear(e.target.value)} className="mt-1 block w-full accent-[#868e96]" />
        </label>
      </div>

      {result && (
        <>
          {/* 시나리오 요약 */}
          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
            {result.sims.map((s) => {
              const last = s.monthly[s.monthly.length - 1];
              const peak = Math.max(...s.monthly);
              return (
                <div key={s.key} className="rounded-lg border p-3" style={{ borderColor: s.color + "55", background: s.color + "0d" }}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold" style={{ color: s.color }}>
                      {s.label}{s.delta ? ` (${s.delta > 0 ? "+" : ""}${s.delta}%p)` : ""}
                    </span>
                    <span className="text-[10px] text-[#999]">최종 {(result.base + s.delta).toFixed(1)}%</span>
                  </div>
                  <div className="mt-1.5 flex items-baseline justify-between">
                    <span className="text-[11px] text-[#888]">월상환 시작 → 변동 후</span>
                    <span className="text-sm font-extrabold tabular-nums" style={{ color: s.color }}>
                      {won(result.first)}
                    </span>
                  </div>
                  <div className="text-right text-[11px] tabular-nums text-[#555]">
                    → {method === "equal_payment" ? won(s.delta >= 0 ? peak : last) : won(s.monthly[Math.min(s.monthly.length - 1, Number(applyYear) * 12 + 24)])}
                  </div>
                  <div className="mt-1.5 border-t border-black/5 pt-1.5 text-[11px] text-[#666]">
                    총이자 <b className="tabular-nums" style={{ color: s.color }}>{eok(s.totalInterest)}원</b>
                    <span className="mx-1 text-[#ccc]">·</span>
                    총상환 <b className="tabular-nums text-[#333]">{eok(s.totalPaid)}원</b>
                  </div>
                </div>
              );
            })}
          </div>

          {/* 연도별 월상환액 그래프 */}
          <div className="mt-4">
            <div className="mb-1 text-[12px] font-bold text-[#333]">연도별 월상환액 추이 (시나리오별)</div>
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={result.chart} margin={{ top: 8, right: 12, bottom: 0, left: 6 }}>
                  <CartesianGrid stroke="#f0f0f0" vertical={false} />
                  <XAxis dataKey="year" tick={{ fontSize: 10, fill: "#999" }} tickLine={false}
                    axisLine={{ stroke: "#e0e0e0" }} tickFormatter={(y) => `${y}년`} />
                  <YAxis tick={{ fontSize: 10, fill: "#999" }} tickLine={false} axisLine={false} width={52}
                    tickFormatter={(v) => `${Math.round(Number(v) / 10000)}만`} />
                  <Tooltip
                    formatter={(val, key) => [won(Number(val)), SCENARIOS.find((s) => s.key === key)?.label ?? String(key)]}
                    labelFormatter={(y) => `${y}년차`}
                    contentStyle={{ fontSize: 11, borderRadius: 6 }} />
                  <Legend formatter={(key) => SCENARIOS.find((s) => s.key === key)?.label ?? key} wrapperStyle={{ fontSize: 11 }} />
                  {SCENARIOS.map((s) => (
                    <Line key={s.key} type="monotone" dataKey={s.key} stroke={s.color} strokeWidth={1.8} dot={false} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <p className="mt-3 text-[11px] leading-relaxed text-[#999]">
            변동금리 가정: {applyYear}년 뒤부터 24개월에 걸쳐 금리가 시나리오만큼 조정된 뒤 유지된다고 봅니다.
            원리금균등은 금리가 바뀔 때마다 남은 잔액·기간으로 월상환액을 재산정합니다.
            실제 기준금리·주담대 금리 데이터로 시나리오 기본값을 자동 설정하려면 ECOS(한국은행) 키 연동이 필요합니다.
          </p>
        </>
      )}
    </Card>
  );
}
