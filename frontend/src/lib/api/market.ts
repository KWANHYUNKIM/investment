// 시장 — 커버리지·투자자 수급·기관 추적·뉴스·종목 리포트·자산 상세

import { request } from "./client";
import type { MacroDriver } from "./macro";

export interface Coverage {
  market: string;
  tickers: number;
  first_date: string;
  last_date: string;
  rows: number;
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
  news_global?: InsightNews[];
  brokers?: BrokerFlow;
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
  region?: string | null;
  cluster?: string[]; // related-coverage sub-headlines (대표 내용)
}

export interface BrokerHouse {
  name: string;
  volume: number | null;
  foreign: boolean;
}

export interface BrokerFlow {
  buy: BrokerHouse[];
  sell: BrokerHouse[];
  foreign: { buy: number | null; sell: number | null; net: number | null } | null;
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

export interface ForeignView {
  lean: string; // 긍정 / 부정 / 중립
  pos: number;
  neg: number;
  pool_size: number;
  summary: string;
  headlines: InsightNews[];
  digest: string[];
}

// 기관 수급 추적 — 언제 담고 던졌나 + 왜 팔았을지 추정
export interface InstFlowStock {
  ticker: string;
  name: string;
  sector: string | null;
  net_amt: number; // 기간 기관 순매수(억)
  buy_amt: number;
  sell_amt: number;
  recent_amt: number;
  days: number;
  price_chg: number | null; // 기간 주가 변화(%)
  foreign_net: number; // 같은 기간 외국인 순매수(억)
  max_buy: { date: string; amt: number };
  max_sell: { date: string; amt: number };
  behavior: string; // 매집 / 저가 매집 추정 / 이탈·분산 / 손절 추정
  change_pct: number | null;
  per: number | null;
  pbr: number | null;
  ret_1m: number | null;
  pct_from_high: number | null;
  why: string[];
}

export interface InstitutionalFlow {
  as_of: string;
  window_days: number;
  universe: number;
  accumulating: InstFlowStock[];
  distributing: InstFlowStock[];
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

// 실시간 시황 펄스 — 시황·분석 글 취합 → 분위기·드라이버·시간순 흐름
export interface PulseFlowItem {
  title: string;
  link: string;
  source: string;
  region: string | null; // 국내 / 해외
  lean: "긍정" | "부정" | "중립";
  ts: number | null;
  ago: string | null; // '방금' / '12분 전' …
  cluster: string[];
}

export interface LivePulse {
  as_of: string;
  pulse: {
    verdict: string; // 강세 분위기 / 약세 분위기 / 혼조
    tone: "긍정" | "부정" | "중립";
    score: number; // -100 ~ 100
    pos: number;
    neg: number;
    neutral: number;
    narrative: string;
  };
  drivers: MacroDriver[];
  flow: PulseFlowItem[];
  pool_size: number;
}

export interface AssetSession {
  date: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
  high_52w: number | null;
  low_52w: number | null;
  prev_close: number | null;
}

export interface AssetHistoryRow {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  change_pct: number | null;
  volume: number | null;
}

export interface AssetConstituent {
  symbol: string;
  name: string | null;
  sector: string | null;
}

export interface AssetDetail {
  key: string;
  label: string;
  symbol: string;
  group: string;
  unit: string;
  session: AssetSession;
  history: AssetHistoryRow[];
  constituents: AssetConstituent[];
  total_constituents: number;
}

export interface ConstituentQuote {
  symbol: string;
  close: number | null;
  change: number | null;
  change_pct: number | null;
  ret_1w: number | null;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_12m: number | null;
}

export const marketApi = {
  coverage: () => request<Coverage[]>("/api/data/coverage"),
  news: (name: string, limit = 15) =>
    request<NewsResponse>(`/api/data/news?name=${encodeURIComponent(name)}&limit=${limit}`),
  investors: (ticker: string) => request<InvestorResponse>(`/api/data/investors?ticker=${ticker}`),
  report: (ticker: string, name?: string) =>
    request<ReportResponse>(`/api/data/report?ticker=${ticker}${name ? `&name=${encodeURIComponent(name)}` : ""}`),
  marketReport: () => request<MarketReport>(`/api/data/market-report`),
  livePulse: () => request<LivePulse>(`/api/data/live-pulse`),
  institutional: () => request<InstitutionalFlow>(`/api/data/institutional`),
  assetDetail: (key: string, date?: string) =>
    request<AssetDetail>(
      `/api/data/asset-detail?key=${encodeURIComponent(key)}${date ? `&date=${encodeURIComponent(date)}` : ""}`,
    ),
  assetQuotes: (symbols: string[], date?: string) =>
    request<{ quotes: ConstituentQuote[] }>(
      `/api/data/asset-quotes?symbols=${encodeURIComponent(symbols.join(","))}${date ? `&date=${encodeURIComponent(date)}` : ""}`,
    ),
};
