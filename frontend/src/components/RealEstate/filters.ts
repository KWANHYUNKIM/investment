// 지도·목록에 함께 걸리는 필터. 네이버 부동산 상단 필터바와 같은 축을 쓰되,
// 우리 데이터(국토부 실거래)에 없는 축(방향·매물특징)은 실거래에서 계산되는
// 축(거래건수·전세가율)으로 대체한다.

import type { RealEstateApartment, TradeKind } from "@/lib/api";
import { toPyeong } from "./format";

export interface Filters {
  trade: TradeKind;
  priceMin: number | null;   // 억 (월세는 보증금)
  priceMax: number | null;
  monthlyMax: number | null; // 만원 — 월세 전용
  areas: string[];           // AREA_BUCKETS.key
  buildAge: string | null;   // BUILD_AGES.key
  floors: string[];          // FLOOR_BANDS.key
  minDeals: number;          // 최소 거래건수
  jeonseRatioMin: number | null; // 전세가율 하한(%) — 매매 전용
  favOnly: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  trade: "sale",
  priceMin: null,
  priceMax: null,
  monthlyMax: null,
  areas: [],
  buildAge: null,
  floors: [],
  minDeals: 0,
  jeonseRatioMin: null,
  favOnly: false,
};

// 평형대 — 네이버의 면적 버킷과 같은 구간
export const AREA_BUCKETS = [
  { key: "u10", label: "~10평", min: 0, max: 10 },
  { key: "p10", label: "10평대", min: 10, max: 20 },
  { key: "p20", label: "20평대", min: 20, max: 30 },
  { key: "p30", label: "30평대", min: 30, max: 40 },
  { key: "p40", label: "40평대", min: 40, max: 50 },
  { key: "p50", label: "50평~", min: 50, max: Infinity },
] as const;

export const BUILD_AGES = [
  { key: "a5", label: "5년 이내", max: 5 },
  { key: "a10", label: "10년 이내", max: 10 },
  { key: "a15", label: "15년 이내", max: 15 },
  { key: "a20", label: "20년 이내", max: 20 },
  { key: "over20", label: "20년 이상", max: -1 },
] as const;

export const FLOOR_BANDS = [
  { key: "low", label: "저층", min: 1, max: 5 },
  { key: "mid", label: "중층", min: 6, max: 15 },
  { key: "high", label: "고층", min: 16, max: Infinity },
] as const;

export const SORTS = [
  { key: "price_desc", label: "가격 높은순" },
  { key: "price_asc", label: "가격 낮은순" },
  { key: "deals", label: "거래 많은순" },
  { key: "recent", label: "최근 거래순" },
  { key: "gap", label: "갭 작은순" },
  { key: "name", label: "단지명순" },
] as const;

export type SortKey = (typeof SORTS)[number]["key"];

function floorBandOf(floor: string | null | undefined): string | null {
  const f = Number(floor);
  if (!f) return null;
  for (const b of FLOOR_BANDS) if (f >= b.min && f <= b.max) return b.key;
  return null;
}

/** 단지 하나가 필터를 통과하는지. 면적·층은 그 단지의 실거래 중 하나라도 맞으면 통과. */
export function passes(a: RealEstateApartment, f: Filters, favs: ReadonlySet<string>): boolean {
  if (f.favOnly && !favs.has(favKey(a))) return false;
  if (f.minDeals > 0 && a.count < f.minDeals) return false;

  if (f.priceMin != null && a.max_eok < f.priceMin) return false;
  if (f.priceMax != null && a.min_eok > f.priceMax) return false;
  if (f.trade === "wolse" && f.monthlyMax != null && (a.monthly_min ?? 0) > f.monthlyMax) return false;

  if (f.trade === "sale" && f.jeonseRatioMin != null) {
    if (a.jeonse_ratio == null || a.jeonse_ratio < f.jeonseRatioMin) return false;
  }

  if (f.areas.length) {
    const buckets = f.areas
      .map((k) => AREA_BUCKETS.find((b) => b.key === k))
      .filter(Boolean) as (typeof AREA_BUCKETS)[number][];
    const hit = a.areas.some((m2) => {
      const p = toPyeong(m2);
      return buckets.some((b) => p >= b.min && p < b.max);
    });
    if (!hit) return false;
  }

  if (f.buildAge) {
    const y = Number(a.build_year);
    if (!y) return false;
    const age = new Date().getFullYear() - y;
    const spec = BUILD_AGES.find((b) => b.key === f.buildAge);
    if (!spec) return true;
    if (spec.max === -1 ? age < 20 : age > spec.max) return false;
  }

  if (f.floors.length) {
    const hit = a.deals.some((d) => {
      const band = floorBandOf(d.floor);
      return band != null && f.floors.includes(band);
    });
    if (!hit) return false;
  }

  return true;
}

export function sortApartments(list: RealEstateApartment[], key: SortKey): RealEstateApartment[] {
  const out = [...list];
  switch (key) {
    case "price_asc":
      return out.sort((a, b) => a.recent_eok - b.recent_eok);
    case "deals":
      return out.sort((a, b) => b.count - a.count);
    case "recent":
      return out.sort((a, b) => (b.recent_date ?? "").localeCompare(a.recent_date ?? ""));
    case "gap":
      return out.sort((a, b) => (a.gap_eok ?? Infinity) - (b.gap_eok ?? Infinity));
    case "name":
      return out.sort((a, b) => a.apt.localeCompare(b.apt, "ko"));
    default:
      return out.sort((a, b) => b.recent_eok - a.recent_eok);
  }
}

/** 관심단지 키 — 단지명+동이면 한 시군구 안에서 유일하다. */
export function favKey(a: { apt: string; dong: string }): string {
  return `${a.apt}|${a.dong}`;
}

/** 기본값과 다른 필터가 몇 개인지 — 필터바 "초기화" 뱃지에 쓴다. */
export function activeCount(f: Filters): number {
  let n = 0;
  if (f.priceMin != null || f.priceMax != null) n++;
  if (f.monthlyMax != null) n++;
  if (f.areas.length) n++;
  if (f.buildAge) n++;
  if (f.floors.length) n++;
  if (f.minDeals > 0) n++;
  if (f.jeonseRatioMin != null) n++;
  if (f.favOnly) n++;
  return n;
}
