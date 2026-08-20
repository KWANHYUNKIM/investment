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

// 지역별 관심도 — 네이버 데이터랩 검색어 트렌드
//
// index 는 검색 **횟수가 아니다.** 데이터랩은 요청마다 최대값을 100 으로 잡는 상대값만
// 주기 때문에, 모든 요청에 같은 앵커 키워드를 끼워 넣고 그 값으로 나눈 '앵커 대비 배수'다.
// 이 축 위에서만 지역끼리 비교가 성립한다.
export interface InterestPoint {
  period: string;
  ratio: number;
}

export interface InterestItem {
  lawd: string;
  sido: string;
  region: string;
  keyword: string;
  index: number;
  rank: number;
  trend_pct: number | null;   // 최근 3구간 대비 그 앞 3구간
  series: InterestPoint[];
}

export interface InterestBoard {
  ready: boolean;
  warming: boolean;
  message?: string | null;
  updated?: string;
  anchor?: string;
  unit?: string;
  period?: { start: string; end: string };
  count: number;
  dropped?: string[];
  items: InterestItem[];
  source: string;
  note: string;
}

export interface InterestCollectResult {
  started: boolean;
  reason?: string;
  configured?: boolean;
  running?: boolean;
  done?: number;
  total?: number;
  msg?: string;
}

// 거래유형 — 네이버 부동산의 매매/전세/월세 전환에 대응
export type TradeKind = "sale" | "jeonse" | "wolse";

// 매물 종류 — 네이버의 아파트/오피스텔/빌라… 탭에 대응(국토부 RTMS 유형)
export type PropertyKind = "apt" | "offi" | "rh" | "sh" | "nrg" | "land" | "silv";

export interface PropertyKindMeta {
  key: PropertyKind;
  label: string;
  has_rent: boolean; // false = 그 유형은 전월세 실거래가 공공데이터에 없음
}

export interface RealEstateDeal {
  apt: string;
  dong: string;
  area: number | null;
  amount_eok: number;      // 매매가(억)
  deposit_eok?: number;    // 전월세 보증금(억) — trade=jeonse|wolse
  monthly_manwon?: number; // 월세(만원) — trade=wolse
  rent_type?: "전세" | "월세";
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
  // 매매(trade=sale)일 때만 — 같은 달 전세 실거래로 계산
  jeonse_eok?: number | null;
  jeonse_ratio?: number | null; // 전세가율 %
  gap_eok?: number | null;      // 갭(매매중위 − 전세중위)
  // 월세(trade=wolse)일 때만 — 보증금은 min/max_eok, 월세는 아래
  monthly_min?: number;
  monthly_max?: number;
  monthly_recent?: number;
}

export interface RealEstateApartments {
  lawd: string;
  sido: string;
  region: string;
  ym?: string | null;
  trade?: TradeKind;
  kind?: PropertyKind;
  kind_label?: string;
  count: number;
  deal_count: number;
  geocoded: number;
  geocoding: boolean; // 동 좌표 채우는 중 → 잠시 후 재조회하면 정밀해짐
  available?: boolean; // false = API 호출한도 초과 등 — "거래 없음"과 구분
  message?: string | null;
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
  realestateInterest: () => request<InterestBoard>(`/api/data/realestate-interest`),
  realestateInterestCollect: (months?: number) =>
    request<InterestCollectResult>(
      `/api/data/realestate-interest/collect${months ? `?months=${months}` : ""}`,
      { method: "POST" }),
  realestateDeals: (lawd: string, ym?: string) =>
    request<RealEstateDeals>(`/api/data/realestate-deals?lawd=${encodeURIComponent(lawd)}${ym ? `&ym=${ym}` : ""}`),
  realestateKinds: () => request<{ kinds: PropertyKindMeta[] }>(`/api/data/realestate-kinds`),
  realestateApartments: (
    lawd: string, ym?: string, trade: TradeKind = "sale", kind: PropertyKind = "apt",
  ) =>
    request<RealEstateApartments>(
      `/api/data/realestate-apartments?lawd=${encodeURIComponent(lawd)}${ym ? `&ym=${ym}` : ""}` +
      `&trade=${trade}&kind=${kind}`,
    ),
  realestateApartment: (lawd: string, apt: string, dong?: string, months = 120) =>
    request<RealEstateApartmentDetail>(
      `/api/data/realestate-apartment?lawd=${encodeURIComponent(lawd)}&apt=${encodeURIComponent(apt)}${
        dong ? `&dong=${encodeURIComponent(dong)}` : ""
      }&months=${months}`,
    ),
};

// --- 지도 주변시설(POI) — 네이버의 학군·교통 레이어 -------------------------
export interface PoiSchool {
  name: string;
  level: string;   // 초등학교 · 중학교 · 고등학교 · 특수학교
  kind: string;    // 초 · 중 · 고 (마커 배지)
  lat: number;
  lng: number;
  addr: string;
}

export interface PoiStation {
  name: string;
  line: string;
  lines: string[];   // 환승역이면 여러 노선
  transfer: boolean;
  lat: number;
  lng: number;
  addr: string;
}

export interface PoiResult<T> {
  available: boolean;   // false = reference JSON 미적재
  message: string | null;
  count: number;
  truncated: boolean;   // 범위 안이 너무 많아 잘림 — 더 확대하라는 신호
  items: T[];
}

export interface MapBounds {
  swLat: number;
  swLng: number;
  neLat: number;
  neLng: number;
}

function bbox(b: MapBounds): string {
  return `sw_lat=${b.swLat}&sw_lng=${b.swLng}&ne_lat=${b.neLat}&ne_lng=${b.neLng}`;
}

export const poiApi = {
  poiSchools: (b: MapBounds, levels?: string[]) =>
    request<PoiResult<PoiSchool>>(
      `/api/data/poi-schools?${bbox(b)}${levels?.length ? `&levels=${encodeURIComponent(levels.join(","))}` : ""}`,
    ),
  poiStations: (b: MapBounds) => request<PoiResult<PoiStation>>(`/api/data/poi-stations?${bbox(b)}`),
};
