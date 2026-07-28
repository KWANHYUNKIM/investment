// 거시 — 매크로/금리 레이어·크로스에셋·자금흐름·ECOS·통화량·실물경제·한국 경제흐름

import { request } from "./client";
import type { InsightNews, NewsItem } from "./market";

// --- Daily archive (persisted day-by-day report) ----------------------------
export interface MacroDriver {
  theme: string;
  direction: string; // 긍정 / 부정 / 중립
  count: number;
  regions?: Record<string, number>;
  headlines: InsightNews[];
  digest?: string[]; // 대표 내용 — cross-source content bullets
}

export interface RegionNews {
  region: string;
  count: number;
  news: NewsItem[];
}

export interface MacroLayer {
  drivers: MacroDriver[];
  news: NewsItem[];
  global_news?: NewsItem[];
  by_region?: RegionNews[];
  pool_size?: number;
  summary: string;
}

export interface RateMeeting {
  key: string;
  name: string;
  flag: string;
  next_date: string | null;
  next_label: string | null;
  d_day: number | null;
  prev_date: string | null;
  remaining_2026: number;
}

export interface RateLayer {
  schedule: RateMeeting[];
  outlook: InsightNews[];
  digest: string[];
  summary: string;
}

export interface CrossAsset {
  key: string;
  label: string;
  group: string;
  kind: string; // index / crypto / commodity / safe / yield / fx
  unit: string; // pt / usd / krw / pct
  value: number | null;
  change_pct: number | null;
  date: string | null;
}

export interface CrossAssetGroup {
  group: string;
  assets: CrossAsset[];
}

export interface MoneyFlow {
  verdict: string; // 위험선호 / 위험회피 / 혼조
  tone: string; // 긍정 / 부정 / 중립
  score: number;
  desc: string;
  metrics: { equities: number | null; crypto: number | null; gold: number | null; usdkrw: number | null };
  summary: string;
}

export interface CrossAssetLayer {
  groups: CrossAssetGroup[];
  flow: MoneyFlow;
  count: number;
  ts?: number;
  as_of?: string;
}

// 글로벌 자금 흐름 — 유동성 레짐 + 한국 외국인/국내 수급 + 크로스에셋 + 자산군별 자금 뉴스
export interface MoneyHeadline {
  title: string;
  link: string;
  source: string;
}

export interface MoneyCategory {
  key: string;
  label: string;
  icon: string;
  direction: "우호" | "경계" | "중립";
  pos: number;
  neg: number;
  count: number;
  headlines: MoneyHeadline[];
  digest: string[];
}

export interface MoneyKrDay {
  date: string;
  foreign: number | null;
  domestic: number | null;
  individual: number | null;
  organ: number | null;
}

export interface GlobalMoneyFlow {
  as_of: string;
  verdict: {
    liquidity: "완화" | "긴축" | "중립";
    liquidity_label: string;
    foreign_kr: "유입" | "이탈" | "중립";
    risk: string;
    narrative: string;
  };
  liquidity: {
    regime: string;
    tone: "완화" | "긴축" | "중립";
    ease: number;
    tight: number;
    count: number;
    headlines: MoneyHeadline[];
    digest: string[];
  };
  indicators: {
    key: string;
    label: string;
    value: number;
    unit: string;
    change: number | null;
    signal: string;
    desc: string;
  }[];
  regions: {
    region: string;
    label: string;
    flag: string;
    stance: "완화" | "긴축" | "중립";
    ease: number;
    tight: number;
    count: number;
    headlines: MoneyHeadline[];
  }[];
  rate_schedule: {
    key: string;
    flag: string;
    name: string;
    next_label: string | null;
    next_date: string | null;
    d_day: number | null;
    remaining_2026: number | null;
  }[];
  kr_capital: {
    series: MoneyKrDay[];
    latest: MoneyKrDay | null;
    foreign_direction: "유입" | "이탈" | "중립";
  };
  usdkrw: { value: number | null; change_pct: number | null } | null;
  cross_asset: {
    verdict: string | null;
    tone: string | null;
    desc: string | null;
    metrics: { equities: number | null; crypto: number | null; gold: number | null; usdkrw: number | null } | null;
    as_of: string | null;
  };
  categories: MoneyCategory[];
}

