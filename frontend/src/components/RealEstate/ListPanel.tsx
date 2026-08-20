"use client";

import type { RealEstateApartment, RealEstateRegion, TradeKind } from "@/lib/api";
import { Spinner } from "@/components/ui";
import { TRADE_META, area as fmtArea, buildAge, eok, manwon, priceRange, AreaUnit } from "./format";
import { useEffect, useRef } from "react";
import { RegionTrend } from "@/components/RealEstate/RegionTrend";
import { favKey, SORTS, SortKey } from "./filters";

/* 네이버 부동산 좌측 목록 — 단지 카드 + 정렬 + 관심단지 */

function Stars({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <span
      role="button"
      tabIndex={0}
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
      onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); onToggle(); } }}
      title={on ? "관심단지 해제" : "관심단지 등록"}
      className={`shrink-0 cursor-pointer text-[15px] leading-none transition ${
        on ? "text-[#f0a500]" : "text-[#d8d8d8] hover:text-[#f0a500]"
      }`}
    >
      ★
    </span>
  );
}

export function ListPanel({
  region, apartments, total, loading, geocoding, trade, areaUnit, sort, onSort,
  favs, onToggleFav, selectedApt, onPick, onDetail, onClose, latestLabel, unavailable, kindLabel,
}: {
  region: RealEstateRegion | null;
  apartments: RealEstateApartment[] | null;   // 필터·정렬 끝난 목록
  total: number;                              // 필터 전 단지 수
  loading: boolean;
  geocoding: boolean;
  trade: TradeKind;
  areaUnit: AreaUnit;
  sort: SortKey;
  onSort: (s: SortKey) => void;
  favs: ReadonlySet<string>;
  onToggleFav: (a: RealEstateApartment) => void;
  selectedApt: string | null;
  onPick: (a: RealEstateApartment) => void;
  onDetail: (a: RealEstateApartment) => void;
  onClose: () => void;
  latestLabel?: string | null;
  unavailable?: string | null;  // API 호출한도 초과 등 — 빈 목록과 구분해 알린다
  kindLabel?: string;           // 아파트/오피스텔/토지… — 카드 문구를 유형에 맞춘다
}) {
  const meta = TRADE_META[trade];

  // 지도에서 마커를 누르면 목록의 그 줄만 색이 바뀐다. 그런데 목록이 길면 그 줄이
  // **화면 밖**이라, 사용자 눈에는 아무 일도 안 일어난 것으로 보인다(실제로 그렇게
  // 보고받았다). 선택이 바뀌면 그 줄로 스크롤한다.
  const selRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!selectedApt || !selRef.current) return;
    selRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedApt]);

  const picked = apartments?.find((a) => favKey(a) === selectedApt) ?? null;

  if (!region) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-xs leading-relaxed text-[#999]">
        지도에서 지역을 클릭하거나<br />지도를 확대하면<br />그 지역 단지 실거래가 여기 나옵니다.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* 헤더 */}
      <div className="flex items-start justify-between border-b border-[#eee] px-3.5 py-2.5">
        <div className="min-w-0">
          <div className="truncate text-[15px] font-bold text-[#222]">
            {region.sido} {region.region}
          </div>
          <div className="mt-0.5 text-[11px] text-[#888]">
            {latestLabel ?? ""} {kindLabel ?? ""} {meta.label} 실거래
            {apartments && (
              <> · <b className="text-[#555]">{apartments.length}</b>
                {apartments.length !== total && <span className="text-[#aaa]">/{total}</span>} 곳</>
            )}
            {geocoding && <span className="text-[#8a6d1a]"> · 위치 보정 중…</span>}
          </div>
        </div>
        <button
          onClick={onClose}
          title="닫기"
          className="ml-2 shrink-0 rounded p-1 text-lg leading-none text-[#999] hover:bg-[#f2f2f2] hover:text-[#555]"
        >
          ×
        </button>
      </div>

      {/* 지역 추이 — 단지 목록보다 위에 둔다. '이 동네가 어떻게 움직여 왔나' 가
          개별 단지를 보기 전에 답해져야 하는 질문이라서다. */}
      <RegionTrend key={region.lawd} lawd={region.lawd} region={region.region} />

      {/* 지도에서 고른 단지 — 목록 맨 위에 고정한다. 스크롤만으로는 '어느 걸 눌렀는지'
          가 목록 안에서 흐려지고, 필터를 바꾸면 그 줄이 아예 사라지기도 한다. */}
      {picked && (
        <div className="shrink-0 border-b border-[#e0e0e0] bg-[#f2f7f4] px-3.5 py-2">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-[13px] font-bold text-[#217346]">{picked.apt}</div>
              <div className="mt-0.5 text-[11px] text-[#666]">
                {picked.dong}
                {picked.recent_area ? ` · 전용 ${fmtArea(picked.recent_area, areaUnit)}` : ""}
                {picked.recent_floor ? ` · ${picked.recent_floor}층` : ""}
                {picked.count ? ` · 거래 ${picked.count}건` : ""}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[15px] font-extrabold tabular-nums" style={{ color: meta.color }}>
                {priceRange(picked, trade)}
              </div>
              <button
                onClick={() => onDetail(picked)}
                className="mt-0.5 text-[11px] font-semibold text-[#217346] hover:underline"
              >
                시세 그래프 보기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 정렬 */}
      <div className="flex items-center gap-2 border-b border-[#eee] px-3.5 py-1.5">
        <span className="text-[11px] text-[#999]">정렬</span>
        <select
          value={sort}
          onChange={(e) => onSort(e.target.value as SortKey)}
          className="flex-1 rounded border border-[#ddd] bg-white px-1.5 py-1 text-[11px] text-[#444] outline-none focus:border-[#217346]"
        >
          {SORTS.filter((s) => s.key !== "gap" || trade === "sale").map((s) => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
      </div>

      {/* 카드 목록 */}
      <div className="min-h-0 flex-1 overflow-y-auto bg-[#f7f8f9] p-2.5">
        {loading && !apartments ? (
          <div className="flex items-center gap-2 py-6 text-xs text-[#888]">
            <Spinner /> 단지 실거래 불러오는 중…
          </div>
        ) : !apartments || apartments.length === 0 ? (
          unavailable ? (
            <div className="rounded border border-[#e0c98a] bg-[#fff8e6] px-3 py-4 text-center text-[11px] leading-relaxed text-[#8a6d1a]">
              {unavailable}
            </div>
          ) : (
            <div className="whitespace-pre-line py-6 text-center text-xs leading-relaxed text-[#999]">
              {total === 0 ? "실거래 내역이 없습니다." : "필터에 맞는 단지가 없습니다.\n조건을 넓혀 보세요."}
            </div>
          )
        ) : (
          <div className="flex flex-col gap-2">
            {apartments.map((a) => {
              const key = favKey(a);
              const sel = selectedApt === key;
              const age = buildAge(a.build_year);
              return (
                <div
                  key={key}
                  ref={sel ? selRef : undefined}
                  onClick={() => onPick(a)}
                  className={`cursor-pointer rounded-lg border bg-white px-3 py-2.5 shadow-sm transition ${
                    sel ? "border-[#217346] ring-1 ring-[#217346]" : "border-[#e5e7eb] hover:border-[#217346] hover:shadow"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="truncate text-[13px] font-bold text-[#222]">{a.apt}</span>
                    <Stars on={favs.has(key)} onToggle={() => onToggleFav(a)} />
                  </div>

                  <div className="mt-0.5 text-[15px] font-extrabold tabular-nums" style={{ color: meta.color }}>
                    {priceRange(a, trade)}
                    {trade === "wolse" && <span className="ml-1 text-[10px] font-semibold text-[#999]">보증/월</span>}
                  </div>

                  <div className="mt-1 text-[11px] text-[#666]">
                    {kindLabel ?? "아파트"}
                    {a.recent_area ? ` · 전용 ${fmtArea(a.recent_area, areaUnit)}` : ""}
                    {a.recent_floor ? ` · ${a.recent_floor}층` : ""}
                    {a.dong ? ` · ${a.dong}` : ""}
                    {age ? ` · ${age}` : ""}
                  </div>

                  {/* 매매 카드에는 전세가율/갭 — 실거래로만 계산되는 값이라 네이버보다 더 정확하다 */}
                  {trade === "sale" && a.jeonse_ratio != null && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1">
                      <span className="rounded bg-[#eaf1fb] px-1.5 py-0.5 text-[10px] font-bold text-[#1a63c4]">
                        전세가율 {a.jeonse_ratio}%
                      </span>
                      <span className="rounded bg-[#f4f4f4] px-1.5 py-0.5 text-[10px] font-semibold text-[#666]">
                        갭 {eok(a.gap_eok)}
                      </span>
                      <span className="text-[10px] text-[#aaa]">전세 {eok(a.jeonse_eok)}</span>
                    </div>
                  )}

                  {trade === "wolse" && (a.monthly_min ?? 0) > 0 && (
                    <div className="mt-1.5">
                      <span className="rounded bg-[#fdf0e8] px-1.5 py-0.5 text-[10px] font-bold text-[#d9480f]">
                        월세 {manwon(a.monthly_min)}~{manwon(a.monthly_max)}만
                      </span>
                    </div>
                  )}

                  <div className="mt-1.5 flex items-center justify-between gap-1.5">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                        style={{ background: meta.soft, color: meta.color }}
                      >
                        최근거래
                      </span>
                      <span className="text-[11px] text-[#888]">{a.recent_date || "—"} · {a.count}건</span>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); onDetail(a); }}
                      className="shrink-0 rounded border border-[#ddd] px-1.5 py-0.5 text-[10px] font-semibold text-[#555] hover:border-[#217346] hover:text-[#217346]"
                    >
                      시세 ›
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
