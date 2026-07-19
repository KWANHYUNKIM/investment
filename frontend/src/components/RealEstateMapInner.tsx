"use client";

import { useEffect, useRef, useState } from "react";
import { RealEstateRegion, RealEstateApartment } from "@/lib/api";

// 네이버 클라우드 플랫폼 Maps 인증키(ncpKeyId). .env.local 에 넣는다.
const CLIENT_ID = process.env.NEXT_PUBLIC_NAVER_MAP_CLIENT_ID || "";

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    naver?: any;
    navermap_authFailure?: () => void;
  }
}

// 평균 거래가(억)별 색
function priceColor(avg: number | null) {
  if (avg == null) return "#9aa0a6";
  if (avg >= 25) return "#7a0c0c";
  if (avg >= 15) return "#c92a2a";
  if (avg >= 10) return "#e8590c";
  if (avg >= 6) return "#f08c00";
  return "#2f9e44";
}
function radius(count: number) {
  return Math.min(30, 5 + Math.sqrt(count) * 1.4);
}

// 네이버 지도 스크립트를 한 번만 로드 (SSR 없음 — 이 컴포넌트는 dynamic ssr:false)
let _loadPromise: Promise<void> | null = null;
function loadNaver(): Promise<void> {
  if (typeof window !== "undefined" && window.naver?.maps) return Promise.resolve();
  if (_loadPromise) return _loadPromise;
  _loadPromise = new Promise<void>((resolve, reject) => {
    if (!CLIENT_ID) { reject(new Error("no-key")); return; }
    const s = document.createElement("script");
    s.type = "text/javascript";
    s.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${encodeURIComponent(CLIENT_ID)}`;
    s.async = true;
    s.onload = () => (window.naver?.maps ? resolve() : reject(new Error("load-fail")));
    s.onerror = () => reject(new Error("load-fail"));
    document.head.appendChild(s);
  });
  return _loadPromise;
}

// 단지 가격박스(호갱노노 스타일) HTML — 네이버 Marker icon.content 로 사용
function aptBoxHtml(a: RealEstateApartment): string {
  const eok = a.recent_eok;
  const txtColor = eok >= 15 ? "#fca5a5" : eok >= 8 ? "#fcd34d" : "#86efac";
  const box = "#1f2937";
  const area = a.recent_area ? `${a.recent_area}㎡` : "";
  return `
    <div style="position:relative;transform:translate(-50%,-100%);cursor:pointer;">
      <div style="background:${box};color:#fff;border-radius:7px;padding:2px 7px 3px;
                  font-size:11px;line-height:1.15;white-space:nowrap;text-align:center;
                  box-shadow:0 1px 4px rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.15);">
        ${area ? `<div style="font-size:9px;color:#cbd5e1;font-weight:600;">${area}</div>` : ""}
        <div style="font-weight:800;color:${txtColor};">실 ${eok}억</div>
      </div>
      <div style="position:absolute;left:50%;top:100%;transform:translateX(-50%);width:0;height:0;
                  border-left:5px solid transparent;border-right:5px solid transparent;
                  border-top:6px solid ${box};"></div>
    </div>`;
}

// 시군구 클러스터 원(픽셀 크기 고정) HTML
function regionBubbleHtml(r: RealEstateRegion, selected: boolean, dim: boolean): string {
  const rad = radius(r.count);
  const d = rad * 2;
  const color = priceColor(r.avg_eok);
  const fillOpacity = dim ? (selected ? 0.12 : 0.18) : r.approx ? 0.35 : 0.6;
  const opacity = dim && !selected ? 0.35 : 1;
  const title = `${r.sido} ${r.region}${r.approx ? " (근사)" : ""} · 거래 ${r.count}건 · 평균 ${r.avg_eok ?? "—"}억 · 합계 ${r.amount_eok}억`;
  return `
    <div title="${title.replace(/"/g, "&quot;")}"
         style="width:${d}px;height:${d}px;border-radius:50%;transform:translate(-50%,-50%);
                background:${color};opacity:${opacity};cursor:pointer;
                border:${selected ? "3px solid #111" : `1px solid ${color}`};
                box-shadow:0 0 0 9999px rgba(0,0,0,0);">
      <div style="width:100%;height:100%;border-radius:50%;background:${color};opacity:${fillOpacity};"></div>
    </div>`;
}

export default function RealEstateMapInner({
  regions,
  apartments,
  selected,
  flyTarget,
  onSelect,
  onAptDetail,
}: {
  regions: RealEstateRegion[];
  apartments: RealEstateApartment[] | null;
  selected: string | null;
  flyTarget: { lat: number; lng: number; zoom: number } | null;
  onSelect: (r: RealEstateRegion) => void;
  onAptDetail: (a: RealEstateApartment) => void;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const infoRef = useRef<any>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "no-key" | "auth-fail" | "load-fail">(
    CLIENT_ID ? "loading" : "no-key",
  );

  // 콜백이 매 렌더 최신값을 보도록 ref 로 보관 (마커 이벤트 클로저용)
  const cbRef = useRef({ onSelect, onAptDetail });
  useEffect(() => { cbRef.current = { onSelect, onAptDetail }; });

  // 1) 지도 최초 생성
  useEffect(() => {
    if (!CLIENT_ID) return; // 키 없음 → 초기 status 가 이미 "no-key"
    let alive = true;
    window.navermap_authFailure = () => alive && setStatus("auth-fail");
    loadNaver()
      .then(() => {
        if (!alive || !elRef.current) return;
        const naver = window.naver;
        mapRef.current = new naver.maps.Map(elRef.current, {
          center: new naver.maps.LatLng(36.4, 127.9),
          zoom: 7,
          scaleControl: false,
          logoControl: true,
          mapDataControl: false,
          zoomControl: true,
          zoomControlOptions: { position: naver.maps.Position.TOP_RIGHT },
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

  // 3) 마커 다시 그리기 (지역/단지/선택 변경 시)
  useEffect(() => {
    if (status !== "ready") return;
    const naver = window.naver;
    const map = mapRef.current;
    // 기존 마커 제거
    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];
    infoRef.current?.close();

    const showApts = !!(apartments && apartments.length > 0);

    // 시군구 클러스터 원
    regions.forEach((r) => {
      const isSel = selected === r.lawd;
      const marker = new naver.maps.Marker({
        position: new naver.maps.LatLng(r.lat, r.lng),
        map,
        icon: { content: regionBubbleHtml(r, isSel, showApts), anchor: new naver.maps.Point(0, 0) },
        zIndex: isSel ? 60 : 20,
      });
      naver.maps.Event.addListener(marker, "click", () => cbRef.current.onSelect(r));
      markersRef.current.push(marker);
    });

    // 단지별 가격박스 + 실거래 상세 InfoWindow
    if (showApts) {
      apartments!.forEach((a) => {
        const marker = new naver.maps.Marker({
          position: new naver.maps.LatLng(a.lat, a.lng),
          map,
          icon: { content: aptBoxHtml(a), anchor: new naver.maps.Point(0, 0) },
          zIndex: 100,
        });
        naver.maps.Event.addListener(marker, "click", () => {
          infoRef.current?.close();
          const el = document.createElement("div");
          el.className = "text-[11px]";
          el.style.cssText = "min-width:190px;max-width:240px;padding:9px 11px;font-size:11px;line-height:1.35;";
          el.innerHTML = `
            <div style="font-size:14px;font-weight:800;color:#222;">${a.apt}</div>
            <div style="color:#888;">${a.dong}${a.build_year ? ` · ${a.build_year}년` : ""}${a.approx ? ' · <span style="color:#c92a2a;">위치 근사</span>' : ""}</div>
            <div style="margin-top:6px;font-weight:800;color:#217346;">실거래 ${a.min_eok === a.max_eok ? `${a.recent_eok}억` : `${a.min_eok}~${a.max_eok}억`}<span style="margin-left:4px;font-weight:400;color:#999;">· ${a.count}건</span></div>
            ${a.areas.length ? `<div style="color:#888;">전용 ${a.areas.map((x) => `${x}㎡`).join(", ")}</div>` : ""}
            <table style="margin-top:6px;width:100%;border-collapse:collapse;">
              <tbody>
                ${a.deals.map((d) => `
                  <tr style="border-top:1px solid #f0f0f0;">
                    <td style="padding:2px 8px 2px 0;color:#888;">${d.date.slice(5)}</td>
                    <td style="padding:2px 8px 2px 0;text-align:right;color:#666;">${d.area ? `${d.area}㎡` : "—"}${d.floor ? ` ${d.floor}층` : ""}</td>
                    <td style="padding:2px 0;text-align:right;font-weight:700;color:#217346;">${d.amount_eok}억</td>
                  </tr>`).join("")}
              </tbody>
            </table>`;
          const btn = document.createElement("button");
          btn.textContent = "시세/실거래 상세 ›";
          btn.style.cssText = "margin-top:8px;width:100%;border:0;border-radius:5px;background:#217346;color:#fff;padding:5px 0;font-size:11px;font-weight:700;cursor:pointer;";
          btn.onclick = () => { infoRef.current?.close(); cbRef.current.onAptDetail(a); };
          el.insertBefore(btn, el.querySelector("table"));

          const info = new naver.maps.InfoWindow({
            content: el,
            borderWidth: 1,
            borderColor: "#d0d0d0",
            anchorSize: new naver.maps.Size(10, 10),
            backgroundColor: "#fff",
            disableAnchor: false,
          });
          info.open(map, marker);
          infoRef.current = info;
        });
        markersRef.current.push(marker);
      });
    }
  }, [regions, apartments, selected, status]);

  // 언마운트 정리
  useEffect(() => () => {
    markersRef.current.forEach((m) => m.setMap(null));
    infoRef.current?.close();
    mapRef.current?.destroy?.();
  }, []);

  return (
    <div style={{ position: "relative", height: "100%", width: "100%" }}>
      <div ref={elRef} style={{ height: "100%", width: "100%", borderRadius: 8, overflow: "hidden" }} />
      {status !== "ready" && (
        <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-[#f5f6f5] p-6 text-center text-sm">
          {status === "loading" && <span className="text-[#888]">네이버 지도 불러오는 중…</span>}
          {status === "no-key" && (
            <div className="max-w-md text-[#555]">
              <div className="mb-1 font-bold text-[#c92a2a]">네이버 지도 인증키가 없습니다</div>
              <p className="text-[12px] leading-relaxed text-[#666]">
                <code className="rounded bg-[#eee] px-1">frontend/.env.local</code> 에
                <code className="mx-1 rounded bg-[#eee] px-1">NEXT_PUBLIC_NAVER_MAP_CLIENT_ID=발급키</code>
                를 넣고 <b>개발서버를 재시작</b>하세요. 키는 네이버 클라우드 플랫폼 → Maps → Application 등록에서 발급합니다.
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
