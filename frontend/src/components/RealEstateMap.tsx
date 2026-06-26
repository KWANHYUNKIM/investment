"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { api, RealEstateMapData, RealEstateRegion, RealEstateDeals } from "@/lib/api";
import { Card, Spinner } from "@/components/ui";

// 지도는 브라우저 전용(leaflet) → SSR 비활성으로 동적 로드
const MapInner = dynamic(() => import("@/components/RealEstateMapInner"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-[#888]">
      <Spinner /> 지도 불러오는 중…
    </div>
  ),
});

export function RealEstateMap() {
  const [data, setData] = useState<RealEstateMapData | null>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<RealEstateRegion | null>(null);
  const [deals, setDeals] = useState<RealEstateDeals | null>(null);
  const [dealsLoading, setDealsLoading] = useState(false);
  const [sido, setSido] = useState<string>("전체");

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      api.realestateMap()
        .then((d) => {
          if (!alive) return;
          setData(d);
          // 아직 수집 중이면 잠시 후 다시(데이터 쌓이면 자동 반영)
          if (!d.ready) timer = setTimeout(load, 15000);
        })
        .catch((e) => alive && setErr(e?.message ?? "지도 데이터를 불러오지 못했습니다."));
    };
    load();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, []);

  function onSelect(r: RealEstateRegion) {
    setSel(r);
    setDeals(null);
    setDealsLoading(true);
    api.realestateDeals(r.lawd, data?.region_ym ?? undefined)
      .then(setDeals)
      .catch(() => setDeals(null))
      .finally(() => setDealsLoading(false));
  }

  const sidos = useMemo(() => {
    if (!data) return [];
    return ["전체", ...Array.from(new Set(data.regions.map((r) => r.sido)))];
  }, [data]);

  const regions = useMemo(() => {
    if (!data) return [];
    return sido === "전체" ? data.regions : data.regions.filter((r) => r.sido === sido);
  }, [data, sido]);

  if (err) return <div className="py-20 text-center text-sm text-rose-600">{err}</div>;
  if (!data) return <div className="flex items-center justify-center gap-2 py-24 text-sm text-[#888]"><Spinner /> 불러오는 중…</div>;

  const subtitle = data.ready
    ? `${data.latest_label} 기준 · 시군구 ${data.count}곳 · 좌표확보 ${data.geocoded}/${data.count}`
    : "데이터 수집 중 — 지도는 먼저 표시됩니다 (채워지면 자동 갱신)";

  return (
    <div className="space-y-4">
      <Card title="부동산 실거래 지도 — 국토부 아파트 매매" subtitle={subtitle}>
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-semibold text-[#555]">시도</span>
          {sidos.map((s) => (
            <button
              key={s}
              onClick={() => setSido(s)}
              className={`rounded border px-2 py-1 text-[11px] font-semibold transition ${
                sido === s ? "border-[#217346] bg-[#217346] text-white" : "border-[#cdcdcd] bg-white text-[#444] hover:bg-[#eef6f0]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_360px]">
          {/* 지도 (데이터 없어도 항상 표시) */}
          <div className="relative h-[600px] w-full overflow-hidden rounded border border-[#e6e6e6]">
            <MapInner regions={regions} selected={sel?.lawd ?? null} onSelect={onSelect} />
            {!data.ready && data.message && (
              <div className="pointer-events-none absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-full border border-[#e0c98a] bg-[#fff8e6]/95 px-4 py-1.5 text-xs font-semibold text-[#8a6d1a] shadow">
                {data.warming && <span className="mr-1 inline-block animate-pulse">●</span>}
                {data.message}
              </div>
            )}
          </div>

          {/* 사이드 패널: 선택 시군구 단지 실거래 */}
          <div className="h-[600px] overflow-y-auto rounded border border-[#e6e6e6] bg-white p-3">
            {!sel ? (
              <div className="flex h-full items-center justify-center px-4 text-center text-xs text-[#999]">
                지도에서 지역(원)을 클릭하면<br />그 시군구의 단지별 실거래가 표시됩니다.
              </div>
            ) : (
              <>
                <div className="mb-2 border-b border-[#eee] pb-2">
                  <div className="text-sm font-bold text-[#333]">{sel.sido} {sel.region}</div>
                  <div className="text-[11px] text-[#888]">
                    {data.latest_label} · 거래 {sel.count}건 · 평균 {sel.avg_eok ?? "—"}억
                    {sel.approx && <span className="text-[#c92a2a]"> · 위치 근사</span>}
                  </div>
                </div>
                {dealsLoading ? (
                  <div className="flex items-center gap-2 py-6 text-xs text-[#888]"><Spinner /> 실거래 불러오는 중…</div>
                ) : !deals || deals.deals.length === 0 ? (
                  <div className="py-6 text-center text-xs text-[#999]">실거래 내역이 없습니다.</div>
                ) : (
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="border-b border-[#eee] text-[#999]">
                        <th className="py-1 text-left font-semibold">단지 / 동</th>
                        <th className="py-1 text-right font-semibold">전용</th>
                        <th className="py-1 text-right font-semibold">거래가</th>
                        <th className="py-1 text-right font-semibold">일자</th>
                      </tr>
                    </thead>
                    <tbody>
                      {deals.deals.map((d, i) => (
                        <tr key={i} className="border-b border-[#f4f4f4]">
                          <td className="py-1 text-left">
                            <span className="font-semibold text-[#333]">{d.apt}</span>
                            <span className="ml-1 text-[#aaa]">{d.dong}</span>
                          </td>
                          <td className="py-1 text-right tabular-nums text-[#666]">{d.area ? `${d.area}㎡` : "—"}</td>
                          <td className="py-1 text-right font-bold tabular-nums text-[#217346]">{d.amount_eok}억</td>
                          <td className="py-1 text-right tabular-nums text-[#999]">{d.date.slice(5)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}
          </div>
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-[#999]">{data.note}</p>
      </Card>
    </div>
  );
}
