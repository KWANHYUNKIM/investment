// 펀더멘털 — 재무지표·주요주주·재무제표(DART)

import { request } from "./client";

export interface FundSnapshot {
  date: string;
  per: number | null;
  pbr: number | null;
  eps: number | null;
  bps: number | null;
  roe: number | null;
  div_yield: number | null;
  market_cap: number | null;
  foreign_ratio: number | null;
  debt_ratio?: number | null; // 부채비율(총부채/자기자본 %) — DART 재무상태표 파생
}

export interface FundamentalsResponse {
  ticker: string;
  latest: FundSnapshot | null;
  prev: FundSnapshot | null;
  change: Record<string, number | null> | null;
  history: FundSnapshot[];
}

export interface Holder {
  name: string;
  ratio: number | null;
  shares: number | null;
  date: string | null;
  report_tp: string | null;
}

export interface HoldersResponse {
  ticker: string;
  available: boolean;
  reason?: string;
  holders: Holder[];
}

export interface FinancialRow {
  period: string; // 사업연도 YYYY/MM
  sales: number | null; // 매출액 (억)
  op_profit: number | null; // 영업이익 (억)
  net_income: number | null; // 당기순이익 (억)
  op_margin: number | null; // 영업이익률 (%)
}

export interface FinancialsResponse {
  ticker: string;
  rows: FinancialRow[];
}

export interface DartAccount {
  account_nm: string;
  ord: number;
  by_year: Record<string, number | null>; // 연도(YYYY) → 금액(원)
}

export interface DartStatement {
  sj_div: string; // BS/IS/CIS/CF/SCE
  label: string; // 재무상태표 등
  accounts: DartAccount[];
}

export interface DartFinancials {
  ticker: string;
  years: string[]; // 최신→과거
  statements: DartStatement[];
  available: boolean;
}

export const fundamentalsApi = {
  holders: (ticker: string) => request<HoldersResponse>(`/api/data/holders?ticker=${ticker}`),
  fundamentals: (ticker: string) => request<FundamentalsResponse>(`/api/data/fundamentals?ticker=${ticker}`),
  financials: (ticker: string) => request<FinancialsResponse>(`/api/data/financials?ticker=${ticker}`),
  dartFinancials: (ticker: string) => request<DartFinancials>(`/api/data/dart-financials?ticker=${ticker}`),
};
