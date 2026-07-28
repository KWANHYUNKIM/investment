// 관심종목 · 포트폴리오 진단

import { request } from "./client";

export interface WatchRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  close: number | null;
  chg_pct: number | null;
  verdict: string | null;
  score: number | null;
  target: number | null;
  upside_pct: number | null;
}

export interface Watchlist {
  tickers: string[];
  rows: WatchRow[];
}

export interface HoldingRow extends WatchRow {
  qty: number;
  avg: number;
  value: number;
  cost: number;
  pnl: number;
  pnl_pct: number | null;
  weight: number | null;
}

export interface Portfolio {
  holdings: HoldingRow[];
  summary: {
    total_value: number;
    total_cost: number;
    total_pnl: number;
    total_pnl_pct: number | null;
    max_weight: number;
    sectors: { sector: string; weight: number }[];
    count: number;
  };
  diagnosis: string[];
}

export const watchlistApi = {
  watchlist: () => request<Watchlist>(`/api/data/watchlist`),
  watchlistAdd: (ticker: string) => request<Watchlist>(`/api/data/watchlist/add?ticker=${ticker}`, { method: "POST" }),
  watchlistRemove: (ticker: string) => request<Watchlist>(`/api/data/watchlist/remove?ticker=${ticker}`, { method: "POST" }),
  portfolioDiag: () => request<Portfolio>(`/api/data/portfolio`),
  portfolioSave: (holdings: { ticker: string; qty: number; avg: number }[]) =>
    request<Portfolio>(`/api/data/portfolio`, { method: "POST", body: JSON.stringify(holdings) }),
};
