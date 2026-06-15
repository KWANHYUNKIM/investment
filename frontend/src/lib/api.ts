// Typed client for the Quant Investment FastAPI backend.
//
// The backend serves everything under /api and has CORS open to this dev
// origin (http://localhost:3000). Override the base with NEXT_PUBLIC_API_BASE
// if you run the API elsewhere.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(
      0,
      `백엔드에 연결할 수 없습니다 (${API_BASE}). 서버가 실행 중인지 확인하세요.`,
    );
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// --- Types mirroring the backend response shapes ----------------------------

export interface Health {
  status: string;
  data_dir: string;
}

export interface Coverage {
  market: string;
  tickers: number;
  first_date: string;
  last_date: string;
  rows: number;
}

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

export interface InvestorRow {
  date: string;
  individual: number | null;
  foreign: number | null;
  organ: number | null;
  foreign_ratio: number | null;
  close: number | null;
}
export interface InvestorResponse {
  ticker: string;
  rows: InvestorRow[];
}

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

export interface MoverRow {
  ticker: string;
  name: string | null;
  sector: string | null;
  close: number | null;
  change_pct: number | null;
  change: number | null;
  volume: number | null;
}
export interface FlowSeller {
  ticker: string;
  name: string | null;
  foreign: number | null;
  organ: number | null;
}
export interface InvestorDriver {
  type: string; // 외국인 / 개인 / 기관
  key: "foreign" | "individual" | "organ";
  action: string; // 순매수 / 순매도 / 관망 / 데이터 없음
  qty: number | null;
  reasons: string[];
}
export interface InsightNews {
  title: string | null;
  link: string | null;
  source: string | null;
}
export interface StockInsight {
  ticker: string;
  name: string | null;
  sector: string | null;
  close: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
  foreign_ratio: number | null;
  foreign_ratio_delta: number | null;
  investors: InvestorDriver[];
  news: InsightNews[];
}
export interface MarketReport {
  date: string | null;
  breadth: { up: number; down: number; flat: number; total: number };
  insights: StockInsight[];
  gainers: MoverRow[];
  losers: MoverRow[];
  most_traded: MoverRow[];
  foreign_sellers: FlowSeller[];
  organ_sellers: FlowSeller[];
  news: NewsItem[];
  summary: string;
}

export interface ReportResponse {
  ticker: string;
  name: string;
  price: {
    date?: string;
    close?: number;
    change?: number;
    change_pct?: number;
    high?: number;
    low?: number;
    volume?: number | null;
  };
  flow: {
    date?: string;
    individual?: number | null;
    foreign?: number | null;
    organ?: number | null;
    foreign_ratio?: number | null;
  };
  lead_seller: string | null;
  lead_buyer: string | null;
  summary: string;
  news: NewsItem[];
  note: string;
}

export interface NewsItem {
  title: string;
  link: string;
  source: string;
  ts: number | null;
  important: boolean;
}
export interface NewsResponse {
  domestic: NewsItem[];
  global: NewsItem[];
  cached: boolean;
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

// --- Endpoints --------------------------------------------------------------

export const api = {
  health: () => request<Health>("/api/health"),
  coverage: () => request<Coverage[]>("/api/data/coverage"),
  securities: (market?: string) =>
    request<Security[]>(`/api/data/securities${market ? `?market=${market}` : ""}`),
  quotes: (market?: string) =>
    request<Quote[]>(`/api/data/quotes${market ? `?market=${market}` : ""}`),
  screenTable: () => request<GridRow[]>(`/api/data/screen-table`),
  live: (market?: string) =>
    request<LiveSnapshot>(`/api/data/live${market ? `?market=${market}` : ""}`),
  news: (name: string, limit = 15) =>
    request<NewsResponse>(`/api/data/news?name=${encodeURIComponent(name)}&limit=${limit}`),
  investors: (ticker: string) => request<InvestorResponse>(`/api/data/investors?ticker=${ticker}`),
  report: (ticker: string, name?: string) =>
    request<ReportResponse>(`/api/data/report?ticker=${ticker}${name ? `&name=${encodeURIComponent(name)}` : ""}`),
  marketReport: () => request<MarketReport>(`/api/data/market-report`),
  holders: (ticker: string) => request<HoldersResponse>(`/api/data/holders?ticker=${ticker}`),
  fundamentals: (ticker: string) => request<FundamentalsResponse>(`/api/data/fundamentals?ticker=${ticker}`),
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
  screen: (body: ScreenRequest) =>
    request<ScreenResponse>("/api/screen", { method: "POST", body: JSON.stringify(body) }),
  backtest: (body: BacktestRequest) =>
    request<BacktestResponse>("/api/backtest", { method: "POST", body: JSON.stringify(body) }),
  portfolio: (body: PortfolioRequest) =>
    request<PortfolioResponse>("/api/portfolio", { method: "POST", body: JSON.stringify(body) }),
};
