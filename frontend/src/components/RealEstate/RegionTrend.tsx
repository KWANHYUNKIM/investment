"use client";

// 시군구 월별 추이 — 거래량·평균가·검색 관심도.
//
// 왜 한 화면에 셋을 같이 두는가: **거래는 관심의 결과라 늦다.** 계약서를 쓰기까지
// 몇 주가 걸리므로, 검색이 먼저 오르고 거래가 뒤따르는 시차가 생긴다. 따로 두면
// 그 시차를 눈으로 확인할 방법이 없어서, 거래량 막대 위에 관심도 선을 겹쳐 놓는다.
//
// 축을 둘로 나눈 이유: 거래 건수(수백)와 관심도(배수, 한 자리)는 자릿수가 달라
// 한 축에 얹으면 관심도가 바닥에 붙어 선이 안 보인다.
//
// 평균가는 따로 뗀다. 거래량·관심도와 묻는 질문이 다르고("얼마나 많이" vs "얼마에"),
// 같은 격자에 세 번째 축을 넣으면 읽기가 급격히 나빠진다.

import { useEffect, useState } from "react";
import {
  ResponsiveContainer, ComposedChart, LineChart, Bar, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { api, type RegionSeries } from "@/lib/api";

const GREEN = "#217346";
const ORANGE = "#e8873a";
const BLUE = "#3b7dd8";

export function RegionTrend({ lawd, region }: { lawd: string; region: string }) {
  const [data, setData] = useState<RegionSeries | null>(null);
  const [open, setOpen] = useState(true);

  // lawd 가 바뀌면 호출부가 key 로 갈아끼운다 — 여기서 setData(null) 로 지우면
  // 이펙트 안 동기 setState 가 되어 렌더가 한 번 더 돈다.
  useEffect(() => {
    let alive = true;
    api.realestateRegionSeries(lawd)
      .then((d) => alive && setData(d))
      .catch(() => { /* 추이는 곁들이는 정보 — 없다고 단지 목록을 막지 않는다 */ });
    return () => { alive = false; };
  }, [lawd]);

  if (!data || !data.available || data.months.length < 2) return null;

  const rows = data.months.map((m) => ({
    label: m.label.slice(2),                     // 2026.07 → 26.07
    거래: m.count,
    관심도: m.interest,
    평균가: m.avg_eok,
    provisional: m.provisional,
  }));
  const last = data.months[data.months.length - 1];
  const hasInterest = rows.some((r) => r.관심도 !== null && r.관심도 !== undefined);

  return (
    <div className="border-b border-[#eee] bg-[#fcfcfc] px-3 py-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="mb-1 flex w-full items-center justify-between text-[11px] font-bold text-[#555]"
      >
        <span>
          {region} 추이
          {data.interest && (
            <span className="ml-1.5 font-normal text-[#888]">
              검색 {data.interest.rank}위
              {data.interest.trend_pct !== null && (
                <span style={{ color: data.interest.trend_pct > 0 ? "#c0392b" : BLUE }}>
                  {" "}{data.interest.trend_pct > 0 ? "▲" : "▼"}{Math.abs(Math.round(data.interest.trend_pct))}%
                </span>
              )}
            </span>
          )}
        </span>
        <span className="text-[#aaa]">{open ? "접기" : "펼치기"}</span>
      </button>

      {open && (
        <>
          <div className="mb-0.5 flex items-center gap-2 text-[9px] text-[#999]">
            <span className="flex items-center gap-0.5">
              <span className="inline-block h-2 w-2 rounded-sm" style={{ background: GREEN }} />거래건수
            </span>
            {hasInterest && (
              <span className="flex items-center gap-0.5">
                <span className="inline-block h-0.5 w-3" style={{ background: ORANGE }} />검색 관심도
              </span>
            )}
          </div>

          {/* 거래량 + 관심도 — 선행/후행을 겹쳐 본다 */}
          <div className="h-[92px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} margin={{ top: 4, right: 2, bottom: 0, left: -22 }}>
                <CartesianGrid stroke="#eee" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="l" tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false} width={38} />
                <YAxis yAxisId="r" orientation="right" hide />
                <Tooltip
                  contentStyle={{ fontSize: 11, padding: "4px 8px", borderRadius: 4 }}
                  formatter={(v, name) =>
                    (name === "관심도"
                      ? [`${Number(v ?? 0).toFixed(2)}배`, "검색 관심도"]
                      : [`${v ?? 0}건`, "거래건수"]) as [string, string]}
                />
                <Bar yAxisId="l" dataKey="거래" fill={GREEN} radius={[2, 2, 0, 0]} isAnimationActive={false} />
                {hasInterest && (
                  <Line yAxisId="r" type="monotone" dataKey="관심도" stroke={ORANGE}
                        strokeWidth={1.8} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* 평균 거래가 — 묻는 질문이 달라 따로 뗀다 */}
          <div className="mt-1 flex items-center justify-between text-[9px] text-[#999]">
            <span className="flex items-center gap-0.5">
              <span className="inline-block h-0.5 w-3" style={{ background: BLUE }} />평균 거래가(억)
            </span>
            <span>{last.label} {last.avg_eok ?? "—"}억{last.provisional && " (잠정)"}</span>
          </div>
          <div className="h-[70px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} margin={{ top: 4, right: 2, bottom: 0, left: -22 }}>
                <CartesianGrid stroke="#eee" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false}
                       width={38} domain={["dataMin - 1", "dataMax + 1"]} />
                <Tooltip contentStyle={{ fontSize: 11, padding: "4px 8px", borderRadius: 4 }}
                         formatter={(v) => [`${v ?? "—"}억`, "평균 거래가"] as [string, string]} />
                <Line type="monotone" dataKey="평균가" stroke={BLUE} strokeWidth={1.8}
                      dot={{ r: 2 }} connectNulls isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* 마지막 달이 잠정치라는 걸 숨기지 않는다 — 신고 기한이 남아 늘 낮게 찍힌다. */}
          {last.provisional && (
            <div className="mt-0.5 text-[9px] leading-snug text-[#8a6d1a]">
              {last.label} 은 신고 기한(계약 후 30일)이 남아 있어 잠정치입니다 — 실제보다 적게 보입니다.
            </div>
          )}
        </>
      )}
    </div>
  );
}
