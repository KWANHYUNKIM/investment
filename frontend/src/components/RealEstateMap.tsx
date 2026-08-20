"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  api, RealEstateMapData, RealEstateRegion, RealEstateApartments, RealEstateApartment,
  TradeKind, PropertyKind, PropertyKindMeta, MapBounds, PoiSchool, PoiStation,
} from "@/lib/api";
import { Spinner } from "@/components/ui";
import { RealEstateAptDetail } from "@/components/RealEstateAptDetail";
import { FilterBar } from "@/components/RealEstate/FilterBar";
import { ListPanel } from "@/components/RealEstate/ListPanel";
import { DONG_ZOOM, MapLayers } from "@/components/RealEstate/MapCanvas";
import { AreaUnit, TRADE_META, eok } from "@/components/RealEstate/format";
import { useFavs, toggleFav } from "@/components/RealEstate/favs";
import {
  DEFAULT_FILTERS, Filters, SortKey, favKey, passes, sortApartments,
} from "@/components/RealEstate/filters";

// 지도는 브라우저 전용(네이버 지도 JS) → SSR 비활성으로 동적 로드
const MapCanvas = dynamic(() => import("@/components/RealEstate/MapCanvas"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center gap-2 text-sm text-[#888]">
      <Spinner /> 지도 불러오는 중…
    </div>
  ),
});

/** 두 좌표의 거리(도 단위 근사) — 지도 중심에 제일 가까운 시군구를 찾는 데만 쓴다. */
function dist2(a: { lat: number; lng: number }, lat: number, lng: number) {
  const dy = a.lat - lat;
  const dx = (a.lng - lng) * Math.cos((lat * Math.PI) / 180);
  return dy * dy + dx * dx;
}

/** 지도 중심에서 가장 가까운 시군구. 35km 밖이면 "그 지역을 보고 있다"고 보기 어려워 null. */
function nearestRegion(regions: RealEstateRegion[], lat: number, lng: number): RealEstateRegion | null {
  let best: RealEstateRegion | null = null;
  let bestD = Infinity;
  for (const r of regions) {
    const d = dist2(r, lat, lng);
    if (d < bestD) { bestD = d; best = r; }
  }
  return best && bestD <= 0.35 * 0.35 ? best : null;
}

/** URL 쿼리에서 필터를 복원한다(공유 링크로 들어온 경우). */
function filtersFromUrl(base: Filters): Filters {
  const p = new URLSearchParams(window.location.search);
  const next = { ...base };
  const trade = p.get("trade");
  if (trade === "sale" || trade === "jeonse" || trade === "wolse") next.trade = trade;
  if (p.get("pmin")) next.priceMin = Number(p.get("pmin"));
  if (p.get("pmax")) next.priceMax = Number(p.get("pmax"));
  if (p.get("a")) next.areas = p.get("a")!.split(",");
  if (p.get("age")) next.buildAge = p.get("age");
  return next;
}

