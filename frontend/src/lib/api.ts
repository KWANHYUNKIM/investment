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
export interface ForeignView {
  lean: string; // 긍정 / 부정 / 중립
  pos: number;
  neg: number;
  pool_size: number;
  summary: string;
  headlines: InsightNews[];
  digest: string[];
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
export interface ArchiveStock extends StockInsight {
  why?: { direction: string; themes: string[] };
  depth?: "deep" | "bulk";
}
export interface DailyArchive {
  date: string | null;
  generated_at?: string;
  scope: { total: number; deep: number; deep_n: number };
  market: {
    breadth: { up: number; down: number; flat: number; total: number };
    summary: string;
    macro: MacroLayer;
    rates?: RateLayer | null;
    foreign_view?: ForeignView | null;
    cross_asset?: CrossAssetLayer | null;
  };
  movers: { gainers: MoverRow[]; losers: MoverRow[]; most_traded: MoverRow[] };
  stocks: ArchiveStock[];
}
export interface ArchiveDatesResponse {
  dates: string[];
  scheduler: Record<string, unknown>;
}

// --- Industry / competition map -------------------------------------------
export interface IndustryMember {
  ticker: string;
  name: string | null;
  products: string | null;
  region?: string | null;
  representative?: string | null;
  homepage?: string | null;
  market_cap: number | null;
  change_pct: number | null;
  fy?: string | null; // 최근 사업연도 (YYYY/MM)
  sales?: number | null; // 매출액 (억)
  op_profit?: number | null; // 영업이익 (억)
  net_income?: number | null; // 당기순이익 (억)
  op_margin?: number | null; // 영업이익률 (%)
  op_yoy?: number | null; // 영업이익 전년대비 (%)
}
export interface IndustryGroup {
  industry: string;
  count: number;
  market_cap: number;
  avg_change_pct: number | null;
  op_profit?: number | null; // 업종 합산 영업이익 (억)
  op_margin?: number | null; // 업종 영업이익률 (%)
  op_count?: number; // 실적 집계된 기업 수
  leader: string | null;
  members: IndustryMember[];
}
export interface IndustryIndexItem {
  industry: string;
  count: number;
  market_cap: number;
  avg_change_pct: number | null;
  op_profit?: number | null;
  op_margin?: number | null;
  op_count?: number;
  leader: string | null;
}
export interface ThemeItem {
  company: string;
  ticker: string | null;
  title: string;
  link: string | null;
  source: string | null;
  themes: string[];
}
export interface ThemeBucket {
  key: string;
  label: string;
  count: number;
  items: ThemeItem[];
}
export interface IndustryResearch {
  industry: string;
  leader: string | null;
  count: number;
  market_cap: number;
  analyzed: string[];
  competitors: { ticker: string; name: string | null; market_cap: number | null; products: string | null }[];
  themes: ThemeBucket[];
  summary: string;
}
export interface IndustriesIndexResponse {
  industries: IndustryIndexItem[];
  scheduler?: Record<string, unknown>;
}
export interface IndustryDetailResponse {
  group: IndustryGroup;
  research: IndustryResearch | null;
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

export interface GlobalMember {
  market: "KR" | "GL";
  code: string;
  name: string | null;
  country: string | null;
  market_cap_usd: number | null;
  revenue_usd?: number | null; // 매출액 (USD)
  op_profit_usd?: number | null; // 영업이익 (USD)
  net_income_usd?: number | null; // 순이익 (USD)
  op_margin: number | null; // 영업이익률 %
  net_margin?: number | null; // 순이익률 %
  gross_margin?: number | null; // 매출총이익률 %
  roe?: number | null; // ROE %
  debt_equity?: number | null; // 부채/자본 %
  pe?: number | null; // PER
  pb?: number | null; // PBR
  div_yield?: number | null; // 배당수익률 %
  fy?: string | null; // 기준 사업연도
  change_pct: number | null;
  note: string | null; // 주요제품 / 업종
}
export interface GlobalCluster {
  key: string;
  label: string;
  desc: string;
  count: number;
  kr_count: number;
  foreign_count: number;
  countries: string[];
  market_cap_usd: number;
  avg_op_margin: number | null;
  leader: string | null;
  members?: GlobalMember[];
}
export interface GlobalClustersResponse {
  clusters: GlobalCluster[];
  finnhub: boolean;
  foreign_loaded: number;
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
  crossAsset: () => request<CrossAssetLayer>(`/api/data/cross-asset`),
  assetDetail: (key: string) => request<AssetDetail>(`/api/data/asset-detail?key=${encodeURIComponent(key)}`),
  assetQuotes: (symbols: string[]) =>
    request<{ quotes: ConstituentQuote[] }>(`/api/data/asset-quotes?symbols=${encodeURIComponent(symbols.join(","))}`),
  industries: () => request<IndustriesIndexResponse>(`/api/data/industries`),
  industry: (name: string) =>
    request<IndustryDetailResponse>(`/api/data/industry?name=${encodeURIComponent(name)}`),
  dailyArchiveDates: () => request<ArchiveDatesResponse>(`/api/data/daily-archive/dates`),
  dailyArchive: (date?: string) =>
    request<DailyArchive>(`/api/data/daily-archive${date ? `?date=${encodeURIComponent(date)}` : ""}`),
  holders: (ticker: string) => request<HoldersResponse>(`/api/data/holders?ticker=${ticker}`),
  fundamentals: (ticker: string) => request<FundamentalsResponse>(`/api/data/fundamentals?ticker=${ticker}`),
  financials: (ticker: string) => request<FinancialsResponse>(`/api/data/financials?ticker=${ticker}`),
  dartFinancials: (ticker: string) => request<DartFinancials>(`/api/data/dart-financials?ticker=${ticker}`),
  globalClusters: () => request<GlobalClustersResponse>(`/api/data/global-clusters`),
  globalCluster: (key: string) => request<GlobalCluster>(`/api/data/global-cluster?key=${encodeURIComponent(key)}`),
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
