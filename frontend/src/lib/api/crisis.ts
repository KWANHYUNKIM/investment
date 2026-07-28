// 금융위기 시뮬레이터 — 아날로그 예측 + 글로벌/한국 조기경보

import { request } from "./client";

// --- 금융위기 시뮬레이터 -----------------------------------------------------
export interface CrisisPoint {
  day: number; // 위기 후 거래일 오프셋 (Day0=0)
  v: number; // Day0=100 정규화 값
}

export interface CrisisMetricMeta {
  key: string; // fx / stock / bond
  label: string;
  direction: "down" | "up"; // down=아래로 붕괴, up=위로 붕괴(금리)
  desc: string;
}

export interface CrisisEpisodeMeta {
  key: string;
  label: string;
  day0: string;
  trigger: string;
  desc: string;
  color: string;
}

export interface CrisisMeta {
  metrics: CrisisMetricMeta[];
  crises: CrisisEpisodeMeta[];
  source: string;
  note: string;
}

export interface CrisisSeries {
  code: string;
  crisis: string;
  label: string;
  name: string;
  color: string;
  freq: string; // 일별 / 월별
  points: CrisisPoint[];
  extreme_day: number | null;
  extreme_v: number | null;
  depth_pct: number | null; // 붕괴 깊이 (음수=하락 / 양수=상승)
}

// 아날로그(현재가 과거 위기의 어느 시점과 닮았나).
export interface CrisisAnalog {
  crisis: string;
  crisis_label: string;
  color: string;
  corr: number; // 상관(-1~1)
  lead_days: number; // 위기까지 남은 일수(0=이미 발발 이후)
  phase: string; // "위기 51일 전" / "위기 후 132일"
}

export interface CrisisBest extends CrisisAnalog {
  expected_pct: number | null; // 역사 반복 시 horizon 내 예상 변화율
  horizon: number; // 예상 구간(일)
}

// 현재 지수 1개. 과거 위기 타임라인의 best 위치에 정렬된 현재선 + 이후 투영(예상 시나리오).
export interface CrisisCurrentLine {
  code: string;
  name: string;
  color: string;
  label: string;
  as_of: string;
  same_instrument: boolean;
  points: CrisisPoint[]; // best 아날로그 위치에 정렬된 현재 구간
  projection: CrisisPoint[]; // 그 위기의 이후 경로(예상 시나리오)
  best: CrisisBest | null;
  analogs: CrisisAnalog[]; // 닮은 위기 랭킹
}

export interface CrisisSim {
  metric: CrisisMetricMeta;
  crises: CrisisEpisodeMeta[];
  series: CrisisSeries[];
  currents: CrisisCurrentLine[];
  axis: { min_day: number; max_day: number };
}

// 위기 선행징후 (조기경보)
export interface CrisisWarnSign {
  key: string;
  label: string;
  value: number;
  unit: string;
  status: "ok" | "watch" | "alert";
  pre_crisis_avg: number | null; // 과거 위기 직전 평균
  desc: string;
  as_of: string;
  extra: string | null;
}

export interface CrisisWarning {
  score: number; // 0~100 종합 경보
  level: string; // 낮음/주의/경고/위험
  signs: CrisisWarnSign[];
  as_of: string | null;
  note: string;
}

// 한국 외환위기 선행징후 (김대종 교수 프레임)
export interface CrisisKrSign {
  key: string;
  label: string;
  value: number;
  unit: string;
  status: "ok" | "watch" | "alert";
  benchmark: number | null; // 교수 기준선(예: 환율 1500, 부채 60)
  desc: string;
  as_of?: string | null; // 기준 시점
  source?: string | null; // 출처(한국은행/FRED)
}

export interface CrisisKrSwap {
  label: string;
  status: "ok" | "watch" | "alert";
  note: string;
}

export interface CrisisKoreaWarning {
  score: number;
  level: string;
  signs: CrisisKrSign[];
  swaps: CrisisKrSwap[];
  as_of: string | null;
  reserves_as_of?: string | null;
  reserves_source?: string | null;
  frame: string;
  note: string;
}

// 국가별 거시지표 비교표
export interface CrisisCountryRow {
  country: string;
  iso: string;
  gdp_usd: number | null;
  gdp_year: string | null;
  gdp_growth: number | null;
  rate: number | null;
  cpi: number | null;
  unemployment: number | null;
  debt_gdp: number | null;
  current_account: number | null;
  population: number | null;
}

export interface CrisisCountries {
  countries: CrisisCountryRow[];
  as_of: string | null;
  note: string;
}

export const crisisApi = {
  crisisMeta: () => request<CrisisMeta>(`/api/crisis/meta`),
  crisisSim: (metric: string, crises?: string[]) => {
    const q = new URLSearchParams({ metric });
    if (crises && crises.length) q.set("crises", crises.join(","));
    return request<CrisisSim>(`/api/crisis/sim?${q.toString()}`);
  },
  crisisWarning: () => request<CrisisWarning>(`/api/crisis/warning`),
  crisisKoreaWarning: () => request<CrisisKoreaWarning>(`/api/crisis/korea-warning`),
  crisisCountries: () => request<CrisisCountries>(`/api/crisis/countries`),
};