// 한국 경제 흐름 — 부동산/리츠·국채 ETF 자금 신호 + 부동산·국채 뉴스 동향
export interface KoreaFlowItem {
  key: string;
  label: string;
  code: string;
  group: "real_estate" | "bond";
  close: number | null;
  change_pct: number | null;
  ret_1w: number | null;
  ret_1m: number | null;
  ret_3m: number | null;
  pct_from_high: number | null;
  date: string;
}

export interface KoreaFlowNews {
  key: string;
  label: string;
  icon: string;
  lean: "긍정" | "부정" | "중립";
  pos: number;
  neg: number;
  count: number;
  headlines: { title: string; link: string; source: string }[];
  digest: string[];
}

export interface KoreaFlow {
  as_of: string | null;
  verdict: {
    real_estate_dir: "유입" | "이탈" | "중립";
    bond_dir: "유입" | "이탈" | "중립";
    real_estate_1m: number | null;
    bond_1m: number | null;
    narrative: string;
  };
  real_estate: KoreaFlowItem[];
  bonds: KoreaFlowItem[];
  news: KoreaFlowNews[];
  note: string;
}

// 전체 기업 실적
export interface KospiEarningRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  period: string;
  sales: number | null;
  op_profit: number | null;
  net_income: number | null;
  op_margin: number | null;
  op_yoy: number | null;
  per: number | null;
  pbr: number | null;
  roe: number | null;
  market_cap: number | null;
  close: number | null;
}

export interface KospiEarnings {
  generated_at: string;
  count: number;
  summary: { companies: number; profitable: number; profitable_pct: number | null; improving: number; improving_pct: number | null };
  companies: KospiEarningRow[];
  note: string;
}

// 한국경제 종합 진단
export interface DiagnosisAxis {
  key: string;
  title: string;
  status: "good" | "neutral" | "warn" | "na";
  status_label: string;
  color: string;
  headline: string;
  detail: string;
  metrics: { k: string; v: string }[];
}

export interface KoreaDiagnosis {
  available: boolean;
  reason?: string;
  generated_at: string;
  regime?: string;
  regime_color?: string;
  score?: number | null;
  score_label?: string;
  narrative?: string;
  axes: DiagnosisAxis[];
  source?: string;
  note?: string;
}

// 국내 거시지표 — 한국은행 ECOS (M2·가계신용·주택매매가격지수)
export interface EcosSeriesPoint {
  t: string;
  v: number;
}

export interface EcosSpan {
  from: string;
  to: string;
  first: number;
  last: number;
  n: number;
  kind: string;
  change_pct?: number | null;
  change_delta?: number | null;
}

export interface EcosIndicator {
  key: string;
  group: string;
  label: string;
  period: string;
  display: string;
  yoy: number | null;
  yoy_label: string;
  mom?: number | null;
  desc: string;
  kind: string;
  span: EcosSpan;
  series: EcosSeriesPoint[];
}

export interface EcosMacro {
  available: boolean;
  reason?: string;
  source?: string;
  indicators: EcosIndicator[];
}

// 통화량 장기·국가 비교 — 과거 위기(IMF·금융위기·코로나) + 해외 주요국
export interface MoneyGrowthPoint {
  year: number;
  growth: number | null;
}

export interface MoneyCountry {
  iso: string;
  name: string;
  currency: string;
  latest_year: number;
  latest: number;
  avg: number | null;
  avg_years: string;
  min: number | null;
  min_year: number | null;
  max: number | null;
  max_year: number | null;
  tone: "hot" | "cold" | "neutral";
  series: MoneyGrowthPoint[];
}

