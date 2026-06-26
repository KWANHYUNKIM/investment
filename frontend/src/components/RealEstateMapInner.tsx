"use client";

import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { RealEstateRegion } from "@/lib/api";

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

export default function RealEstateMapInner({
  regions,
  selected,
  onSelect,
}: {
  regions: RealEstateRegion[];
  selected: string | null;
  onSelect: (r: RealEstateRegion) => void;
}) {
  return (
    <MapContainer
      center={[36.4, 127.9]}
      zoom={7}
      scrollWheelZoom
      style={{ height: "100%", width: "100%", borderRadius: 8 }}
    >
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
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
              fillOpacity: r.approx ? 0.35 : 0.6,
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
    </MapContainer>
  );
}
