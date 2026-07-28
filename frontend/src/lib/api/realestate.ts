// 부동산 — 실거래 거래액·전월세·지도·단지 상세

import { request } from "./client";

// 부동산 실거래 — 국토부 RTMS (서울 25개구 아파트 매매 월별 거래량·거래대금)
export interface RealEstateMonth {
  ym: string;
  label: string;
  count: number;
  amount_eok: number;
  provisional: boolean; // 신고 진행중(잠정) — 보통 당월
}

export interface RealEstateSido {
  sido: string;
  count: number;
  amount_eok: number;
}

export interface RealEstateSigungu {
  region: string;
  sido: string;
  count: number;
  amount_eok: number;
}

export interface RealEstateTrades {
  available: boolean;
  reason?: string;
  scope: string;
  source?: string;
  latest_ym?: string;
  latest_label?: string;
  latest_count?: number;
  latest_amount_eok?: number;
  mom_count_pct?: number | null;
  region_ym?: string;
  monthly: RealEstateMonth[];
  by_sido: RealEstateSido[];
  top_sigungu: RealEstateSigungu[];
  partial?: boolean;
}

// 부동산 전월세 실거래 — 국토부 RTMS (전국 아파트 전월세)
export interface RentMonth {
  ym: string;
  label: string;
  count: number;
  jeonse: number;
  wolse: number;
  wolse_ratio: number | null;
  avg_jeonse_eok: number | null;
  provisional: boolean;
}

export interface RentSido {
  sido: string;
  count: number;
  wolse_ratio: number | null;
  avg_jeonse_eok: number | null;
}

export interface RealEstateRent {
  available: boolean;
  reason?: string;
  scope: string;
  source?: string;
  latest_ym?: string;
  latest_label?: string;
  latest_count?: number;
  latest_jeonse?: number;
  latest_wolse?: number;
  latest_wolse_ratio?: number | null;
  latest_avg_jeonse_eok?: number | null;
  mom_count_pct?: number | null;
  region_ym?: string;
  monthly: RentMonth[];
  by_sido: RentSido[];
  partial?: boolean;
}

// 부동산 실거래 지도
export interface RealEstateRegion {
  region: string;
  sido: string;
  lawd: string;
  count: number;
  amount_eok: number;
  avg_eok: number | null;
  lat: number;
  lng: number;
  approx: boolean; // true=시도 중심 근사(지오코딩 미완)
}

export interface RealEstateMapData {
  ready: boolean; // 실거래 데이터가 채워졌는지 (false여도 지도는 표시)
  warming: boolean;
  message: string | null; // 수집중/안내 메시지
  source?: string;
  latest_label?: string | null;
  region_ym?: string | null;
  count?: number;
  geocoded?: number;
  regions: RealEstateRegion[];
  note?: string;
}

export interface RealEstateDeal {
  apt: string;
  dong: string;
  area: number | null;
  amount_eok: number;
  floor: string | null;
  build_year: string | null;
  date: string;
}

export interface RealEstateDeals {
  lawd: string;
  count: number;
  deals: RealEstateDeal[];
}

export interface RealEstateApartment {
  apt: string;
  dong: string;
  count: number;
  recent_eok: number;
  recent_area: number | null;
  recent_date: string;
  recent_floor: string | null;
  build_year: string | null;
  min_eok: number;
  max_eok: number;
  areas: number[];
  lat: number;
  lng: number;
  approx: boolean; // true=동 좌표 미확보 → 시군구 중심 근사
  deals: RealEstateDeal[];
}

export interface RealEstateApartments {
  lawd: string;
  sido: string;
  region: string;
  ym?: string | null;
  count: number;
  deal_count: number;
  geocoded: number;
  geocoding: boolean; // 동 좌표 채우는 중 → 잠시 후 재조회하면 정밀해짐
  center: number[];
  apartments: RealEstateApartment[];
}

export interface ReDealPt {
  date: string;
  eok: number;
  floor: string | null;
  area: number | null;
}

export interface ReSeriesPt {
  ym: string; // YYYY-MM
  avg: number;
  min: number;
  max: number;
  count: number;
}

export interface ReAreaMeta {
  area: number;
  key: string; // series 키
  count: number;
  min_eok: number;
  max_eok: number;
  recent_eok: number;
  recent_date: string;
  deals: ReDealPt[];
}

export interface ReStatic {
  available: boolean;
  reason: string;
  households: number | null;
  dong_count: number | null;
  approval_date: string | null;
  floors: string | null;
  parking: string | null;
  far: number | null;
  bcr: number | null;
  builder: string | null;
  heating: string | null;
  office_tel: string | null;
  road_address: string | null;
}

export interface RealEstateApartmentDetail {
  lawd: string;
  sido: string;
  region: string;
  apt: string;
  dong: string;
  ready: boolean;
  warming: boolean;
  progress: { done: number; total: number };
  months?: number;
  hist_from?: string; // YYYYMM
  build_year: string | null;
  total_deals?: number;
  last_date?: string | null;
  areas: ReAreaMeta[];
  series: Record<string, ReSeriesPt[]>;
  static: ReStatic;
  source?: string;
  note?: string;
  message?: string;
}

export const realestateApi = {
  realestateTrades: () => request<RealEstateTrades>(`/api/data/realestate-trades`),
  realestateRent: () => request<RealEstateRent>(`/api/data/realestate-rent`),
  realestateMap: () => request<RealEstateMapData>(`/api/data/realestate-map`),
  realestateDeals: (lawd: string, ym?: string) =>
    request<RealEstateDeals>(`/api/data/realestate-deals?lawd=${encodeURIComponent(lawd)}${ym ? `&ym=${ym}` : ""}`),
  realestateApartments: (lawd: string, ym?: string) =>
    request<RealEstateApartments>(`/api/data/realestate-apartments?lawd=${encodeURIComponent(lawd)}${ym ? `&ym=${ym}` : ""}`),
  realestateApartment: (lawd: string, apt: string, dong?: string, months = 120) =>
    request<RealEstateApartmentDetail>(
      `/api/data/realestate-apartment?lawd=${encodeURIComponent(lawd)}&apt=${encodeURIComponent(apt)}${
        dong ? `&dong=${encodeURIComponent(dong)}` : ""
      }&months=${months}`,
    ),
};
