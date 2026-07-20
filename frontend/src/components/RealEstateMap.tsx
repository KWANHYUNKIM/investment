"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { api, RealEstateMapData, RealEstateRegion, RealEstateApartments, RealEstateApartment } from "@/lib/api";
import { Card, Spinner } from "@/components/ui";
import { RealEstateAptDetail } from "@/components/RealEstateAptDetail";

// 지도는 브라우저 전용(네이버 지도 JS) → SSR 비활성으로 동적 로드
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
  const [apts, setApts] = useState<RealEstateApartments | null>(null);
  const [aptsLoading, setAptsLoading] = useState(false);
  const [sido, setSido] = useState<string>("전체");
  const [flyTarget, setFlyTarget] = useState<{ lat: number; lng: number; zoom: number } | null>(null);
  const [detail, setDetail] = useState<{ lawd: string; apt: string; dong: string } | null>(null);
  const [query, setQuery] = useState("");
  const aptTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

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

  function loadApts(lawd: string) {
    api.realestateApartments(lawd, data?.region_ym ?? undefined)
      .then((d) => {
        setApts(d);
        setAptsLoading(false);
        // 동 좌표 채우는 중이면 잠시 후 다시 (정밀 좌표로 자동 갱신)
        if (aptTimer.current) clearTimeout(aptTimer.current);
        if (d.geocoding) aptTimer.current = setTimeout(() => loadApts(lawd), 6000);
      })
      .catch(() => {
        setApts(null);
        setAptsLoading(false);
      });
  }

  function onSelect(r: RealEstateRegion) {
    setSel(r);
    setApts(null);
    setAptsLoading(true);
    setFlyTarget({ lat: r.lat, lng: r.lng, zoom: 13 });
    if (aptTimer.current) clearTimeout(aptTimer.current);
    loadApts(r.lawd);
  }

  useEffect(() => () => { if (aptTimer.current) clearTimeout(aptTimer.current); }, []);

  function openDetail(a: RealEstateApartment) {
    setDetail({ lawd: apts?.lawd ?? sel?.lawd ?? "", apt: a.apt, dong: a.dong });
  }

  const sidos = useMemo(() => {
    if (!data) return [];
    return ["전체", ...Array.from(new Set(data.regions.map((r) => r.sido)))];
  }, [data]);

  const regions = useMemo(() => {
    if (!data) return [];
    return sido === "전체" ? data.regions : data.regions.filter((r) => r.sido === sido);
  }, [data, sido]);

  // 검색: 현재 시군구의 단지명 + (지역 미선택 시) 시군구명으로 이동
  const aptMatches = useMemo(() => {
    const q = query.trim();
    if (!q || !apts) return [];
    return apts.apartments.filter((a) => a.apt.includes(q)).slice(0, 8);
  }, [query, apts]);

  const regionMatches = useMemo(() => {
    const q = query.trim();
    if (!q) return [];
    return (data?.regions ?? [])
      .filter((r) => `${r.sido} ${r.region}`.includes(q) || r.region.includes(q))
      .slice(0, 6);
  }, [query, data]);

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

        {/* 검색 */}
        <div className="relative mb-3 max-w-md">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={sel ? `${sel.region} 단지 또는 지역(시군구) 검색…` : "지역(시군구) 검색 — 예: 둔산, 서구"}
            className="w-full rounded border border-[#cdcdcd] px-3 py-1.5 text-[12px] outline-none focus:border-[#217346]"
          />
          {query.trim() && (aptMatches.length > 0 || regionMatches.length > 0) && (
            <div className="absolute z-[1100] mt-1 max-h-72 w-full overflow-y-auto rounded border border-[#ddd] bg-white shadow-lg">
              {aptMatches.length > 0 && (
                <div className="px-2 py-1 text-[10px] font-bold text-[#aaa]">단지 ({sel?.region})</div>
              )}
              {aptMatches.map((a, i) => (
                <button
                  key={`a${i}`}
                  onClick={() => { openDetail(a); setQuery(""); }}
                  className="flex w-full items-center justify-between px-3 py-1.5 text-left text-[12px] hover:bg-[#eef6f0]"
                >
                  <span className="font-semibold text-[#333]">{a.apt}<span className="ml-1 text-[#aaa]">{a.dong}</span></span>
                  <span className="font-bold text-[#217346]">{a.recent_eok}억</span>
                </button>
              ))}
              {regionMatches.length > 0 && (
                <div className="border-t border-[#f0f0f0] px-2 py-1 text-[10px] font-bold text-[#aaa]">지역 이동</div>
              )}
              {regionMatches.map((r, i) => (
                <button
                  key={`r${i}`}
                  onClick={() => { onSelect(r); setSido(r.sido); setQuery(""); }}
                  className="flex w-full items-center justify-between px-3 py-1.5 text-left text-[12px] hover:bg-[#eef6f0]"
                >
                  <span className="text-[#333]">{r.sido} <b>{r.region}</b></span>
                  <span className="text-[#999]">거래 {r.count}건</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_360px]">
          {/* 지도 (데이터 없어도 항상 표시) */}
          <div className="relative h-[600px] w-full overflow-hidden rounded border border-[#e6e6e6]">
            <MapInner
              regions={regions}
              apartments={apts?.lawd === sel?.lawd ? apts?.apartments ?? null : null}
              selected={sel?.lawd ?? null}
              flyTarget={flyTarget}
              onSelect={onSelect}
              onAptDetail={openDetail}
            />
            {!data.ready && data.message && (
              <div className="pointer-events-none absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-full border border-[#e0c98a] bg-[#fff8e6]/95 px-4 py-1.5 text-xs font-semibold text-[#8a6d1a] shadow">
                {data.warming && <span className="mr-1 inline-block animate-pulse">●</span>}
                {data.message}
              </div>
            )}
          </div>

          {/* 사이드 패널: 선택 시군구 실거래 목록 (네이버 부동산 카드 스타일) */}
          <div className="flex h-[600px] flex-col overflow-hidden rounded border border-[#e6e6e6] bg-white">
            {!sel ? (
              <div className="flex h-full items-center justify-center px-4 text-center text-xs text-[#999]">
                지도에서 지역을 클릭하면<br />그 시군구로 확대되며<br />단지별 실거래 목록이 여기에 표시됩니다.
              </div>
            ) : (
              <>
                {/* 헤더 (지역명 + 닫기) */}
                <div className="flex items-start justify-between border-b border-[#eee] px-3.5 py-2.5">
                  <div>
                    <div className="text-[15px] font-bold text-[#222]">{sel.sido} {sel.region}</div>
                    <div className="mt-0.5 text-[11px] text-[#888]">
                      {data.latest_label} 실거래 · 거래 {sel.count}건 · 평균 {sel.avg_eok ?? "—"}억
                      {apts && <> · 단지 {apts.count}곳{apts.geocoding && <span className="text-[#8a6d1a]"> · 위치 보정 중…</span>}</>}
                    </div>
                  </div>
                  <button onClick={() => { setSel(null); setApts(null); }} title="닫기"
                    className="ml-2 shrink-0 rounded p-1 text-lg leading-none text-[#999] hover:bg-[#f2f2f2] hover:text-[#555]">×</button>
                </div>
                {/* 탭 (실거래 목록) */}
                <div className="flex border-b border-[#eee] px-3.5 text-[13px]">
                  <span className="border-b-2 border-[#217346] py-2 font-bold text-[#217346]">실거래 목록</span>
                </div>
                {/* 카드 리스트 */}
                <div className="min-h-0 flex-1 overflow-y-auto bg-[#f7f8f9] p-2.5">
                  {aptsLoading && !apts ? (
                    <div className="flex items-center gap-2 py-6 text-xs text-[#888]"><Spinner /> 단지 실거래 불러오는 중…</div>
                  ) : !apts || apts.apartments.length === 0 ? (
                    <div className="py-6 text-center text-xs text-[#999]">실거래 내역이 없습니다.</div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {apts.apartments.map((a, i) => {
                        const priceLabel = a.min_eok === a.max_eok ? `${a.recent_eok}억` : `${a.min_eok}~${a.max_eok}억`;
                        return (
                          <button
                            key={i}
                            onClick={() => { setFlyTarget({ lat: a.lat, lng: a.lng, zoom: 16 }); openDetail(a); }}
                            className="rounded-lg border border-[#e5e7eb] bg-white px-3 py-2.5 text-left shadow-sm transition hover:border-[#217346] hover:shadow"
                          >
                            <div className="flex items-baseline justify-between gap-2">
                              <span className="truncate text-[13px] font-bold text-[#222]">{a.apt}</span>
                              {a.build_year ? <span className="shrink-0 text-[10px] text-[#aaa]">{a.build_year}년</span> : null}
                            </div>
                            <div className="mt-0.5 text-[15px] font-extrabold tabular-nums text-[#217346]">실거래 {priceLabel}</div>
                            <div className="mt-1 text-[11px] text-[#666]">
                              아파트
                              {a.recent_area ? ` · 전용 ${a.recent_area}㎡` : ""}
                              {a.recent_floor ? ` · ${a.recent_floor}층` : ""}
                              {a.dong ? ` · ${a.dong}` : ""}
                            </div>
                            <div className="mt-1.5 flex items-center gap-1.5">
                              <span className="rounded bg-[#eef6f0] px-1.5 py-0.5 text-[10px] font-semibold text-[#217346]">최근거래</span>
                              <span className="text-[11px] text-[#888]">{a.recent_date || "—"} · 거래 {a.count}건</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-[#999]">
          {data.note}
          {sel && " · 단지 마커 위치는 동 단위 근사 배치(정부 실거래 API가 단지 좌표를 제공하지 않음) — 가격·면적·거래일은 실제값."}
        </p>
      </Card>

      {detail && detail.lawd && (
        <RealEstateAptDetail
          lawd={detail.lawd}
          apt={detail.apt}
          dong={detail.dong}
          onClose={() => setDetail(null)}
        />
      )}
    </div>
  );
}
