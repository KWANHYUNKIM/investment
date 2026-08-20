"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type {
  MapBounds, PoiSchool, PoiStation, RealEstateApartment, RealEstateRegion, TradeKind,
} from "@/lib/api";
import { TRADE_META, area as fmtArea, eokShort, headlinePrice, AreaUnit } from "./format";
import { favKey } from "./filters";

// 네이버 클라우드 플랫폼 Maps 인증키(ncpKeyId). .env.local 에 넣는다.
const CLIENT_ID = process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID || "";

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    naver?: any;
    navermap_authFailure?: () => void;
  }
}

// 마커 단계 — 네이버 부동산과 같은 전환점.
//   ~11  시군구 버블 / 12~13 읍면동 버블 / 14~ 단지 알약
export const DONG_ZOOM = 12;
export const APT_ZOOM = 14;

export type MapKind = "normal" | "satellite" | "terrain";

// 네이버 지도 스크립트를 한 번만 로드 (SSR 없음 — 이 컴포넌트는 dynamic ssr:false)
let _loadPromise: Promise<void> | null = null;
function loadNaver(): Promise<void> {
  if (typeof window !== "undefined" && window.naver?.maps) return Promise.resolve();
  if (_loadPromise) return _loadPromise;
  _loadPromise = new Promise<void>((resolve, reject) => {
    if (!CLIENT_ID) { reject(new Error("no-key")); return; }
    const s = document.createElement("script");
    s.type = "text/javascript";
    // panorama 서브모듈을 함께 받아 거리뷰를 띄운다(네이버 부동산의 거리뷰와 같은 것).
    s.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${encodeURIComponent(CLIENT_ID)}&submodules=panorama`;
    s.async = true;
    s.onload = () => (window.naver?.maps ? resolve() : reject(new Error("load-fail")));
    s.onerror = () => reject(new Error("load-fail"));
    document.head.appendChild(s);
  });
  return _loadPromise;
}

/** 단지 알약 — 네이버는 단지명과 가격을 함께 얹는다. */
function aptPill(
  a: RealEstateApartment, trade: TradeKind, unit: AreaUnit, selected: boolean, fav: boolean,
): string {
  const meta = TRADE_META[trade];
  const areaTxt = a.recent_area ? fmtArea(a.recent_area, unit) : "";
  const border = selected ? `2px solid ${meta.color}` : "1px solid #e2e2e2";
  const bg = selected ? meta.soft : "#fff";
  const name = a.apt.length > 9 ? `${a.apt.slice(0, 8)}…` : a.apt;
  return `
    <div style="position:relative;transform:translate(-50%,-100%);cursor:pointer;">
      <div style="background:${bg};border:${border};border-radius:9px;padding:3px 9px 4px;
                  font-family:inherit;line-height:1.2;white-space:nowrap;text-align:center;
                  box-shadow:0 2px 6px rgba(0,0,0,.18);">
        ${fav ? '<span style="position:absolute;top:-6px;right:-5px;font-size:11px;color:#f0a500;">★</span>' : ""}
        <div style="font-size:11px;font-weight:700;color:#333;">${name}</div>
        <div style="font-size:13px;font-weight:800;color:${meta.color};">${headlinePrice(a, trade)}</div>
        ${areaTxt ? `<div style="font-size:9px;color:#9a9a9a;font-weight:600;">${areaTxt}</div>` : ""}
      </div>
      <div style="position:absolute;left:50%;top:100%;margin-top:-1px;transform:translateX(-50%);width:0;height:0;
                  border-left:6px solid transparent;border-right:6px solid transparent;
                  border-top:7px solid ${bg};filter:drop-shadow(0 2px 1px rgba(0,0,0,.12));"></div>
    </div>`;
}

/** 읍면동 집계 버블 — 네이버의 중간 줌 단계. 동명 + 단지수 + 평균가. */
function dongBubble(d: DongAgg, trade: TradeKind): string {
  const meta = TRADE_META[trade];
  return `
    <div style="transform:translate(-50%,-50%);cursor:pointer;
                background:#fff;border:1px solid #e2e2e2;border-radius:999px;
                padding:5px 11px;font-family:inherit;line-height:1.2;white-space:nowrap;
                text-align:center;box-shadow:0 2px 7px rgba(0,0,0,.17);">
      <div style="font-size:11px;font-weight:800;color:#2a2a2a;">${d.dong}</div>
      <div style="font-size:11px;font-weight:800;color:${meta.color};">${eokShort(d.avg)}</div>
      <div style="font-size:9px;color:#9a9a9a;">${d.count}개 단지</div>
    </div>`;
}

/** 시군구 집계 버블 */
// 검색 관심도 — 네이버 부동산이 인기 지역을 눈에 띄게 하듯, 마커 자체가 열기를 말하게 한다.
// 목록을 따로 열어 보지 않아도 지도를 훑는 것만으로 '어디가 뜨나' 가 보여야 한다.
export interface HeatItem { rank: number; index: number; trend_pct: number | null }
export type HeatMap = Record<string, HeatItem>;

// 상위권만 색으로 구분한다. 181곳을 전부 물들이면 지도가 색칠공부가 되고, 정작
// 어디가 위인지 안 보인다.
function heatStyle(rank: number): { bg: string; fg: string; label: string } | null {
  if (rank <= 3) return { bg: "#c0392b", fg: "#fff", label: `관심 ${rank}위` };
  if (rank <= 10) return { bg: "#e8873a", fg: "#fff", label: `관심 ${rank}위` };
  if (rank <= 30) return { bg: "#f0c419", fg: "#4a3b00", label: `관심 ${rank}위` };
  return null;
}

function regionBubble(r: RealEstateRegion, selected: boolean, trade: TradeKind,
                      heat?: HeatItem): string {
  const meta = TRADE_META[trade];
  const hs = heat ? heatStyle(heat.rank) : null;
  const trend = heat?.trend_pct;
  const title = `${r.sido} ${r.region}${r.approx ? " (근사)" : ""} · 거래 ${r.count}건 · 평균 ${r.avg_eok ?? "—"}억`
    + (heat ? ` · 검색 관심도 ${heat.rank}위(${heat.index.toFixed(2)}배)` : "");

  // 상위권 배지 — 마커 위에 얹어 지도를 훑을 때 먼저 눈에 걸리게 한다.
  const badge = hs
    ? `<div style="position:absolute;top:-9px;left:50%;transform:translateX(-50%);
                   background:${hs.bg};color:${hs.fg};font-size:9px;font-weight:800;
                   border-radius:7px;padding:1px 5px;white-space:nowrap;
                   box-shadow:0 1px 3px rgba(0,0,0,.25);">${hs.label}</div>`
    : "";

  // 상승 중인 곳은 삼각형 하나로 표시한다. 순위는 '지금 크다', 추세는 '커지는 중'
  // 이라 둘이 다른 말을 하므로 같이 보여야 판단이 된다.
  const arrow = trend !== null && trend !== undefined && Math.abs(trend) >= 10
    ? `<span style="color:${trend > 0 ? "#c0392b" : "#3b7dd8"};font-size:9px;font-weight:800;">
         ${trend > 0 ? "▲" : "▼"}${Math.abs(Math.round(trend))}%</span>`
    : "";

  return `
    <div title="${title.replace(/"/g, "&quot;")}"
         style="position:relative;transform:translate(-50%,-50%);cursor:pointer;
                background:${selected ? meta.color : "#fff"};
                border:${selected ? `2px solid ${meta.color}` : hs ? `1.5px solid ${hs.bg}` : "1px solid #e2e2e2"};
                border-radius:10px;padding:3px 9px 4px;font-family:inherit;line-height:1.2;
                white-space:nowrap;text-align:center;box-shadow:0 2px 6px rgba(0,0,0,.16);">
      ${badge}
      <div style="font-size:11px;font-weight:800;color:${selected ? "#fff" : "#2a2a2a"};">${r.region} ${arrow}</div>
      <div style="font-size:10px;font-weight:700;color:${selected ? "#fff" : meta.color};">거래 ${r.count}건</div>
      <div style="font-size:10px;color:${selected ? "rgba(255,255,255,.85)" : "#8a8a8a"};">평균 ${r.avg_eok ?? "—"}억</div>
    </div>`;
}

interface DongAgg { dong: string; lat: number; lng: number; count: number; avg: number }

/** 단지 목록을 읍면동으로 접는다 — 중간 줌에서 마커가 뭉개지지 않게. */
function foldByDong(list: RealEstateApartment[]): DongAgg[] {
  const acc = new Map<string, { lat: number; lng: number; n: number; sum: number }>();
  for (const a of list) {
    const k = a.dong || "기타";
    const cur = acc.get(k) ?? { lat: 0, lng: 0, n: 0, sum: 0 };
    cur.lat += a.lat; cur.lng += a.lng; cur.n += 1; cur.sum += a.recent_eok;
    acc.set(k, cur);
  }
  return [...acc.entries()].map(([dong, v]) => ({
    dong, lat: v.lat / v.n, lng: v.lng / v.n, count: v.n, avg: v.sum / v.n,
  }));
}

// 학교 마커 — 학교급별 색(네이버 학군 레이어와 같은 위계: 초 파랑/중 초록/고 주황)
const SCHOOL_COLOR: Record<string, string> = {
  초등학교: "#2f6fed", 중학교: "#1f9d55", 고등학교: "#e8590c", 특수학교: "#7048e8",
};

function schoolPin(s: PoiSchool): string {
  const c = SCHOOL_COLOR[s.level] ?? "#666";
  return `
    <div title="${s.name.replace(/"/g, "&quot;")} · ${s.addr.replace(/"/g, "&quot;")}"
         style="transform:translate(-50%,-50%);cursor:default;display:flex;align-items:center;gap:3px;
                background:#fff;border:1px solid ${c};border-radius:999px;padding:1px 6px 1px 2px;
                box-shadow:0 1px 4px rgba(0,0,0,.18);white-space:nowrap;">
      <span style="display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;
                   border-radius:50%;background:${c};color:#fff;font-size:9px;font-weight:800;">${s.kind}</span>
      <span style="font-size:10px;font-weight:700;color:#444;">${s.name.replace(/(초등학교|중학교|고등학교)$/, "")}</span>
    </div>`;
}

function stationPin(t: PoiStation): string {
  const c = t.transfer ? "#d9480f" : "#0b7285";
  return `
    <div title="${t.name.replace(/"/g, "&quot;")} · ${t.lines.join(", ").replace(/"/g, "&quot;")}"
         style="transform:translate(-50%,-50%);cursor:default;display:flex;align-items:center;gap:3px;
                background:#fff;border:1px solid ${c};border-radius:999px;padding:1px 6px 1px 2px;
                box-shadow:0 1px 4px rgba(0,0,0,.18);white-space:nowrap;">
      <span style="display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;
                   border-radius:50%;background:${c};color:#fff;font-size:9px;font-weight:800;">${t.transfer ? "환" : "역"}</span>
      <span style="font-size:10px;font-weight:700;color:#444;">${t.name}</span>
    </div>`;
}

export interface MapLayers { schools: boolean; stations: boolean }

const MAP_KINDS: { key: MapKind; label: string }[] = [
  { key: "normal", label: "일반" },
  { key: "satellite", label: "위성" },
  { key: "terrain", label: "지형" },
];

export default function MapCanvas({
  regions, apartments, selectedLawd, selectedApt, trade, areaUnit, favs,
  flyTarget, layers, onLayers, schools, stations, heat,
  onSelectRegion, onSelectApt, onAptDetail, onViewport,
}: {
  regions: RealEstateRegion[];
  heat?: HeatMap;            // lawd → 검색 관심도(없으면 마커는 지금 모습 그대로)
  apartments: RealEstateApartment[] | null;
  selectedLawd: string | null;
  selectedApt: string | null;      // favKey
  trade: TradeKind;
  areaUnit: AreaUnit;
  favs: ReadonlySet<string>;
  flyTarget: { lat: number; lng: number; zoom: number } | null;
  layers: MapLayers;
  onLayers: (l: MapLayers) => void;
  schools: PoiSchool[];
  stations: PoiStation[];
  onSelectRegion: (r: RealEstateRegion) => void;
  onSelectApt: (a: RealEstateApartment) => void;
  onAptDetail: (a: RealEstateApartment) => void;
  onViewport: (v: { zoom: number; lat: number; lng: number; bounds: MapBounds }) => void;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const panoElRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const panoRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const poiRef = useRef<any[]>([]);
  const cadastralRef = useRef<any>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "no-key" | "auth-fail" | "load-fail">(
    CLIENT_ID ? "loading" : "no-key",
  );
  const [zoom, setZoom] = useState(7);
  const [mapKind, setMapKind] = useState<MapKind>("normal");
  const [cadastral, setCadastral] = useState(false);
  const [street, setStreet] = useState(false);
  const [streetErr, setStreetErr] = useState("");

  // 콜백이 매 렌더 최신값을 보도록 ref 로 보관 (마커 이벤트 클로저용)
  const cbRef = useRef({ onSelectRegion, onSelectApt, onAptDetail, onViewport });
  useEffect(() => { cbRef.current = { onSelectRegion, onSelectApt, onAptDetail, onViewport }; });

  const dongs = useMemo(() => (apartments ? foldByDong(apartments) : []), [apartments]);

  // 1) 지도 최초 생성
  useEffect(() => {
    if (!CLIENT_ID) return;
    let alive = true;
    window.navermap_authFailure = () => alive && setStatus("auth-fail");
    loadNaver()
      .then(() => {
        if (!alive || !elRef.current) return;
        const naver = window.naver;
        const map = new naver.maps.Map(elRef.current, {
          center: new naver.maps.LatLng(36.4, 127.9),
          zoom: 7,
          scaleControl: false,
          logoControl: true,
          mapDataControl: false,
          zoomControl: false,   // 우리 컨트롤을 오른쪽에 직접 얹는다
        });
        mapRef.current = map;
        // 지도를 멈춰 세울 때마다(idle) 뷰포트를 부모에 알린다 — 네이버처럼
        // 줌을 당기면 그 지역 단지가 자동으로 불려온다.
        naver.maps.Event.addListener(map, "idle", () => {
          const c = map.getCenter();
          const z = map.getZoom();
          const b = map.getBounds();
          const sw = b.getSW();
          const ne = b.getNE();
          setZoom(z);
          cbRef.current.onViewport({
            zoom: z, lat: c.lat(), lng: c.lng(),
            bounds: { swLat: sw.lat(), swLng: sw.lng(), neLat: ne.lat(), neLng: ne.lng() },
          });
        });
        setStatus("ready");
      })
      .catch((e) => alive && setStatus(e?.message === "no-key" ? "no-key" : "load-fail"));
    return () => { alive = false; };
  }, []);

  // 2) flyTarget → 부드럽게 이동
  useEffect(() => {
    if (status !== "ready" || !flyTarget) return;
    const naver = window.naver;
    mapRef.current?.morph(new naver.maps.LatLng(flyTarget.lat, flyTarget.lng), flyTarget.zoom);
  }, [flyTarget, status]);

  // 3) 지도 유형 / 지적편집도
  useEffect(() => {
    if (status !== "ready") return;
    const naver = window.naver;
    const id = mapKind === "satellite" ? naver.maps.MapTypeId.HYBRID
      : mapKind === "terrain" ? naver.maps.MapTypeId.TERRAIN
      : naver.maps.MapTypeId.NORMAL;
    mapRef.current?.setMapTypeId(id);
  }, [mapKind, status]);

  useEffect(() => {
    if (status !== "ready") return;
    const naver = window.naver;
    if (!cadastralRef.current) cadastralRef.current = new naver.maps.CadastralLayer();
    cadastralRef.current.setMap(cadastral ? mapRef.current : null);
  }, [cadastral, status]);

  // 4) 거리뷰 — 지도 중심의 파노라마를 오른쪽 아래 창에 띄운다.
  useEffect(() => {
    if (status !== "ready") return;
    const naver = window.naver;
    if (!street) {
      panoRef.current?.setVisible?.(false);
      return;
    }
    if (!panoElRef.current || !naver.maps.Panorama) return;
    const c = mapRef.current.getCenter();
    if (!panoRef.current) {
      panoRef.current = new naver.maps.Panorama(panoElRef.current, {
        position: c, pov: { pan: 0, tilt: 0, fov: 100 }, logoControl: true,
      });
      naver.maps.Event.addListener(panoRef.current, "pano_status", (st: string) => {
        setStreetErr(st === "OK" ? "" : "이 위치에는 거리뷰가 없습니다 — 도로 쪽으로 옮겨 보세요.");
      });
    } else {
      panoRef.current.setVisible(true);
      panoRef.current.setPosition(c);
    }
  }, [street, status, flyTarget]);

  // 5) 마커 다시 그리기 — 줌 단계에 따라 시군구 ↔ 읍면동 ↔ 단지
  useEffect(() => {
    if (status !== "ready") return;
    const naver = window.naver;
    const map = mapRef.current;
    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];

    const hasApts = !!apartments && apartments.length > 0;
    const tier = !hasApts || zoom < DONG_ZOOM ? "region" : zoom < APT_ZOOM ? "dong" : "apt";

    if (tier === "region") {
      regions.forEach((r) => {
        const isSel = selectedLawd === r.lawd;
        const marker = new naver.maps.Marker({
          position: new naver.maps.LatLng(r.lat, r.lng),
          map,
          icon: { content: regionBubble(r, isSel, trade, heat?.[r.lawd]),
                  anchor: new naver.maps.Point(0, 0) },
          // 관심도 상위는 위로 올린다 — 겹칠 때 가려지면 표시한 의미가 없다.
          zIndex: isSel ? 60 : heat?.[r.lawd] ? 40 - Math.min(heat[r.lawd].rank, 30) + 20 : 20,
        });
        naver.maps.Event.addListener(marker, "click", () => cbRef.current.onSelectRegion(r));
        markersRef.current.push(marker);
      });
    } else if (tier === "dong") {
      dongs.forEach((d) => {
        const marker = new naver.maps.Marker({
          position: new naver.maps.LatLng(d.lat, d.lng),
          map,
          icon: { content: dongBubble(d, trade), anchor: new naver.maps.Point(0, 0) },
          zIndex: 50,
        });
        // 동 버블을 누르면 그 동으로 확대 — 네이버와 같은 드릴다운
        naver.maps.Event.addListener(marker, "click", () => {
          map.morph(new naver.maps.LatLng(d.lat, d.lng), APT_ZOOM + 1);
        });
        markersRef.current.push(marker);
      });
    } else {
      apartments!.forEach((a) => {
        const key = favKey(a);
        const isSel = selectedApt === key;
        const marker = new naver.maps.Marker({
          position: new naver.maps.LatLng(a.lat, a.lng),
          map,
          icon: { content: aptPill(a, trade, areaUnit, isSel, favs.has(key)), anchor: new naver.maps.Point(0, 0) },
          zIndex: isSel ? 200 : 100,
        });
        naver.maps.Event.addListener(marker, "click", () => cbRef.current.onSelectApt(a));
        naver.maps.Event.addListener(marker, "dblclick", () => cbRef.current.onAptDetail(a));
        markersRef.current.push(marker);
      });
    }
  }, [regions, apartments, dongs, selectedLawd, selectedApt, trade, areaUnit, favs, zoom, status, heat]);

  // 6) 주변시설 레이어 — 학교/지하철은 실거래 마커와 따로 그린다(껐다 켜도 재계산 최소).
  useEffect(() => {
    if (status !== "ready") return;
    const naver = window.naver;
    const map = mapRef.current;
    poiRef.current.forEach((m) => m.setMap(null));
    poiRef.current = [];
    if (layers.schools) {
      schools.forEach((s) => {
        poiRef.current.push(new naver.maps.Marker({
          position: new naver.maps.LatLng(s.lat, s.lng), map, clickable: false,
          icon: { content: schoolPin(s), anchor: new naver.maps.Point(0, 0) }, zIndex: 15,
        }));
      });
    }
    if (layers.stations) {
      stations.forEach((t) => {
        poiRef.current.push(new naver.maps.Marker({
          position: new naver.maps.LatLng(t.lat, t.lng), map, clickable: false,
          icon: { content: stationPin(t), anchor: new naver.maps.Point(0, 0) }, zIndex: 16,
        }));
      });
    }
  }, [layers, schools, stations, status]);

  // 언마운트 정리
  useEffect(() => () => {
    poiRef.current.forEach((m) => m.setMap(null));
    markersRef.current.forEach((m) => m.setMap(null));
    cadastralRef.current?.setMap(null);
    panoRef.current?.destroy?.();
    mapRef.current?.destroy?.();
  }, []);

  const zoomBy = (d: number) => {
    const map = mapRef.current;
    if (map) map.setZoom(Math.max(6, Math.min(21, map.getZoom() + d)), true);
  };

  // panorama 서브모듈이 실렸는지 — 상태가 아니라 스크립트 로드 결과라 렌더에서 읽는다.
  const panoSupported = status === "ready" && !!window.naver?.maps?.Panorama;

  const tierLabel = zoom < DONG_ZOOM ? "시군구 단위" : zoom < APT_ZOOM ? "읍면동 단위" : "단지 단위";

  return (
    <div style={{ position: "relative", height: "100%", width: "100%" }}>
      <div ref={elRef} style={{ height: "100%", width: "100%" }} />

      {/* 거리뷰 창 — 네이버 부동산의 거리뷰 패널과 같은 자리 */}
      <div
        className={`absolute bottom-3 right-3 z-[600] overflow-hidden rounded-md border border-[#d0d0d0] bg-black shadow-lg ${
          street ? "" : "hidden"
        }`}
        style={{ width: 320, height: 220 }}
      >
        <div ref={panoElRef} style={{ height: "100%", width: "100%" }} />
        <button
          onClick={() => setStreet(false)}
          className="absolute right-1 top-1 z-10 rounded bg-black/55 px-1.5 py-0.5 text-[11px] font-bold text-white"
        >
          ✕
        </button>
        {(streetErr || !panoSupported) && (
          <div className="absolute inset-x-0 bottom-0 bg-black/65 px-2 py-1 text-[10px] text-white">
            {panoSupported ? streetErr : "거리뷰 모듈(panorama)을 불러오지 못했습니다."}
          </div>
        )}
      </div>

      {status === "ready" && (
        <>
          {/* 우상단 지도 컨트롤 — 네이버 부동산의 오른쪽 세로 툴바 */}
          <div className="absolute right-3 top-3 z-[500] flex flex-col items-end gap-1.5">
            <div className="flex overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
              {MAP_KINDS.map((k) => (
                <button
                  key={k.key}
                  onClick={() => setMapKind(k.key)}
                  className={`px-2.5 py-1.5 text-[11px] font-bold transition ${
                    mapKind === k.key ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#f2f2f2]"
                  }`}
                >
                  {k.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setCadastral((v) => !v)}
              className={`rounded-md border px-2.5 py-1.5 text-[11px] font-bold shadow-sm transition ${
                cadastral ? "border-[#217346] bg-[#217346] text-white" : "border-[#d0d0d0] bg-white text-[#555] hover:bg-[#f2f2f2]"
              }`}
            >
              지적편집도
            </button>
            <div className="flex overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
              <button
                onClick={() => onLayers({ ...layers, schools: !layers.schools })}
                title="학교 표시 — 초/중/고 (공공 표준데이터)"
                className={`px-2.5 py-1.5 text-[11px] font-bold transition ${
                  layers.schools ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#f2f2f2]"
                }`}
              >
                학군
              </button>
              <div className="w-px bg-[#e4e4e4]" />
              <button
                onClick={() => onLayers({ ...layers, stations: !layers.stations })}
                title="지하철역 표시 — 환승역은 주황 (공공 표준데이터)"
                className={`px-2.5 py-1.5 text-[11px] font-bold transition ${
                  layers.stations ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#f2f2f2]"
                }`}
              >
                지하철
              </button>
            </div>
            <button
              onClick={() => { setStreetErr(""); setStreet((v) => !v); }}
              className={`rounded-md border px-2.5 py-1.5 text-[11px] font-bold shadow-sm transition ${
                street ? "border-[#217346] bg-[#217346] text-white" : "border-[#d0d0d0] bg-white text-[#555] hover:bg-[#f2f2f2]"
              }`}
            >
              거리뷰
            </button>
            <div className="flex flex-col overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
              <button onClick={() => zoomBy(1)} className="px-2.5 py-1 text-[15px] font-bold text-[#555] hover:bg-[#f2f2f2]">+</button>
              <div className="h-px bg-[#e4e4e4]" />
              <button onClick={() => zoomBy(-1)} className="px-2.5 py-1 text-[15px] font-bold text-[#555] hover:bg-[#f2f2f2]">−</button>
            </div>
          </div>

          {/* 좌하단 줌 단계 안내 — 왜 마커가 바뀌는지 보이게 */}
          <div className="pointer-events-none absolute bottom-3 left-3 z-[500] rounded-md border border-[#e0e0e0] bg-white/95 px-2.5 py-1.5 text-[10px] font-semibold text-[#666] shadow-sm">
            {tierLabel} · 줌 {zoom}
            {zoom < APT_ZOOM && <span className="ml-1 text-[#aaa]">— 확대하면 더 잘게 나뉩니다</span>}
          </div>
        </>
      )}

      {status !== "ready" && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#f5f6f5] p-6 text-center text-sm">
          {status === "loading" && <span className="text-[#888]">네이버 지도 불러오는 중…</span>}
          {status === "no-key" && (
            <div className="max-w-md text-[#555]">
              <div className="mb-1 font-bold text-[#c92a2a]">네이버 지도 인증키가 없습니다</div>
              <p className="text-[12px] leading-relaxed text-[#666]">
                <code className="rounded bg-[#eee] px-1">frontend/.env.local</code> 에
                <code className="mx-1 rounded bg-[#eee] px-1">NEXT_PUBLIC_NAVER_MAP_CLIENT_ID=발급키</code>
                를 넣고 <b>개발서버를 재시작</b>하세요.
              </p>
            </div>
          )}
          {status === "auth-fail" && (
            <div className="max-w-md text-[#555]">
              <div className="mb-1 font-bold text-[#c92a2a]">네이버 지도 인증 실패</div>
              <p className="text-[12px] leading-relaxed text-[#666]">
                Application의 <b>Web 서비스 URL</b>에 <code className="rounded bg-[#eee] px-1">http://localhost:3000</code>
                (와 실제 접속 도메인)을 등록했는지, <b>Dynamic Map</b>이 켜져 있는지 확인하세요.
              </p>
            </div>
          )}
          {status === "load-fail" && <span className="text-[#c92a2a]">네이버 지도 스크립트 로드 실패 — 네트워크·키를 확인하세요.</span>}
        </div>
      )}
    </div>
  );
}
