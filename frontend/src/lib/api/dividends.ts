// 배당 — 배당주 보드·심층분석·배당왕/귀족·위기생존주·ETF·S&P 적립

import { request } from "./client";

export interface DividendRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  close: number | null;
  div_yield: number;
  per: number | null;
  roe: number | null;
}

export interface EarningRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  close: number | null;
  period: string;
  op_yoy: number;
  op_margin: number | null;
  op_profit: number | null;
}

export interface DividendsBoard {
  generated_at: string;
  dividends: DividendRow[];
  earnings: EarningRow[];
  note: string;
}

export interface DividendStock {
  ticker: string;
  name: string;
  sector: string | null;
  close: number;
  div_yield: number | null;
  dps: number | null;
}

export interface DividendUniverse {
  generated_at: string;
  count: number;
  stocks: DividendStock[];
  note: string;
}

// ── 종목 단위 배당 심층 분석 ──────────────────────────────────────────────
export interface DDMetric {
  series: { year: number; value: number; estimate: boolean }[];
  latest: { year: number; value: number } | null;
  trend: "증가" | "감소" | "정체" | null;
  unit: string;
  why: string;
  available?: boolean;
  note?: string;
}

export interface DDCrisisRow { year: number; dps: number | null; verdict: "증가" | "유지" | "삭감" | "중단" | null; }

export interface DDCrisis {
  key: string;
  label: string;
  rows: DDCrisisRow[];
  summary: string;
  min?: number | null;
  max?: number | null;
}

export interface DividendDetail {
  ticker: string;
  name: string | null;
  sector: string | null;
  market?: "KR" | "US";
  currency?: "KRW" | "USD";
  royalty?: { tier: string; tier_label: string; years: number | null } | null;
  close: number | null;
  generated_at: string;
  dividend: { dps: number | null; dps_estimated: boolean; div_yield: number | null; formula: string };
  checklist: {
    revenue: DDMetric;
    net_income: DDMetric;
    op_cash_flow: DDMetric;
    div_years: { value: number; window: [number, number] | null; why: string };
    div_growth: { cagr: number | null; series: { year: number; dps: number }[]; window: [number, number] | null; why: string };
    roe: DDMetric;
  } | null;
  crises: { available: boolean; name: string | null; notes: string | null; sources: string[]; crises: DDCrisis[] } | null;
  note: string;
}

// ── 배당왕·귀족·월배당 ────────────────────────────────────────────────────
export interface RoyaltyRow { ticker: string; name: string; sector?: string; type?: string; years?: number | null; yield?: number | null; freq?: string; }

export interface RoyaltyGroup { count: number; criteria: string; avg_yield: number | null; rows: RoyaltyRow[]; }

export interface MonthlyPortfolio {
  invest: number; blended_yield: number; annual_gross: number; annual_net: number;
  monthly_gross: number; monthly_net: number; n_holdings: number; note: string;
}

export interface DividendRoyalty {
  as_of: string;
  kings: RoyaltyGroup;
  aristocrats: RoyaltyGroup;
  monthly: RoyaltyGroup;
  portfolio?: MonthlyPortfolio;
  note: string;
}

// ── 위기를 이겨낸 우상향 배당주 ───────────────────────────────────────────
export interface SurvivorCrisis { key: string; label: string; drawdown: number | null; dividend: string; }

export interface SurvivorRow {
  ticker: string; name: string; sector: string | null; tier_label: string | null; years: number | null;
  multiple: number | null; cagr: number | null;
  index: { date: string; v: number }[];
  crises: SurvivorCrisis[];
}

export interface CrisisSurvivors {
  generated_at: string; start: string; benchmark: SurvivorRow | null;
  survivors: SurvivorRow[]; crises: { key: string; label: string }[]; note: string;
}

// ── 배당 ETF + S&P 적립 ───────────────────────────────────────────────────
export interface EtfRow {
  ticker: string; name: string; category: string; yield: number | null;
  div_cagr_5y: number | null; expense: number | null; inception: number | null;
  freq: string; strategy: string;
}

export interface EtfGroup { category: string; count: number; avg_yield: number | null; rows: EtfRow[]; }

export interface DividendEtfBoard { as_of: string; groups: EtfGroup[]; count: number; note: string; }

export interface SpDca {
  monthly: number; years: number; annual_return_pct: number; principal: number;
  future_value: number; gain: number; est_annual_dividend: number; est_monthly_dividend: number; note: string;
}

export const dividendsApi = {
  dividends: () => request<DividendsBoard>(`/api/data/dividends`),
  dividendUniverse: () => request<DividendUniverse>(`/api/data/dividend-universe`),
  dividendDetail: (ticker: string) => request<DividendDetail>(`/api/data/dividend-detail?ticker=${ticker}`),
  dividendRoyalty: (invest = 0) => request<DividendRoyalty>(`/api/data/dividend-royalty${invest > 0 ? `?invest=${invest}` : ""}`),
  crisisSurvivors: () => request<CrisisSurvivors>(`/api/data/crisis-survivors`),
  dividendEtf: () => request<DividendEtfBoard>(`/api/data/dividend-etf`),
  spDca: (monthly: number, years: number, annualReturn: number) =>
    request<SpDca>(`/api/data/sp-dca?monthly=${monthly}&years=${years}&annual_return=${annualReturn}`),
};
