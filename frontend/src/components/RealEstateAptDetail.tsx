"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ResponsiveContainer, ComposedChart, Area, Line, Scatter, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from "recharts";
import { api, RealEstateApartmentDetail } from "@/lib/api";
import { Spinner } from "@/components/ui";

type Tab = "price" | "info" | "dong" | "photo";

function ymToX(ym: string, sY: number, sM: number) {
  const [y, m] = ym.split("-").map(Number);
  return (y - sY) * 12 + (m - sM);
}
function xToLabel(x: number, sY: number, sM: number) {
  const t = sY * 12 + (sM - 1) + Math.round(x);
  const y = Math.floor(t / 12);
  const m = (t % 12) + 1;
  return `${String(y).slice(2)}.${String(m).padStart(2, "0")}`;
}

export function RealEstateAptDetail({
  lawd, apt, dong, onClose,
}: {
  lawd: string;
  apt: string;
  dong: string;
  onClose: () => void;
}) {
  const [d, setD] = useState<RealEstateApartmentDetail | null>(null);
  const [tab, setTab] = useState<Tab>("price");
  const [areaKey, setAreaKey] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    setD(null);
    setAreaKey(null);
    const load = () => {
      api.realestateApartment(lawd, apt, dong)
        .then((res) => {
          if (!alive) return;
          setD(res);
          setAreaKey((k) => k ?? (res.areas[0]?.key ?? null));
          if (!res.ready || res.warming) timer.current = setTimeout(load, 5000);
        })
        .catch(() => alive && setD((p) => p));
    };
    load();
    return () => { alive = false; if (timer.current) clearTimeout(timer.current); };
  }, [lawd, apt, dong]);

  const area = useMemo(
    () => d?.areas.find((a) => a.key === areaKey) ?? d?.areas[0] ?? null,
    [d, areaKey],
  );

  const chart = useMemo(() => {
    if (!d || !d.hist_from || !area) return null;
    const sY = +d.hist_from.slice(0, 4);
    const sM = +d.hist_from.slice(4, 6);
    const ser = d.series[area.key] ?? [];
    const line = ser.map((p) => ({ x: ymToX(p.ym, sY, sM), avg: p.avg, band: [p.min, p.max] as [number, number] }));
    const dots = area.deals.map((dl) => {
      const day = Number(dl.date.slice(8, 10)) || 15;
      return { x: ymToX(dl.date.slice(0, 7), sY, sM) + day / 31, eok: dl.eok, date: dl.date, floor: dl.floor };
    });
    const months = d.months ?? 120;
    const ticks: number[] = [];
    for (let x = 0; x <= months; x += 12) ticks.push(x);
    const ys = ser.flatMap((p) => [p.min, p.max]);
    const yMin = ys.length ? Math.min(...ys) : 0;
    const yMax = ys.length ? Math.max(...ys) : 1;
    const pad = (yMax - yMin) * 0.12 || 0.1;
    return { line, dots, ticks, sY, sM, months, yDomain: [Math.max(0, yMin - pad), yMax + pad] as [number, number] };
  }, [d, area]);

  // 거래이력: 계약월 내림차순 그룹
  const history = useMemo(() => {
    if (!area) return [];
    const by: Record<string, typeof area.deals> = {};
    for (const dl of area.deals) {
      const ym = dl.date.slice(0, 7);
      (by[ym] ||= []).push(dl);
    }
    return Object.keys(by)
      .sort((a, b) => (a < b ? 1 : -1))
      .map((ym) => ({
        ym,
        deals: by[ym].slice().sort((a, b) => (a.date < b.date ? 1 : -1)),
      }));
  }, [area]);

  return (
    <div className="fixed inset-0 z-[2000] flex justify-end">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="flex h-full w-full max-w-[480px] flex-col bg-white shadow-2xl">
        {/* 헤더 */}
        <div className="flex items-start justify-between border-b border-[#e6e6e6] px-4 py-3">
          <div>
            <div className="text-base font-bold text-[#222]">{apt}</div>
            <div className="text-[11px] text-[#888]">
              {d?.sido} {d?.region} {dong}
              {d?.build_year ? ` · ${d.build_year}년 건축` : ""}
              {d?.total_deals != null ? ` · 10년 거래 ${d.total_deals}건` : ""}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded px-2 py-1 text-sm text-[#888] hover:bg-[#f0f0f0]"
            aria-label="닫기"
          >
            ✕
          </button>
        </div>

        {/* 탭 */}
        <div className="flex border-b border-[#e6e6e6] text-[13px]">
          {([
            ["price", "시세/실거래"],
            ["info", "단지정보"],
            ["dong", "동호수/공시가격"],
            ["photo", "사진"],
          ] as [Tab, string][]).map(([t, label]) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`-mb-px border-b-2 px-3 py-2 font-semibold transition ${
                tab === t ? "border-[#217346] text-[#217346]" : "border-transparent text-[#888] hover:text-[#555]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 면적 칩 (시세/단지정보 공통) */}
        {d?.ready && d.areas.length > 0 && tab !== "photo" && (
          <div className="flex flex-wrap items-center gap-1.5 border-b border-[#f0f0f0] px-4 py-2">
            {d.areas
              .slice()
              .sort((a, b) => a.area - b.area)
              .map((a) => (
                <button
                  key={a.key}
                  onClick={() => setAreaKey(a.key)}
                  className={`rounded px-2.5 py-1 text-[12px] font-bold transition ${
                    (areaKey ?? d.areas[0].key) === a.key
                      ? "bg-[#217346] text-white"
                      : "bg-[#eef1f0] text-[#555] hover:bg-[#e2e8e5]"
                  }`}
                >
                  {a.area}㎡
                </button>
              ))}
            <span className="ml-auto text-[11px] text-[#aaa]">전용면적</span>
          </div>
        )}

        {/* 본문 */}
        <div className="flex-1 overflow-y-auto">
          {!d ? (
            <div className="flex items-center justify-center gap-2 py-24 text-sm text-[#888]">
              <Spinner /> 단지 정보 불러오는 중…
            </div>
          ) : !d.ready ? (
            <div className="flex flex-col items-center justify-center gap-2 py-24 text-sm text-[#888]">
              <Spinner />
              <div>{d.message ?? "시세·실거래 수집 중…"}</div>
              {d.progress?.total ? (
                <div className="text-[11px] text-[#aaa]">
                  국토부 10년 거래 수집 {d.progress.done}/{d.progress.total}개월
                </div>
              ) : null}
            </div>
          ) : d.areas.length === 0 ? (
            <div className="py-24 text-center text-sm text-[#999]">최근 10년 실거래 내역이 없습니다.</div>
          ) : tab === "price" ? (
            <div className="p-4">
              {/* 요약 */}
              {area && (
                <div className="mb-3 flex items-end gap-3">
                  <div>
                    <div className="text-[11px] text-[#999]">최근 실거래 ({area.recent_date.slice(2)})</div>
                    <div className="text-xl font-extrabold text-[#217346]">{area.recent_eok}억</div>
                  </div>
                  <div className="pb-0.5 text-[12px] text-[#888]">
                    10년 범위 {area.min_eok}~{area.max_eok}억 · {area.count}건
                  </div>
                </div>
              )}
              {/* 차트 */}
              <div className="h-[260px] w-full">
                {chart && (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chart.line} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
                      <CartesianGrid stroke="#f0f0f0" vertical={false} />
                      <XAxis
                        type="number"
                        dataKey="x"
                        domain={[0, chart.months]}
                        ticks={chart.ticks}
                        tickFormatter={(x) => xToLabel(x, chart.sY, chart.sM)}
                        tick={{ fontSize: 10, fill: "#999" }}
                        tickLine={false}
                        axisLine={{ stroke: "#e0e0e0" }}
                      />
                      <YAxis
                        domain={chart.yDomain}
                        tick={{ fontSize: 10, fill: "#999" }}
                        tickFormatter={(v) => `${(+v).toFixed(1)}억`}
                        tickLine={false}
                        axisLine={false}
                        width={46}
                      />
                      <Tooltip
                        formatter={(val, name) => {
                          if (name === "band") {
                            const [lo, hi] = val as unknown as [number, number];
                            return [`${lo}~${hi}억`, "월 범위"];
                          }
                          if (name === "avg") return [`${val}억`, "월 평균"];
                          return [`${val}억`, "실거래"];
                        }}
                        labelFormatter={(x) => xToLabel(Number(x), chart!.sY, chart!.sM)}
                        contentStyle={{ fontSize: 11, borderRadius: 6 }}
                      />
                      <Area
                        type="monotone"
                        dataKey="band"
                        stroke="none"
                        fill="#7fb89a"
                        fillOpacity={0.18}
                        connectNulls
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="avg"
                        stroke="#3f8f6b"
                        strokeWidth={1.6}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                      />
                      <Scatter data={chart.dots} dataKey="eok" fill="#e8590c" fillOpacity={0.85} isAnimationActive={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div className="mt-1 flex items-center gap-3 text-[10px] text-[#999]">
                <span className="flex items-center gap-1"><span className="inline-block h-2 w-3 rounded-sm bg-[#7fb89a]/40" /> 월 범위</span>
                <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-3 bg-[#3f8f6b]" /> 월 평균</span>
                <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-[#e8590c]" /> 실거래</span>
              </div>

              {/* 매매 실거래가 (계약월) */}
              <div className="mt-4">
                <div className="mb-1 text-[12px] font-bold text-[#333]">매매 실거래가 · 국토교통부</div>
                <table className="w-full text-[11px]">
                  <tbody>
                    {history.map((g) => (
                      <tr key={g.ym} className="border-t border-[#f1f1f1] align-top">
                        <td className="w-16 py-1.5 font-semibold text-[#666]">{g.ym.replace("-", ".")}</td>
                        <td className="py-1.5">
                          <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                            {g.deals.map((dl, i) => (
                              <span key={i} className="tabular-nums">
                                <b className="text-[#217346]">{dl.eok}억</b>
                                <span className="text-[#aaa]">
                                  ({dl.date.slice(8, 10)}일{dl.floor ? `,${dl.floor}층` : ""})
                                </span>
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {d.note && <p className="mt-3 text-[10px] leading-relaxed text-[#aaa]">{d.note} · {d.source}</p>}
            </div>
          ) : tab === "info" ? (
            <div className="p-4 text-[12px]">
              {/* 실거래 기반 정보 */}
              <div className="mb-3 grid grid-cols-2 gap-y-1.5">
                <InfoRow k="건축년도" v={d.build_year ? `${d.build_year}년` : "—"} />
                <InfoRow k="법정동" v={dong || "—"} />
                <InfoRow k="전용면적" v={d.areas.map((a) => `${a.area}㎡`).join(", ")} span />
                <InfoRow k="10년 거래" v={`${d.total_deals ?? 0}건`} />
                <InfoRow k="최근 거래일" v={d.last_date ?? "—"} />
              </div>
              {/* 평형별 요약 */}
              <div className="mb-3">
                <div className="mb-1 text-[12px] font-bold text-[#333]">평형별 실거래 요약</div>
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="border-b border-[#eee] text-[#999]">
                      <th className="py-1 text-left">전용</th>
                      <th className="py-1 text-right">최저</th>
                      <th className="py-1 text-right">최고</th>
                      <th className="py-1 text-right">최근</th>
                      <th className="py-1 text-right">건수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.areas.slice().sort((a, b) => a.area - b.area).map((a) => (
                      <tr key={a.key} className="border-b border-[#f4f4f4]">
                        <td className="py-1 font-semibold text-[#333]">{a.area}㎡</td>
                        <td className="py-1 text-right tabular-nums text-[#666]">{a.min_eok}억</td>
                        <td className="py-1 text-right tabular-nums text-[#666]">{a.max_eok}억</td>
                        <td className="py-1 text-right font-bold tabular-nums text-[#217346]">{a.recent_eok}억</td>
                        <td className="py-1 text-right tabular-nums text-[#999]">{a.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* K-apt 미연동 정적정보 */}
              <div className="rounded border border-dashed border-[#d8d8d8] bg-[#fafafa] p-3">
                <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-bold text-[#999]">
                  세대수 · 용적률 · 건설사 등 단지 제원
                  <span className="rounded bg-[#eee] px-1.5 py-0.5 text-[10px] font-semibold text-[#999]">미연동</span>
                </div>
                <p className="text-[11px] leading-relaxed text-[#aaa]">{d.static?.reason}</p>
              </div>
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-1 px-6 text-center text-sm text-[#aaa]">
              <span className="rounded bg-[#eee] px-2 py-0.5 text-[11px] font-semibold text-[#999]">준비중</span>
              <div className="mt-1">
                {tab === "dong" ? "동호수·공시가격은 K-apt/공시가격 API 연동 시 제공됩니다." : "단지 사진은 추후 제공 예정입니다."}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InfoRow({ k, v, span }: { k: string; v: string; span?: boolean }) {
  return (
    <div className={span ? "col-span-2" : ""}>
      <span className="mr-2 text-[#999]">{k}</span>
      <span className="font-semibold text-[#333]">{v}</span>
    </div>
  );
}