export interface MoneyCrisis {
  key: string;
  name: string;
  period: string;
  scope: string;
  tone: "hot" | "cold" | "mixed";
  kr_growth: MoneyGrowthPoint[] | null;
  us_growth: MoneyGrowthPoint[] | null;
  headline: string;
  narrative: string;
  lesson: string;
  data_note: string | null;
}

export interface MoneySupply {
  available: boolean;
  reason?: string;
  as_of?: string | null;
  source?: string;
  headline?: {
    kr_m2_display: string | null;
    kr_m2_period: string | null;
    kr_m2_yoy: number | null;
    us_m2_yoy: number | null;
  };
  verdict?: {
    stance: string;
    current: number | null;
    current_label: string;
    avg_20y: number | null;
    narrative: string;
  };
  crises: MoneyCrisis[];
  countries: MoneyCountry[];
  note?: string;
}

// 통화량 심층분석 — 마샬케이·실질통화량·신용 + 돈의 행선지 + 레짐
export interface AnalysisPoint {
  year: number;
  v: number;
}

export interface StructuralMetric {
  latest: number | null;
  latest_year?: number | null;
  avg?: number | null;
  trend?: string;
  max?: number | null;
  series: AnalysisPoint[];
}

export interface StructuralCountry {
  iso: string;
  name: string;
  latest_year: number;
  marshall_k: StructuralMetric;
  velocity: StructuralMetric;
  real_m2: StructuralMetric;
  credit_gdp: StructuralMetric;
}

export interface AssetLinkItem {
  key: string;
  label: string;
  from: number;
  to: number;
  series: AnalysisPoint[];
  m2_series: AnalysisPoint[];
  corr: number | null;
  asset_total_ret: number;
  m2_total_ret: number;
  outpaced: "asset" | "m2";
}

export interface AssetLink {
  assets: AssetLinkItem[];
  narrative: string;
  from: number;
  to: number;
}

export interface RealRate {
  policy: number;
  inflation: number | null;
  real: number;
  period: string;
}

export interface Regime {
  kr: RealRate | null;
  us: RealRate | null;
  us_recession_now: boolean | null;
  recessions: { start: string; end: string }[];
  narrative: string;
}

export interface MoneyAnalysis {
  available: boolean;
  reason?: string;
  as_of?: string;
  source?: string;
  structural: StructuralCountry[];
  asset_link: AssetLink | null;
  regime: Regime | null;
  note?: string;
}

// 실물경제 — 한국(ECOS) & 세계(World Bank)
export interface WorldEntity {
  iso: string;
  name: string;
  latest: number;
  latest_year: number;
  first_year: number;
  series: { year: number; v: number }[];
}

export interface WorldIndicator {
  key: string;
  label: string;
  unit: string;
  kind: string;
  desc: string;
  world_latest: number | null;
  world_year: number | null;
  entities: WorldEntity[];
}

export interface RealEconomy {
  available: boolean;
  reason?: string;
  as_of?: number | null;
  source?: string;
  korea: EcosIndicator[];
  world: WorldIndicator[];
  note?: string;
}

export const macroApi = {
  moneyFlow: () => request<GlobalMoneyFlow>(`/api/data/money-flow`),
  koreaFlow: () => request<KoreaFlow>(`/api/data/korea-flow`),
  koreaDiagnosis: () => request<KoreaDiagnosis>(`/api/data/korea-diagnosis`),
  kospiEarnings: () => request<KospiEarnings>(`/api/data/kospi-earnings`),
  ecosMacro: () => request<EcosMacro>(`/api/data/ecos-macro`),
  moneySupply: () => request<MoneySupply>(`/api/data/money-supply`),
  moneyAnalysis: () => request<MoneyAnalysis>(`/api/data/money-analysis`),
  realEconomy: () => request<RealEconomy>(`/api/data/real-economy`),
  crossAsset: () => request<CrossAssetLayer>(`/api/data/cross-asset`),
};