export function RealEstateMap() {
  const [data, setData] = useState<RealEstateMapData | null>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<RealEstateRegion | null>(null);
  const [apts, setApts] = useState<RealEstateApartments | null>(null);
  const [aptsLoading, setAptsLoading] = useState(false);
  const [flyTarget, setFlyTarget] = useState<{ lat: number; lng: number; zoom: number } | null>(null);
  const [detail, setDetail] = useState<{ lawd: string; apt: string; dong: string } | null>(null);
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [sort, setSort] = useState<SortKey>("price_desc");
  const [areaUnit, setAreaUnit] = useState<AreaUnit>("m2");
  const [selectedApt, setSelectedApt] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [autoSearch, setAutoSearch] = useState(true);
  const [viewport, setViewport] = useState<{ zoom: number; lat: number; lng: number } | null>(null);
  const [kind, setKind] = useState<PropertyKind>("apt");
  const [layers, setLayers] = useState<MapLayers>({ schools: false, stations: false });
  const [schools, setSchools] = useState<PoiSchool[]>([]);
  const [stations, setStations] = useState<PoiStation[]>([]);
  const [poiNote, setPoiNote] = useState("");
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [kinds, setKinds] = useState<PropertyKindMeta[]>([]);
  const favs = useFavs();
  const aptTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // --- 지도 스냅샷(시군구 집계) + URL 복원 -----------------------------------
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let first = true;
    const load = () => {
      api.realestateMap()
        .then((d) => {
          if (!alive) return;
          setData(d);
          if (first) {
            // 공유 링크로 들어왔다면 필터·지역을 복원한다. 첫 응답이 온 뒤라
            // 렌더 중 window 를 읽지 않고, effect 안에서 setState 하지도 않는다.
            first = false;
            const restored = filtersFromUrl(DEFAULT_FILTERS);
            setFilters(restored);
            const lawd = new URLSearchParams(window.location.search).get("lawd");
            const r = lawd ? d.regions.find((x) => x.lawd === lawd) : null;
            if (r) selectRegion(r, restored.trade, "apt", d.region_ym ?? undefined);
          }
          if (!d.ready) timer = setTimeout(load, 15000);   // 수집 중이면 자동 재조회
        })
        .catch((e) => alive && setErr(e?.message ?? "지도 데이터를 불러오지 못했습니다."));
    };
    load();
    return () => { alive = false; if (timer) clearTimeout(timer); };
    // selectRegion 은 렌더마다 새로 만들어지지만 최신 클로저를 쓰므로 의존성에 넣지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 지원 매물 종류(네이버의 매물종류 탭) — 유형별 전월세 제공 여부까지 서버가 알려준다.
  useEffect(() => {
    let alive = true;
    api.realestateKinds()
      .then((d) => alive && setKinds(d.kinds))
      .catch(() => { /* 목록을 못 받으면 탭 없이 아파트만 쓴다 */ });
    return () => { alive = false; };
  }, []);

  // --- 시군구 단지 실거래 ----------------------------------------------------
  // 함수 선언으로 두어 재조회 타이머가 자기 자신을 부를 수 있게 한다.
  function loadApts(lawd: string, trade: TradeKind, k: PropertyKind, ym?: string) {
    setAptsLoading(true);
    api.realestateApartments(lawd, ym, trade, k)
      .then((d) => {
        setApts(d);
        setAptsLoading(false);
        // 동 좌표를 채우는 중이면 잠시 뒤 다시 — 정밀 좌표로 자동 갱신된다.
        if (aptTimer.current) clearTimeout(aptTimer.current);
        if (d.geocoding) aptTimer.current = setTimeout(() => loadApts(lawd, trade, k, ym), 6000);
      })
      .catch(() => { setApts(null); setAptsLoading(false); });
  }

  function selectRegion(r: RealEstateRegion, trade: TradeKind, k: PropertyKind,
                        ym?: string, fly = true) {
    setSel(r);
    setApts(null);
    setSelectedApt(null);
    setPanelOpen(true);
    if (fly) setFlyTarget({ lat: r.lat, lng: r.lng, zoom: 13 });
    if (aptTimer.current) clearTimeout(aptTimer.current);
    loadApts(r.lawd, trade, k, ym);
  }

  const ym = data?.region_ym ?? undefined;

  function pickRegion(r: RealEstateRegion, fly = true) {
    selectRegion(r, filters.trade, kind, ym, fly);
  }

  useEffect(() => () => { if (aptTimer.current) clearTimeout(aptTimer.current); }, []);

  // 거래유형 전환(매매/전세/월세)은 같은 지역을 그 유형으로 다시 받는다.
  function changeFilters(next: Filters) {
    setFilters(next);
    if (next.trade !== filters.trade && sel) {
      setSelectedApt(null);
      loadApts(sel.lawd, next.trade, kind, ym);
    }
  }

  // 매물 종류 전환 — 전월세가 없는 유형이면 매매로 되돌린다.
  function changeKind(k: PropertyKind) {
    const meta = kinds.find((x) => x.key === k);
    const trade: TradeKind = meta && !meta.has_rent ? "sale" : filters.trade;
    setKind(k);
    if (trade !== filters.trade) setFilters({ ...filters, trade });
    setSelectedApt(null);
    if (sel) loadApts(sel.lawd, trade, k, ym);
  }

  // --- 지도 이동 → 자동 재검색 (네이버처럼 확대하면 그 지역이 열린다) -----------
  function onViewport(v: { zoom: number; lat: number; lng: number; bounds: MapBounds }) {
    setViewport(v);
    setBounds(v.bounds);
    if (!autoSearch || !data || v.zoom < DONG_ZOOM) return;
    const best = nearestRegion(data.regions, v.lat, v.lng);
    if (!best || sel?.lawd === best.lawd) return;
    pickRegion(best, false);
  }

  // --- 주변시설(학군·지하철) — 켜져 있을 때만, 화면 범위만 받는다 ----------------
  // 꺼진 레이어는 여기서 비우지 않는다. 지도가 layers 를 보고 안 그리므로 남아 있어도
  // 화면에 안 나오고, 다시 켤 때 이전 결과가 곧바로 보여 깜빡임이 없다.
  useEffect(() => {
    if (!bounds || (!layers.schools && !layers.stations)) return;
    let alive = true;
    const notes: string[] = [];
    const jobs: Promise<void>[] = [];
    if (layers.schools) {
      jobs.push(api.poiSchools(bounds)
        .then((d) => {
          if (!alive) return;
          setSchools(d.items);
          if (!d.available && d.message) notes.push(d.message);
          else if (d.truncated) notes.push(`학교 ${d.count}곳 중 일부만 표시 — 더 확대하세요`);
        })
        .catch(() => { if (alive) setSchools([]); }));
    }
    if (layers.stations) {
      jobs.push(api.poiStations(bounds)
        .then((d) => {
          if (!alive) return;
          setStations(d.items);
          if (!d.available && d.message) notes.push(d.message);
        })
        .catch(() => { if (alive) setStations([]); }));
    }
    Promise.all(jobs).then(() => { if (alive) setPoiNote(notes.join(" · ")); });
    return () => { alive = false; };
  }, [bounds, layers]);

  // --- URL 상태 동기화 (공유 가능한 링크) --------------------------------------
  useEffect(() => {
    const p = new URLSearchParams();
    p.set("trade", filters.trade);
    if (sel) p.set("lawd", sel.lawd);
    if (viewport) p.set("z", String(Math.round(viewport.zoom)));
    if (filters.priceMin != null) p.set("pmin", String(filters.priceMin));
    if (filters.priceMax != null) p.set("pmax", String(filters.priceMax));
    if (filters.areas.length) p.set("a", filters.areas.join(","));
    if (filters.buildAge) p.set("age", filters.buildAge);
    window.history.replaceState(null, "", `${window.location.pathname}?${p.toString()}`);
  }, [filters, sel, viewport]);

  // --- 검색 ------------------------------------------------------------------
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

  // --- 필터·정렬 -------------------------------------------------------------
  const filtered = useMemo(() => {
    if (!apts) return null;
    return sortApartments(apts.apartments.filter((a) => passes(a, filters, favs)), sort);
  }, [apts, filters, favs, sort]);

  const regionsForMap = useMemo(() => data?.regions ?? [], [data]);

  function openDetail(a: RealEstateApartment) {
    setDetail({ lawd: apts?.lawd ?? sel?.lawd ?? "", apt: a.apt, dong: a.dong });
  }

  function pickApt(a: RealEstateApartment) {
    setSelectedApt(favKey(a));
    setFlyTarget({ lat: a.lat, lng: a.lng, zoom: Math.max(viewport?.zoom ?? 15, 15) });
  }

  if (err) return <div className="flex h-full items-center justify-center text-sm text-rose-600">{err}</div>;
  if (!data) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-[#888]">
        <Spinner /> 불러오는 중…
      </div>
    );
  }

  const meta = TRADE_META[filters.trade];
  const showList = !!sel && apts?.lawd === sel.lawd
    && apts?.trade === filters.trade && apts?.kind === kind;

  return (
    /* 지도는 보이는 면적이 곧 정보량이라 사이드바 옆까지 꽉 채운다. 바깥(page.tsx)에서
       1600px 래퍼 밖에 두고, 여기서는 main 높이를 셋으로 나눈다 — 헤더/지도/주석.
       min-h-0 이 없으면 가운데 지도가 내용 높이만큼 부풀어 주석이 화면 밖으로 밀린다. */
    <div className="flex h-full min-h-0 flex-col bg-[#fafafa]">
      {/* 상단 바 — 검색 + 필터 (네이버 부동산 헤더) */}
      <div className="shrink-0 border-b border-[#d0d0d0] bg-white px-3 py-2.5 shadow-sm">
        <div className="mb-2.5 flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1 md:max-w-sm">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={sel ? `${sel.region} 단지 또는 지역 검색…` : "지역·단지 검색 — 예: 둔산동, 래미안"}
              className="w-full rounded-full border border-[#d5d5d5] py-1.5 pl-8 pr-3 text-[12px] outline-none focus:border-[#217346]"
            />
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[12px] text-[#aaa]">⌕</span>
            {query.trim() && (aptMatches.length > 0 || regionMatches.length > 0) && (
              <div className="absolute z-[1300] mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-[#ddd] bg-white shadow-lg">
                {aptMatches.length > 0 && (
                  <div className="px-2 py-1 text-[10px] font-bold text-[#aaa]">단지 ({sel?.region})</div>
                )}
                {aptMatches.map((a) => (
                  <button
                    key={favKey(a)}
                    onClick={() => { pickApt(a); setQuery(""); }}
                    className="flex w-full items-center justify-between px-3 py-1.5 text-left text-[12px] hover:bg-[#f2f7f4]"
                  >
                    <span className="truncate font-semibold text-[#333]">
                      {a.apt}<span className="ml-1 text-[#aaa]">{a.dong}</span>
                    </span>
                    <span className="ml-2 shrink-0 font-bold" style={{ color: meta.color }}>{eok(a.recent_eok)}</span>
                  </button>
                ))}
                {regionMatches.length > 0 && (
                  <div className="border-t border-[#f0f0f0] px-2 py-1 text-[10px] font-bold text-[#aaa]">지역 이동</div>
                )}
                {regionMatches.map((r) => (
                  <button
                    key={r.lawd}
                    onClick={() => { pickRegion(r); setQuery(""); }}
                    className="flex w-full items-center justify-between px-3 py-1.5 text-left text-[12px] hover:bg-[#f2f7f4]"
                  >
                    <span className="text-[#333]">{r.sido} <b>{r.region}</b></span>
                    <span className="ml-2 shrink-0 text-[#999]">거래 {r.count}건</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-[#666]">
            <input
              type="checkbox"
              checked={autoSearch}
              onChange={(e) => setAutoSearch(e.target.checked)}
              className="h-3.5 w-3.5 accent-[#217346]"
            />
            지도 이동 시 자동 검색
          </label>
        </div>

        <FilterBar
          filters={filters}
          onChange={changeFilters}
          areaUnit={areaUnit}
          onAreaUnit={setAreaUnit}
          resultCount={showList && filtered ? filtered.length : null}
          kinds={kinds}
          kind={kind}
          onKind={changeKind}
        />
      </div>

      {/* 지도 + 목록 — 네이버처럼 목록이 지도 위에 얹힌다 */}
      <div className="relative min-h-0 w-full flex-1 overflow-hidden bg-white">
        <MapCanvas
          regions={regionsForMap}
          apartments={showList ? filtered : null}
          selectedLawd={sel?.lawd ?? null}
          selectedApt={selectedApt}
          trade={filters.trade}
          areaUnit={areaUnit}
          favs={favs}
          flyTarget={flyTarget}
          layers={layers}
          onLayers={setLayers}
          schools={schools}
          stations={stations}
          onSelectRegion={(r) => pickRegion(r)}
          onSelectApt={pickApt}
          onAptDetail={openDetail}
          onViewport={onViewport}
        />

        {/* 좌측 목록 패널 (오버레이) */}
        <div
          className={`absolute left-0 top-0 z-[600] h-full overflow-hidden border-r border-[#e0e0e0] bg-white shadow-[2px_0_10px_rgba(0,0,0,.08)] transition-[width] duration-200 ${
            panelOpen ? "w-[330px]" : "w-0 border-r-0"
          }`}
        >
          {panelOpen && (
            <ListPanel
              region={sel}
              apartments={showList ? filtered : null}
              total={apts?.apartments.length ?? 0}
              loading={aptsLoading}
              geocoding={!!apts?.geocoding}
              trade={filters.trade}
              areaUnit={areaUnit}
              sort={sort}
              onSort={setSort}
              favs={favs}
              onToggleFav={(a) => toggleFav(favKey(a))}
              selectedApt={selectedApt}
              onPick={pickApt}
              onDetail={openDetail}
              onClose={() => { setSel(null); setApts(null); setSelectedApt(null); }}
              latestLabel={data.latest_label}
              kindLabel={apts?.kind_label}
              unavailable={apts && apts.available === false ? apts.message : null}
            />
          )}
        </div>

        {/* 패널 접기/펴기 손잡이 */}
        <button
          onClick={() => setPanelOpen((v) => !v)}
          title={panelOpen ? "목록 접기" : "목록 펼치기"}
          style={{ left: panelOpen ? 330 : 0 }}
          className="absolute top-1/2 z-[650] -translate-y-1/2 rounded-r-md border border-l-0 border-[#d5d5d5] bg-white px-1 py-4 text-[11px] text-[#666] shadow-sm transition-[left] duration-200 hover:bg-[#f4f4f4]"
        >
          {panelOpen ? "‹" : "›"}
        </button>

        {/* 수집 중 안내 */}
        {!data.ready && data.message && (
          <div className="pointer-events-none absolute left-1/2 top-3 z-[700] -translate-x-1/2 rounded-full border border-[#e0c98a] bg-[#fff8e6]/95 px-4 py-1.5 text-xs font-semibold text-[#8a6d1a] shadow">
            {data.warming && <span className="mr-1 inline-block animate-pulse">●</span>}
            {data.message}
          </div>
        )}

        {/* 자동 검색을 껐을 때의 수동 버튼 — 네이버의 "이 지역 재검색" */}
        {!autoSearch && viewport && viewport.zoom >= DONG_ZOOM && (
          <button
            onClick={() => {
              const best = nearestRegion(data.regions, viewport.lat, viewport.lng);
              if (best) pickRegion(best, false);
            }}
            className="absolute left-1/2 top-3 z-[700] -translate-x-1/2 rounded-full border border-[#217346] bg-white px-4 py-1.5 text-xs font-bold text-[#217346] shadow hover:bg-[#eef6f0]"
          >
            ↻ 이 지역 재검색
          </button>
        )}
      </div>

      <p className="max-h-16 shrink-0 overflow-y-auto border-t border-[#e5e5e5] bg-white px-3 py-1.5 text-[11px] leading-relaxed text-[#999]">
        {data.ready
          ? `${data.latest_label} 기준 · 시군구 ${data.count}곳 · 좌표확보 ${data.geocoded}/${data.count}`
          : "실거래 수집 중 — 지도는 먼저 표시됩니다."}
        {" · "}
        {data.note}
        {(layers.schools || layers.stations) && poiNote && (
          <><br /><span className="text-[#8a6d1a]">{poiNote}</span></>
        )}
        {" · 매물(호가)은 정부 API에 없어 "}
        <b>실거래</b>
        {"만 보여줍니다. 단지 마커 위치는 동 단위 근사 배치 — 가격·면적·거래일은 실제값."}
      </p>

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
