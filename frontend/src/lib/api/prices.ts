// 시세 — 종목목록·현재가·OHLC·실시간 스냅샷·엑셀 그리드

import { request } from "./client";

export interface Security {
  market: string;
  ticker: string;
  name: string | null;
  sector: string | null;
}

export interface PriceSeries {
  dates: string[];
  series: Record<string, (number | null)[]>;
}

export interface Quote {
  ticker: string;
  name: string | null;
  sector: string | null;
  date: string | null;
  close: number | null;
  volume: number | null;
  change: number | null;
  change_pct: number | null;
  change_1m_pct: number | null;
}

export interface GridRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  date: string;
  close: number | null;
  change: number | null;
  change_pct: number | null;
  ret_1w: number | null;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_6m: number | null;
  ret_12m: number | null;
  ret_ytd: number | null;
  vol: number | null;
  pct_from_high: number | null;
  volume: number | null;
  per: number | null;
  pbr: number | null;
  eps: number | null;
  bps: number | null;
  roe: number | null;
  div_yield: number | null;
  foreign_ratio: number | null;
  market_cap: number | null;
}

export interface OHLC {
  ticker: string;
  dates: string[];
  open: (number | null)[];
  high: (number | null)[];
  low: (number | null)[];
  close: (number | null)[];
  volume: (number | null)[];
}

export interface Metrics {
  cagr: number;
  volatility: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  calmar: number;
  win_rate: number;
  total_return: number;
}

export interface LiveQuote {
  ticker: string;
  name: string | null;
  sector: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
}

export interface LiveSnapshot {
  ts: number;
  as_of: string;
  stale_sec: number;
  count: number;
  quotes: LiveQuote[];
}

export const pricesApi = {
  securities: (market?: string) =>
    request<Security[]>(`/api/data/securities${market ? `?market=${market}` : ""}`),
  quotes: (market?: string) =>
    request<Quote[]>(`/api/data/quotes${market ? `?market=${market}` : ""}`),
  screenTable: () => request<GridRow[]>(`/api/data/screen-table`),
  live: (market?: string) =>
    request<LiveSnapshot>(`/api/data/live${market ? `?market=${market}` : ""}`),
  ohlc: (params: { ticker: string; start?: string; end?: string }) => {
    const q = new URLSearchParams({ ticker: params.ticker });
    if (params.start) q.set("start", params.start);
    if (params.end) q.set("end", params.end);
    return request<OHLC>(`/api/data/ohlc?${q.toString()}`);
  },
  prices: (params: { tickers: string; market?: string; start?: string; end?: string; field?: string }) => {
    const q = new URLSearchParams();
    q.set("tickers", params.tickers);
    if (params.market) q.set("market", params.market);
    if (params.start) q.set("start", params.start);
    if (params.end) q.set("end", params.end);
    if (params.field) q.set("field", params.field);
    return request<PriceSeries>(`/api/data/prices?${q.toString()}`);
  },
};
