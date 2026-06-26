"use client";

import { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { RealEstateRegion, RealEstateApartment } from "@/lib/api";

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

// 단지 가격박스 마커(호갱노노 스타일). 바닥 꼭짓점이 좌표에 닿도록 wrapper로 자가정렬.
function aptDivIcon(a: RealEstateApartment): L.DivIcon {
  const eok = a.recent_eok;
  const txtColor = eok >= 15 ? "#fca5a5" : eok >= 8 ? "#fcd34d" : "#86efac";
  const box = "#1f2937";
  const area = a.recent_area ? `${a.recent_area}㎡` : "";
  const html = `
    <div style="position:absolute;transform:translate(-50%,-100%);">
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
  return L.divIcon({
    html,
    className: "re-apt-pin",
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}

// 지역/단지 선택 시 지도 부드럽게 이동
function FlyTo({ target }: { target: { lat: number; lng: number; zoom: number } | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lng], target.zoom, { duration: 0.8 });
  }, [target, map]);
  return null;
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
  const showApts = apartments && apartments.length > 0;
  return (
    <MapContainer
      center={[36.4, 127.9]}
      zoom={7}
      scrollWheelZoom
      style={{ height: "100%", width: "100%", borderRadius: 8 }}
    >
      <TileLayer
        attribution="&copy; OpenStreetMap"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FlyTo target={flyTarget} />

      {/* 시군구 클러스터 원 (단지 표시 중이면 흐리게) */}
      {regions.map((r) => {
        const isSel = selected === r.lawd;
        return (
          <CircleMarker
            key={r.lawd}
            center={[r.lat, r.lng]}
            radius={radius(r.count)}
            pathOptions={{
              color: isSel ? "#111" : priceColor(r.avg_eok),
              weight: isSel ? 3 : 1,
              fillColor: priceColor(r.avg_eok),
              fillOpacity: showApts ? (isSel ? 0.12 : 0.18) : r.approx ? 0.35 : 0.6,
              opacity: showApts && !isSel ? 0.35 : 1,
            }}
            eventHandlers={{ click: () => onSelect(r) }}
          >
            <Tooltip>
              <div className="text-xs">
                <b>{r.sido} {r.region}</b>
                {r.approx && <span className="text-[#c92a2a]"> (근사)</span>}
                <br />
                거래 {r.count}건 · 평균 {r.avg_eok ?? "—"}억 · 합계 {r.amount_eok}억
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}

      {/* 단지별 가격박스 마커 */}
      {showApts &&
        apartments!.map((a, i) => (
          <Marker key={`${a.apt}-${a.dong}-${i}`} position={[a.lat, a.lng]} icon={aptDivIcon(a)}>
            <Popup>
              <div className="text-[11px]" style={{ minWidth: 180 }}>
                <div className="text-sm font-bold text-[#222]">{a.apt}</div>
                <div className="text-[#888]">
                  {a.dong}
                  {a.build_year ? ` · ${a.build_year}년` : ""}
                  {a.approx && <span className="text-[#c92a2a]"> · 위치 근사</span>}
                </div>
                <div className="mt-1.5 font-bold text-[#217346]">
                  실거래 {a.min_eok === a.max_eok ? `${a.recent_eok}억` : `${a.min_eok}~${a.max_eok}억`}
                  <span className="ml-1 font-normal text-[#999]">· {a.count}건</span>
                </div>
                {a.areas.length > 0 && (
                  <div className="text-[#888]">전용 {a.areas.map((x) => `${x}㎡`).join(", ")}</div>
                )}
                <button
                  onClick={() => onAptDetail(a)}
                  className="mt-1.5 w-full rounded bg-[#217346] py-1 text-[11px] font-bold text-white hover:bg-[#1b5e3a]"
                >
                  시세/실거래 상세 ›
                </button>
                <table className="mt-1.5 w-full">
                  <tbody>
                    {a.deals.map((d, j) => (
                      <tr key={j} className="border-t border-[#f0f0f0]">
                        <td className="py-0.5 pr-2 text-[#888] tabular-nums">{d.date.slice(5)}</td>
                        <td className="py-0.5 pr-2 text-right text-[#666] tabular-nums">
                          {d.area ? `${d.area}㎡` : "—"}
                          {d.floor ? ` ${d.floor}층` : ""}
                        </td>
                        <td className="py-0.5 text-right font-bold text-[#217346] tabular-nums">{d.amount_eok}억</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Popup>
          </Marker>
        ))}
    </MapContainer>
  );
}
