// 스크리너 보드 — 투자점수 · 관리종목/상폐 위험 · 이익품질

import { request } from "./client";

export interface StockScoreRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  close: number | null;
  chg_pct: number | null;
  ret_1m: number | null;
  per: number | null;
  pbr: number | null;
  roe: number | null;
  div_yield: number | null;
  value_score: number | null;
  momentum_score: number | null;
  flow_score: number | null;
  total_score: number | null;
}

export interface StockScoreBoard {
  generated_at: string;
  count: number;
  weights: Record<string, number>;
  rows: StockScoreRow[];
  note: string;
}

export interface DelistingReason { sev: number; text: string; kind?: string }

export interface DelistingAlert {
  date: string;
  report_nm: string;
  sev: number;
  kind: string;
  rcept_no: string;
}

export interface DelistingRow {
  ticker: string;
  name: string;
  market: string;
  dept: string | null;
  level: number;
  level_name: string;
  designated: string | null;
  tech_special: boolean;
  reasons: DelistingReason[];
  consec_op_loss: number;
  latest_year: number | null;
  latest_op: number | null;
  latest_sales: number | null;
  impair_rate: number | null;
  equity: number | null;            // 최신 시점 자기자본 (코스닥 (B) 10억 요건)
  impair_basis: string | null;      // 잠식률 기준 시점 (FY2025말 / FY2025반기말)
  half_ready: boolean;              // 반기 자본계정 적재 여부
  market_cap: number | null;        // 비재무 요건: 시가총액(원)
  cap_days_below: number | null;    // 시총 기준 미달 연속 거래일
  vol_ratio: number | null;         // 월평균거래량 / 상장주식수(근사)
  alerts: DelistingAlert[];
}

export interface DelistingBoard {
  generated_at: string;
  count: number;
  summary: Record<string, number>;
  alerts_generated_at: string | null;
  market_class_ready: boolean;
  half_ready: number;               // 반기 자본계정이 적재된 종목 수
  market_stats_ready: number;       // 시총·거래량 통계가 계산된 종목 수
  rows: DelistingRow[];
  note: string;
}

export interface EqFlag { sev: number; kind: string; text: string; }

export interface EqRow {
  ticker: string;
  name: string;
  score: number;
  latest_year: number | null;
  rev: number | null;
  op: number | null;
  ni: number | null;
  rev_yoy: number | null;
  minor_eq_ratio: number | null;
  minor_ni_ratio: number | null;
  ctrl_equity: number | null;
  disposal_gain: number | null;
  sep_op: number | null;
  gross_margin: number | null;
  ar_ratio: number | null;
  capital: number | null;
  cap_impair_rate: number | null;
  flags: EqFlag[];
}

export interface EqBoard {
  generated_at: string;
  count: number;
  summary: Record<string, number>;
  rows: EqRow[];
  note: string;
}

export const screenerApi = {
  stockScore: () => request<StockScoreBoard>(`/api/data/stock-score`),
  delistingRisk: () => request<DelistingBoard>(`/api/data/delisting-risk`),
  earningsQuality: () => request<EqBoard>(`/api/data/earnings-quality`),
};
