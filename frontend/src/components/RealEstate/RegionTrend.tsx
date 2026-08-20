"use client";

// 시군구 월별 추이 — 거래량·가격·검색 관심도, 거래유형과 평형별로.
//
// 왜 거래량 위에 관심도를 겹치는가: **거래는 관심의 결과라 늦다.** 계약서를 쓰기까지
// 몇 주가 걸리므로 검색이 먼저 오르고 거래가 뒤따른다. 따로 두면 그 시차를 눈으로
// 확인할 방법이 없다. 축을 둘로 나눈 건 거래 건수(수백)와 관심도(배수, 한 자리)가
// 자릿수가 달라 한 축에 얹으면 관심도가 바닥에 붙기 때문이다.
//
// 평형을 고르면 **가격만** 그 평형 것으로 바뀐다. 관심도는 검색어가 '○○구 아파트'
// 하나라 평형별로 나뉘지 않는데, 나뉜 척 보여주면 없는 정밀도를 지어내는 셈이 된다.
//
// 금액의 뜻이 거래유형마다 다르다 — 매매는 거래가, 전세·월세는 보증금. 월세는 보증금과
// 월세가 다른 돈이라 평균 월세를 따로 적는다.

import { useEffect, useState } from "react";
import {
  ResponsiveContainer, ComposedChart, LineChart, Bar, Line,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { api, type RegionSeries, type TradeKind } from "@/lib/api";

const GREEN = "#217346";
const ORANGE = "#e8873a";
const BLUE = "#3b7dd8";

const TRADES: { key: TradeKind; label: string; price: string }[] = [
  { key: "sale", label: "매매", price: "평균 거래가" },
  { key: "jeonse", label: "전세", price: "평균 보증금" },
  { key: "wolse", label: "월세", price: "평균 보증금" },
];

const ALL = "전체";

export function RegionTrend({ lawd, region }: { lawd: string; region: string }) {
  const [trade, setTrade] = useState<TradeKind>("sale");
  const [area, setArea] = useState<string>(ALL);
  const [data, setData] = useState<RegionSeries | null>(null);
  const [open, setOpen] = useState(true);

  // lawd 가 바뀌면 호출부가 key 로 갈아끼운다 — 여기서 setData(null) 로 지우면
  // 이펙트 안 동기 setState 가 되어 렌더가 한 번 더 돈다.
  useEffect(() => {
    let alive = true;
    api.realestateRegionSeries(lawd, trade)
      .then((d) => alive && setData(d))
      .catch(() => { /* 추이는 곁들이는 정보 — 없다고 단지 목록을 막지 않는다 */ });
    return () => { alive = false; };
  }, [lawd, trade]);

  if (!data) return null;

  const meta = TRADES.find((t) => t.key === trade)!;
  const isWolse = trade === "wolse";

  const rows = data.months.map((m) => {
    const bucket = area === ALL ? null : m.by_area?.[area];
    return {
      label: m.label.slice(2),                      // 2026.07 → 26.07
      // 평형을 고르면 건수·가격 모두 그 평형 것으로 본다. 전체 건수와 섞으면
      // '이 평형이 몇 건인가' 에 답이 안 된다.
      거래: area === ALL ? m.count : (bucket?.count ?? 0),
      가격: area === ALL ? m.avg_eok : (bucket?.avg_eok ?? null),
      관심도: m.interest,
      월세: m.avg_rent_manwon,
    };
  });

  const hasInterest = rows.some((r) => r.관심도 !== null && r.관심도 !== undefined);
  const hasPrice = rows.some((r) => r.가격 !== null && r.가격 !== undefined);
  const last = data.months[data.months.length - 1];

  // 이 지역에 실제로 거래가 있는 평형만 고를 수 있게 한다 — 늘 빈 그래프가 나오는
  // 선택지를 남겨 두면 고장으로 읽힌다.
  const buckets = (data.buckets ?? []).filter((b) =>
    data.months.some((m) => (m.by_area?.[b]?.count ?? 0) > 0));

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
          {/* 거래유형 · 평형 */}
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
            <div className="flex overflow-hidden rounded border border-[#d5d5d5]">
              {TRADES.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTrade(t.key)}
                  className={`px-2 py-0.5 text-[10px] font-semibold ${
                    trade === t.key ? "bg-[#217346] text-white" : "bg-white text-[#666] hover:bg-[#f0f0f0]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {buckets.length > 0 && (
              <select
                value={area}
                onChange={(e) => setArea(e.target.value)}
                title="전용면적(㎡)"
                className="rounded border border-[#d5d5d5] bg-white px-1 py-0.5 text-[10px] text-[#555] outline-none"
              >
                <option value={ALL}>전 평형</option>
                {buckets.map((b) => <option key={b} value={b}>{b}㎡</option>)}
              </select>
            )}
          </div>

          {!data.available ? (
            <div className="rounded border border-[#f0e6c9] bg-[#fdfaf0] px-2 py-1.5 text-[10px] leading-relaxed text-[#7a5f10]">
              {data.reason}
            </div>
          ) : (
            <>
              <div className="mb-0.5 flex items-center gap-2 text-[9px] text-[#999]">
                <span className="flex items-center gap-0.5">
                  <span className="inline-block h-2 w-2 rounded-sm" style={{ background: GREEN }} />
                  {meta.label} 거래건수
                </span>
                {hasInterest && (
                  <span className="flex items-center gap-0.5">
                    <span className="inline-block h-0.5 w-3" style={{ background: ORANGE }} />검색 관심도
                  </span>
                )}
                {area !== ALL && <span className="text-[#8a6d1a]">{area}㎡</span>}
              </div>

              {/* 거래량 + 관심도 — 선행/후행을 겹쳐 본다 */}
              <div className="h-[92px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={rows} margin={{ top: 4, right: 2, bottom: 0, left: -22 }}>
                    <CartesianGrid stroke="#eee" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                    <YAxis yAxisId="l" tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false} width={38} />
                    <YAxis yAxisId="r" orientation="right" hide />
                    <Tooltip
                      contentStyle={{ fontSize: 11, padding: "4px 8px", borderRadius: 4 }}
                      formatter={(v, name) =>
                        (name === "관심도"
                          ? [`${Number(v ?? 0).toFixed(2)}배`, "검색 관심도"]
                          : [`${v ?? 0}건`, `${meta.label} 거래`]) as [string, string]}
                    />
                    <Bar yAxisId="l" dataKey="거래" fill={GREEN} radius={[2, 2, 0, 0]} isAnimationActive={false} />
                    {hasInterest && (
                      <Line yAxisId="r" type="monotone" dataKey="관심도" stroke={ORANGE}
                            strokeWidth={1.8} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* 가격 — '얼마나 많이' 와 '얼마에' 는 다른 질문이라 격자를 나눈다 */}
              {hasPrice && (
                <>
                  <div className="mt-1 flex items-center justify-between text-[9px] text-[#999]">
                    <span className="flex items-center gap-0.5">
                      <span className="inline-block h-0.5 w-3" style={{ background: BLUE }} />
                      {meta.price}(억)
                    </span>
                    <span>
                      {last?.label} {(area === ALL ? last?.avg_eok : last?.by_area?.[area]?.avg_eok) ?? "—"}억
                      {isWolse && last?.avg_rent_manwon ? ` · 월세 ${last.avg_rent_manwon}만원` : ""}
                    </span>
                  </div>
                  <div className="h-[70px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={rows} margin={{ top: 4, right: 2, bottom: 0, left: -22 }}>
                        <CartesianGrid stroke="#eee" vertical={false} />
                        <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false}
                               width={38} domain={["dataMin - 1", "dataMax + 1"]} />
                        <Tooltip contentStyle={{ fontSize: 11, padding: "4px 8px", borderRadius: 4 }}
                                 formatter={(v) => [`${v ?? "—"}억`, meta.price] as [string, string]} />
                        <Line type="monotone" dataKey="가격" stroke={BLUE} strokeWidth={1.8}
                              dot={{ r: 2 }} connectNulls isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </>
              )}

              {/* 월세는 보증금만 봐선 알 수 없다 — 월 얼마인지가 실제 부담이다 */}
              {isWolse && rows.some((r) => r.월세) && (
                <>
                  <div className="mt-1 text-[9px] text-[#999]">평균 월세(만원)</div>
                  <div className="h-[56px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={rows} margin={{ top: 4, right: 2, bottom: 0, left: -22 }}>
                        <CartesianGrid stroke="#eee" vertical={false} />
                        <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 9, fill: "#999" }} axisLine={false} tickLine={false} width={38} />
                        <Tooltip contentStyle={{ fontSize: 11, padding: "4px 8px", borderRadius: 4 }}
                                 formatter={(v) => [`${v ?? "—"}만원`, "평균 월세"] as [string, string]} />
                        <Line type="monotone" dataKey="월세" stroke="#c0392b" strokeWidth={1.6}
                              dot={{ r: 2 }} connectNulls isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </>
              )}

              {/* 잠정치와 수집 진행률을 숨기지 않는다 — 모르면 '거래 급감' 으로 오독한다. */}
              <div className="mt-0.5 text-[9px] leading-snug text-[#8a6d1a]">
                {last?.provisional && "최근 2개월은 신고 기한(계약 후 30일)이 남아 잠정치입니다. "}
                {data.coverage && data.coverage.pct < 99 && (
                  <span className="text-[#999]">
                    과거 구간 수집 {data.coverage.pct}% — 시간이 지나면 그래프가 왼쪽으로 길어집니다.
                  </span>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
