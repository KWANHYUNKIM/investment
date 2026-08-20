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

// 시군구 월별 추이 — 거래(후행)와 검색(선행)을 한 그래프에 겹쳐 시차를 본다.
//
// 금액의 뜻이 거래유형마다 다르다: 매매는 거래가, 전세·월세는 **보증금**이고,
// 월세만 평균 월세(avg_rent_manwon)가 따로 붙는다. 하나로 뭉개면 평균이 무의미해진다.
export interface AreaBucketStat {
  count: number;
  avg_eok: number | null;
}

export interface RegionMonth {
  ym: string;
  label: string;
  count: number;
  amount_eok: number;
  avg_eok: number | null;
  avg_rent_manwon: number | null;          // 월세일 때만
  by_area: Record<string, AreaBucketStat>; // "60~85" 등
  provisional: boolean;                    // 최근 2개월 — 신고 기한이 남아 계속 자란다
  interest: number | null;                 // 같은 달 검색 관심도(앵커 대비 배수)
}

export interface RegionSeries {
  lawd: string;
  trade: TradeKind;
  available: boolean;
  reason: string | null;
  months: RegionMonth[];
  buckets: string[];                       // 평형 구간 표시 순서
  interest: { rank: number; index: number; trend_pct: number | null; keyword: string } | null;
  coverage: { have: number; total: number; pct: number; months: number };
  note: string;
}

// 지역 상권 — 업종 구성이 그 동네가 무엇을 하는 곳인지를 말한다.
//
// work_index = (과학·기술 + 시설관리·임대) ÷ (교육 + 보건의료 + 수리·개인)
// 사무실이 있어야 존재하는 업종과 사람이 살아야 존재하는 업종의 비다.
// 실측: 중구 2.86 · 종로 1.74 · 강남 1.69 · 마포 1.27 · 강서 0.83 · 분당 0.61 · 노원 0.36
export interface CommerceCategory {
  code: string;
  name: string;
  count: number;
  share: number;   // %
}

export interface RegionCommerce {
  lawd: string;
  available: boolean;
  total: number;
  counts: CommerceCategory[];
  shares: Record<string, number>;
  work_index: number | null;
  character: "업무·상업" | "혼합" | "주거" | "자료 없음" | "판단 보류";
  note: string;
  coverage: { have: number; total: number; pct: number };
}

// 인구이동 — 가격은 결과고 이동은 원인에 가깝다.
//
// 20~34세를 따로 세는 이유: 전체는 늘어도 청년이 빠지는 동네가 실제로 있고,
// 그 둘이 가격에 다르게 작용한다(청년 유입은 임대·상권·신축 수요를 같이 끌고 온다).
export interface MigrationPartner {
  cd: string;
  name: string;
  total: number;
  young: number;
}

export interface MigrationPoint {
  ym: string;
  in: number;
  out: number;
  net: number;
  in_young: number;
  out_young: number;
  net_young: number;
}

export interface RegionMigration {
  lawd: string;
  code: string;
  available: boolean;
  months: string[];
  in_total: number;
  out_total: number;
  net: number;
  in_young: number;
  out_young: number;
  net_young: number;
  churn: number;
  net_rate: number;
  direction: "유입" | "유출" | "균형";
  young_direction: "청년 유입" | "청년 유출" | "균형";
  inbound: MigrationPartner[];
  outbound: MigrationPartner[];
  series: MigrationPoint[];
  note: string;
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
  realestateRegionSeries: (lawd: string, trade: TradeKind = "sale") =>
    request<RegionSeries>(`/api/data/realestate-region-series?lawd=${lawd}&trade=${trade}`),
  realestateMigration: (lawd: string, months = 3) =>
    request<RegionMigration>(`/api/data/realestate-migration?lawd=${lawd}&months=${months}`),
  realestateCommerce: (lawd: string) =>
    request<RegionCommerce>(`/api/data/realestate-commerce?lawd=${lawd}`),
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
