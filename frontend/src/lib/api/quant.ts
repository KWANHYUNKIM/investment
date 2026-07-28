// 퀀트 — 스크리닝·백테스트·포트폴리오 최적화

import { request } from "./client";
import type { Metrics } from "./prices";

export interface ScreenFilter {
  factor: string;
  min?: number | null;
  max?: number | null;
}

export interface ScreenFactor {
  factor: string;
  weight: number;
  direction?: number | null;
}

export interface ScreenRequest {
  market?: string | null;
  filters: ScreenFilter[];
  factors: ScreenFactor[];
  top_n: number;
  as_of?: string | null;
}

export type ScreenRow = Record<string, string | number | null> & {
  ticker: string;
  name: string | null;
  score: number;
};

export interface ScreenResponse {
  count: number;
  results: ScreenRow[];
}

export interface BacktestRequest {
  tickers: string[];
  market?: string | null;
  start?: string | null;
  end?: string | null;
  scheme: string;
  rebalance: string;
  cost_bps: number;
  lookback: number;
  benchmark?: string | null;
}

export interface BacktestResponse {
  dates: string[];
  equity_curve: number[];
  drawdown: number[];
  daily_returns: number[];
  metrics: Metrics;
  weights: Record<string, Record<string, number>>;
  rebalance_count: number;
  benchmark?: { equity_curve: number[]; metrics: Metrics };
}

export interface PortfolioRequest {
  tickers: string[];
  market?: string | null;
  start?: string | null;
  end?: string | null;
  scheme: string;
}

export interface PortfolioResponse {
  scheme: string;
  weights: Record<string, number>;
  metrics: Metrics;
}

export const quantApi = {
  screen: (body: ScreenRequest) =>
    request<ScreenResponse>("/api/screen", { method: "POST", body: JSON.stringify(body) }),
  backtest: (body: BacktestRequest) =>
    request<BacktestResponse>("/api/backtest", { method: "POST", body: JSON.stringify(body) }),
  portfolio: (body: PortfolioRequest) =>
    request<PortfolioResponse>("/api/portfolio", { method: "POST", body: JSON.stringify(body) }),
};
