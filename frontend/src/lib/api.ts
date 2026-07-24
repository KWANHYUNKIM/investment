// Typed client for the Quant Investment FastAPI backend.
//
// The backend serves everything under /api and has CORS open to this dev
// origin (http://localhost:3000). Override the base with NEXT_PUBLIC_API_BASE
// if you run the API elsewhere.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

const TOKEN_KEY = "auth_token";
export function getToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
}
export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}
export function authHeader(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}
function on401() {
  setToken(null);
  if (typeof window !== "undefined") window.dispatchEvent(new Event("auth-expired"));
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...authHeader(), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(
      0,
      `백엔드에 연결할 수 없습니다 (${API_BASE}). 서버가 실행 중인지 확인하세요.`,
    );
  }
  if (!res.ok) {
    if (res.status === 401) on401();
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
// 시장 전체 투자자별 매매 동향(일단위) — 순매수 금액(억원) + 수량
export interface InvestorDay {
  date: string;
  foreign: number | null; // 외국인 순매수 (억원)
  individual: number | null; // 개인 순매수 (억원)
  organ: number | null; // 기관 순매수 (억원)
  foreign_qty: number | null;
  individual_qty: number | null;
  organ_qty: number | null;
  stocks: number; // 집계 종목 수
}
export interface DailyArchive {
  date: string | null;
  generated_at?: string;
  scope: { total: number; deep: number; deep_n: number };
  market: {
    breadth: { up: number; down: number; flat: number; total: number };
    summary: string;
    data_freshness?: {
      report_generated: string | null;
      price_date: string | null;
      investor_date: string | null;
      cross_asset_as_of: string | null;
      macro_pool: number | null;
    };
    investor_trend?: InvestorDay[];
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
export interface PremarketSignal {
  key: string;
  label: string;
  group: string;
  unit: string;
  weight: number;
  direction: number;
  value: number;
  change_pct: number;
  date: string;
  impact_pct: number;
}
export interface PremarketAdr {
  ticker: string;
  name: string;
  value: number;
  change_pct: number;
  date: string;
}
export interface PremarketAi {
  bias: string;
  one_liner: string;
  narrative: string;
  sectors: { name: string; view: string }[];
  risks: string[];
  confidence: string;
  model: string;
}
export interface PremarketIndex {
  key: string;
  label: string;
  close: number;
  change_pct: number | null;
  change_5d: number | null;
  change_20d: number | null;
  ma20: number;
  vs_ma20_pct: number | null;
  trend: string;
  series: { date: string; close: number }[];
}
export interface Premarket {
  generated_at: string;
  signals: PremarketSignal[];
  adrs: PremarketAdr[];
  indices: PremarketIndex[];
  bias: "강세" | "중립" | "약세";
  tone: string;
  weighted_pct: number;
  gauge: number;
  expected_gap: { low: number; high: number };
  adr_avg: number | null;
  drivers: string[];
  ai: PremarketAi | null;
  ai_error: string | null;
  ai_enabled: boolean;
}

export interface TargetPriceScenario {
  name: string;
  r: number;
  per_mult: number;
  target: number | null;
  upside_pct: number | null;
  methods: Record<string, number>;
}
export interface TargetPriceAi {
  fair_value: number;
  targets: Record<string, number>;
  rationale: string;
  key_drivers: string[];
  confidence: string;
  model: string;
}
export interface TargetPrice {
  ticker: string;
  close: number | null;
  fundamentals: Record<string, number | null>;
  per_median?: number | null;
  target_per_used?: number;
  base: number | null;
  base_upside_pct?: number | null;
  scenarios: TargetPriceScenario[];
  note: string;
  ai: TargetPriceAi | null;
  ai_error: string | null;
  ai_enabled: boolean;
}

export interface TradeSignalItem {
  name: string;
  score: number;
  view: string;
}
export interface TradeSignals {
  ticker: string;
  date?: string;
  close?: number;
  verdict: "매수" | "중립" | "매도" | null;
  tone?: string;
  score?: number;
  rsi?: number | null;
  ma5?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ma_arrange?: string;
  cross?: string | null;
  macd_hist?: number | null;
  bb_pct?: number | null;
  vol_ratio?: number | null;
  pos_52w?: number | null;
  atr?: number | null;
  risk?: {
    stop_loss: number | null;
    target1: number | null;
    target2: number | null;
    risk_reward: number | null;
    support: number | null;
    resistance: number | null;
  };
  signals: TradeSignalItem[];
  backtest?: {
    trades: number;
    win_rate: number | null;
    strat_return_pct: number | null;
    bh_return_pct: number | null;
    avg_trade_pct: number | null;
    open_position: boolean;
  } | null;
  note?: string;
}

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

// ── 관리자 ────────────────────────────────────────────────────────────────
export interface Me { username: string; is_admin: boolean; }
export interface BlogPost { title: string; markdown: string; html: string; tags: string[]; generated_at: string; }
// 자동 발행되어 data/blog_posts 에 보관된 글
export interface BlogSavedPost extends BlogPost {
  date: string; kind: string; saved_at?: string; reused?: boolean;
  path?: string; markdown_path?: string; available?: boolean; reason?: string;
}
export interface BlogPostListItem {
  date: string; kind: string; title: string; tags: string[];
  saved_at: string; chars: number; sections: number; file: string;
}
export interface BlogSchedulerStatus {
  running: boolean; enabled: boolean; schedule: string;
  posts: number; last_run: string | null; last_post_date: string | null;
  last_title: string | null; skipped_reason: string | null; last_error: string | null;
  latest_post: { date?: string; title?: string; saved_at?: string } | null;
}
export interface AdminUser { username: string; email: string | null; name: string | null; created: number | null; is_admin: boolean; }
export interface AdminStatus {
  coverage: { market: string; tickers: number; rows: number; first_date: string; last_date: string }[];
  price_scheduler: Record<string, unknown>;
  report_scheduler: Record<string, unknown>;
  fundamentals_crawler: Record<string, unknown>;
  dart_enabled: boolean;
}
export interface VisitorStats {
  total: number; today: number;
  top_views: { view: string; count: number }[];
  daily: { date: string; count: number }[];
}
export interface Curation { headline: string; picks: string[]; note: string; updated_at: string | null; }

export interface BudgetIncome {
  monthly_net: number;
  extra: number;
  memo: string;
}
export interface BudgetTx {
  id: number;
  date: string;
  merchant: string;
  amount: number;
  category: string;
}
export interface BudgetSummary {
  month: string;
  months: string[];
  income: BudgetIncome;
  income_total: number;
  spent: number;
  refund: number;
  savings_possible: number;
  savings_rate: number | null;
  by_category: { category: string; amount: number; pct: number }[];
  categories: string[];
  count: number;
  transactions: BudgetTx[];
}
export interface BudgetPlan {
  income_total: number;
  avg_spend: number;
  surplus: number;
  savings_rate: number | null;
  emergency_months: number;
  emergency_target: number;
  invest_ratio: number;
  monthly_save: number;
  monthly_invest: number;
  stock_value: number;
  allocation: { name: string; monthly: number }[];
  steps: string[];
  note: string;
}

export interface SalaryItem { label: string; amount: number }
export interface SalaryComputed {
  earnings: SalaryItem[];
  deductions: SalaryItem[];
  memo: string;
  gross: number;
  deduction: number;
  net: number;
  annual_net: number;
  annual_gross: number;
  updated: string | null;
}
export interface SalaryHistory { date: string; gross: number; net: number; annual_net: number }
export interface RaiseSim {
  base_net: number; new_net: number; monthly_increase: number; annual_increase: number;
  years: number; invest_ratio: number; annual_return: number;
  invest_monthly: number; contributed: number; future_value: number; investment_gain: number; note: string;
}
export interface SideRow { id: number; date: string; source: string; amount: number; memo: string }
export interface SideList {
  month: string | null; months: string[]; rows: SideRow[];
  month_total: number; total: number; sources: { source: string; amount: number }[];
}
export interface IncomeOverview {
  salary: SalaryComputed | null;
  side: { this_month: number; total: number; count: number };
  investment: { value: number; pnl: number; pnl_pct: number | null };
  total_month_income: number;
  annual_est: number;
  tips: string[];
}

export interface WealthProduct {
  name: string;
  category: string;
  eligible: boolean;
  cond: string;
  benefit: string;
  cap: number;
  priority: number;
  link: string;
  example: string;
}
export interface WealthPlan {
  profile: Record<string, unknown>;
  goal: { amount: number; years: number };
  required_monthly: number;
  capacity_monthly: number;
  feasible: boolean | null;
  shortfall: number;
  reach_years: number | null;
  assumed_return: number;
  scenarios: {
    key: string; name: string; desc: string; safety: string; risk: string;
    return_mid: number; return_low: number; return_high: number;
    balance_at_goal_years: number; balance_low: number; balance_high: number;
    reach_years: number | null; reach_years_low: number | null; reach_years_high: number | null;
    time_saved_vs_safe: number | null; recommended: boolean;
  }[];
  projection: { year: number; balance: number }[];
  products: WealthProduct[];
  eligible_count: number;
  allocation: { name: string; monthly: number; category: string; why: string }[];
  steps: string[];
  note: string;
}

export interface LoanSim {
  loan_amount: number; loan_rate: number; loan_years: number; invest_return: number;
  monthly_payment: number; total_repay: number; total_interest: number;
  invest_value: number; net_profit: number; worthwhile: boolean;
  breakeven_return: number | null;
  scenarios: { name: string; return: number; invest_value: number; net_profit: number; worthwhile: boolean }[];
  loans: { name: string; rate: number; note: string }[];
  verdict: string; warning: string;
}

export interface RealtySim {
  mode: string; price: number; own_capital: number; loan: number; loan_rate: number; years: number; appreciation: number;
  deposit: number; rent_monthly: number; monthly_interest: number; monthly_cashflow: number;
  rent_yield_on_capital: number | null; total_interest: number;
  future_price: number; sale_gain: number; net_profit: number; roe: number | null; roe_no_leverage: number;
  scenarios: { name: string; appreciation: number; future_price: number; sale_gain: number; net_profit: number; roe: number | null }[];
  note: string; warning: string;
}

export interface BriefSignal { key: string; label: string; group?: string; change_pct: number | null; last?: number | null; }
export interface BriefADR { name: string; ticker?: string; change_pct: number; }
export interface BriefStory { topic: string; title: string; source: string | null; link: string; ts: number | null; }
export interface BriefOutlook {
  market: string; bias: string | null; gauge: number | null;
  expected_gap: { low?: number; high?: number }; drivers: string[]; basis: string;
}
export interface BriefNarrative { headline?: string; recap?: string[]; outlook?: string; risks?: string[]; one_liner?: string; source?: string; }
export interface Briefing {
  generated_at: string; market: string; market_label: string;
  signals: BriefSignal[]; adrs: BriefADR[]; extras: Record<string, { name?: string; change_pct?: number } | undefined>;
  flow: unknown; stories: BriefStory[]; outlook: BriefOutlook; narrative: BriefNarrative;
  ai_enabled: boolean; note: string;
}

export interface MoverNews { title: string; source: string; link: string; ts: number | null; }
export interface Mover {
  ticker: string; name: string; sector: string; close: number; change_pct: number; value: number; news: MoverNews[];
}
export interface MoverSector {
  sector: string; avg_change_pct: number; count: number; advancers: number; decliners: number;
  leaders: { name: string; ticker: string; change_pct: number }[];
}
export interface MoversAI { overall?: string; losers_cause?: string; gainers_cause?: string; drivers?: string[]; model?: string; }
export interface Movers {
  generated_at: string; count: number; breadth?: { advancers: number; decliners: number }; threshold?: number;
  gainers: Mover[]; losers: Mover[]; sectors_up: MoverSector[]; sectors_down: MoverSector[];
  ai: MoversAI | null; ai_enabled: boolean; note: string;
}
export interface MoversHistoryItem {
  generated_at: string; breadth?: { advancers: number; decliners: number };
  gainers: { name: string; change_pct: number }[]; losers: { name: string; change_pct: number }[];
  sector_up: string | null; sector_down: string | null;
  overall?: string | null; losers_cause?: string | null; gainers_cause?: string | null;
}

export interface RealtyLoan {
  name: string; kind: string; rate: number; limit: number | null; eligible: boolean; cond: string; note: string;
}
export interface RealtyLoans {
  price: number; annual_income: number; mode: string; ltv_pct: number;
  loans: RealtyLoan[]; eligible_count: number; max_limit: number; dsr_note: string; note: string;
}

export interface HoldingCatalogItem {
  name: string; category: string; benefit: string; example: string; rate: number; bonus_note: string; has_bonus: boolean;
}
export interface HoldingItem {
  name: string; category: string; monthly: number; current: number; rate: number; bonus_note: string;
  principal: number; invest_value: number; bonus_total: number; total: number; gain: number;
  yearly: { year: number; total: number }[];
}
export interface HoldingsData {
  holdings: { name: string; monthly: number; current: number }[];
  horizon: number;
  catalog: HoldingCatalogItem[];
  projection: {
    horizon: number;
    items: HoldingItem[];
    totals_by_year: { year: number; total: number }[];
    summary: { monthly_sum: number; principal: number; bonus_total: number; gain: number; total: number };
    note: string;
  };
}

export interface DividendSim {
  invest: number; yield_pct: number; years: number; growth_pct: number; reinvest: boolean; tax_pct: number;
  annual_gross: number; annual_net: number; monthly_net: number; final_value: number; total_dividends_net: number;
  yearly: { year: number; dividend_net: number; cum_net: number; value: number }[];
  targets: { monthly: number; invest: number }[];
  examples: { name: string; yield: string; note: string }[];
  guide: string[]; note: string;
}
export interface IpoSim {
  offer_price: number; alloc_shares: number; cost: number; subscribe_amount: number; margin_estimate: number;
  scenarios: { gain_pct: number; sell_price: number; profit: number; roi_on_cost: number | null }[];
  guide: string[]; note: string;
}

export interface DividendPick {
  ticker: string; name: string; sector: string | null; close: number | null;
  div_yield: number; per: number | null; pbr: number | null; roe: number | null;
  market_cap: number | null; foreign_ratio: number | null; op_yoy: number | null;
  score: number; grade: string; reasons: string[]; stability: string; cycle: string;
  monthly_per_10m: number; naver_url: string;
}
export interface DividendPicks { generated_at: string; picks: DividendPick[]; guide: string[]; note: string; }
export interface IpoScheduleItem {
  no?: string; name: string; subscribe: string; status: string; price_confirmed: string | null; price_band: string; underwriter: string;
  market?: string; shares?: string; offer_amount_text?: string; offer_amount_won?: number | null;
  listing_date?: string; demand_competition?: string; lockup?: string; detail_url?: string;
}
export interface IpoSchedule {
  items: IpoScheduleItem[]; upcoming_count: number; source: string; generated_at: string; error?: string; guide?: string[]; note: string;
}

export interface PayslipParse {
  filename: string;
  net: number | null;
  gross: number | null;
  deduction: number | null;
  guessed: boolean;
  candidates: { label: string; amount: number }[];
  note: string;
}

export interface PremarketRecord {
  based_on: string;
  made_at: string;
  prediction: {
    bias: string;
    weighted_pct: number;
    gauge: number;
    expected_gap: { low: number; high: number };
    adr_avg: number | null;
    drivers: string[];
    ai_one_liner: string | null;
  };
  graded: boolean;
  hit?: boolean;
  reason?: string;
  actual: {
    open_date: string;
    kospi_gap: number;
    kosdaq_gap: number | null;
    direction: string;
  } | null;
}
export interface PremarketHistory {
  accuracy: {
    total: number;
    hits: number;
    rate: number | null;
    recent10_hits: number;
    recent10_total: number;
    pending: number;
  };
  records: PremarketRecord[];
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

// 부동산 실거래 — 국토부 RTMS (서울 25개구 아파트 매매 월별 거래량·거래대금)
export interface RealEstateMonth {
  ym: string;
  label: string;
  count: number;
  amount_eok: number;
  provisional: boolean; // 신고 진행중(잠정) — 보통 당월
}
export interface RealEstateSido {
  sido: string;
  count: number;
  amount_eok: number;
}
export interface RealEstateSigungu {
  region: string;
  sido: string;
  count: number;
  amount_eok: number;
}
export interface RealEstateTrades {
  available: boolean;
  reason?: string;
  scope: string;
  source?: string;
  latest_ym?: string;
  latest_label?: string;
  latest_count?: number;
  latest_amount_eok?: number;
  mom_count_pct?: number | null;
  region_ym?: string;
  monthly: RealEstateMonth[];
  by_sido: RealEstateSido[];
  top_sigungu: RealEstateSigungu[];
  partial?: boolean;
}

// 부동산 전월세 실거래 — 국토부 RTMS (전국 아파트 전월세)
export interface RentMonth {
  ym: string;
  label: string;
  count: number;
  jeonse: number;
  wolse: number;
  wolse_ratio: number | null;
  avg_jeonse_eok: number | null;
  provisional: boolean;
}
export interface RentSido {
  sido: string;
  count: number;
  wolse_ratio: number | null;
  avg_jeonse_eok: number | null;
}
export interface RealEstateRent {
  available: boolean;
  reason?: string;
  scope: string;
  source?: string;
  latest_ym?: string;
  latest_label?: string;
  latest_count?: number;
  latest_jeonse?: number;
  latest_wolse?: number;
  latest_wolse_ratio?: number | null;
  latest_avg_jeonse_eok?: number | null;
  mom_count_pct?: number | null;
  region_ym?: string;
  monthly: RentMonth[];
  by_sido: RentSido[];
  partial?: boolean;
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

// 미래 성장테마 — 메가트렌드 동향 + 매핑 종목(미래가치 후보)
export interface FutureThemeMember {
  ticker: string;
  name: string | null;
  products: string | null;
  wics_sector: string | null;
  market_cap: number | null;
  close: number | null;
  change_pct: number | null;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_12m: number | null;
  pct_from_high: number | null;
  per: number | null;
  pbr: number | null;
  beaten: boolean; // 최근 하락(파란) = 미래가치 후보
}
export interface FutureThemeNews {
  count: number;
  pos: number;
  neg: number;
  lean: "긍정" | "부정" | "중립";
  headlines: { title: string; link: string; source: string }[];
  digest: string[];
}
export interface FutureThemeIndexItem {
  key: string;
  label: string;
  icon: string;
  desc: string;
  momentum_score: number;
  member_count: number;
  beaten_count: number;
  news_count: number;
  lean: "긍정" | "부정" | "중립";
}
export interface FutureTheme {
  key: string;
  label: string;
  icon: string;
  desc: string;
  news: FutureThemeNews;
  momentum_score: number;
  member_count: number;
  beaten_count: number;
  members: FutureThemeMember[];
}
export interface FutureThemesResponse {
  themes: FutureThemeIndexItem[];
}
export interface FutureThemesStatus {
  running: boolean;
  ticks: number;
  theme_refreshes: number;
  snapshots: number;
  last_run: string | null;
  last_snapshot_date: string | null;
  last_error: string | null;
  interval_sec: number;
  snapshot_dates: string[];
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
  per?: number | null; // PER (배) — 같은 업종 내 밸류 비교
  pbr?: number | null; // PBR (배)
  roe?: number | null; // ROE (%)
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

// 기업 프로파일 — 기술/사업모델/해자/투자 (정성 큐레이션)
export interface GlobalProfile {
  tech?: string; // 핵심 기술/제품
  biz?: string; // 영업이익을 어떻게 내는지
  moat?: string; // 경쟁 우위/해자
  invest?: string; // R&D·CAPEX 투자와 그 회수
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
  // 투자효율 (이익/투자 대비)
  roic?: number | null; // 투하자본이익률 %
  roa?: number | null; // 총자산이익률 %
  asset_turnover?: number | null; // 자산회전율 (배)
  ev_ebitda?: number | null; // EV/EBITDA (배)
  rev_growth?: number | null; // 매출성장률 YoY %
  eps_growth?: number | null; // EPS성장률 YoY %
  rev_cagr5y?: number | null; // 5년 매출 CAGR %
  interest_cov?: number | null; // 이자보상배율 (배)
  op_yoy?: number | null; // 영업이익 YoY % (한국)
  fy?: string | null; // 기준 사업연도
  change_pct: number | null;
  note: string | null; // 주요제품 / 업종
  profile?: GlobalProfile | null;
}
export interface GlobalBattleground {
  arena: string; // 세부 전장 이름
  desc: string; // 경쟁 구도 설명
  players: string[]; // 주요 선수
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
  tech?: boolean; // 기술주 클러스터
  battleground_count?: number; // index용
  battlegrounds?: GlobalBattleground[]; // detail용
  members?: GlobalMember[];
}
export interface GlobalClustersResponse {
  clusters: GlobalCluster[];
  finnhub: boolean;
  foreign_loaded: number;
}

// --- 금융위기 시뮬레이터 -----------------------------------------------------
export interface CrisisPoint {
  day: number; // 위기 후 거래일 오프셋 (Day0=0)
  v: number; // Day0=100 정규화 값
}
export interface CrisisMetricMeta {
  key: string; // fx / stock / bond
  label: string;
  direction: "down" | "up"; // down=아래로 붕괴, up=위로 붕괴(금리)
  desc: string;
}
export interface CrisisEpisodeMeta {
  key: string;
  label: string;
  day0: string;
  trigger: string;
  desc: string;
  color: string;
}
export interface CrisisMeta {
  metrics: CrisisMetricMeta[];
  crises: CrisisEpisodeMeta[];
  source: string;
  note: string;
}
export interface CrisisSeries {
  code: string;
  crisis: string;
  label: string;
  name: string;
  color: string;
  freq: string; // 일별 / 월별
  points: CrisisPoint[];
  extreme_day: number | null;
  extreme_v: number | null;
  depth_pct: number | null; // 붕괴 깊이 (음수=하락 / 양수=상승)
}
// 아날로그(현재가 과거 위기의 어느 시점과 닮았나).
export interface CrisisAnalog {
  crisis: string;
  crisis_label: string;
  color: string;
  corr: number; // 상관(-1~1)
  lead_days: number; // 위기까지 남은 일수(0=이미 발발 이후)
  phase: string; // "위기 51일 전" / "위기 후 132일"
}
export interface CrisisBest extends CrisisAnalog {
  expected_pct: number | null; // 역사 반복 시 horizon 내 예상 변화율
  horizon: number; // 예상 구간(일)
}
// 현재 지수 1개. 과거 위기 타임라인의 best 위치에 정렬된 현재선 + 이후 투영(예상 시나리오).
export interface CrisisCurrentLine {
  code: string;
  name: string;
  color: string;
  label: string;
  as_of: string;
  same_instrument: boolean;
  points: CrisisPoint[]; // best 아날로그 위치에 정렬된 현재 구간
  projection: CrisisPoint[]; // 그 위기의 이후 경로(예상 시나리오)
  best: CrisisBest | null;
  analogs: CrisisAnalog[]; // 닮은 위기 랭킹
}
export interface CrisisSim {
  metric: CrisisMetricMeta;
  crises: CrisisEpisodeMeta[];
  series: CrisisSeries[];
  currents: CrisisCurrentLine[];
  axis: { min_day: number; max_day: number };
}
// 위기 선행징후 (조기경보)
export interface CrisisWarnSign {
  key: string;
  label: string;
  value: number;
  unit: string;
  status: "ok" | "watch" | "alert";
  pre_crisis_avg: number | null; // 과거 위기 직전 평균
  desc: string;
  as_of: string;
  extra: string | null;
}
export interface CrisisWarning {
  score: number; // 0~100 종합 경보
  level: string; // 낮음/주의/경고/위험
  signs: CrisisWarnSign[];
  as_of: string | null;
  note: string;
}
// 한국 외환위기 선행징후 (김대종 교수 프레임)
export interface CrisisKrSign {
  key: string;
  label: string;
  value: number;
  unit: string;
  status: "ok" | "watch" | "alert";
  benchmark: number | null; // 교수 기준선(예: 환율 1500, 부채 60)
  desc: string;
  as_of?: string | null; // 기준 시점
  source?: string | null; // 출처(한국은행/FRED)
}
export interface CrisisKrSwap {
  label: string;
  status: "ok" | "watch" | "alert";
  note: string;
}
export interface CrisisKoreaWarning {
  score: number;
  level: string;
  signs: CrisisKrSign[];
  swaps: CrisisKrSwap[];
  as_of: string | null;
  reserves_as_of?: string | null;
  reserves_source?: string | null;
  frame: string;
  note: string;
}
// 국가별 거시지표 비교표
export interface CrisisCountryRow {
  country: string;
  iso: string;
  gdp_usd: number | null;
  gdp_year: string | null;
  gdp_growth: number | null;
  rate: number | null;
  cpi: number | null;
  unemployment: number | null;
  debt_gdp: number | null;
  current_account: number | null;
  population: number | null;
}
export interface CrisisCountries {
  countries: CrisisCountryRow[];
  as_of: string | null;
  note: string;
}
// 부동산 실거래 지도
export interface RealEstateRegion {
  region: string;
  sido: string;
  lawd: string;
  count: number;
  amount_eok: number;
  avg_eok: number | null;
  lat: number;
  lng: number;
  approx: boolean; // true=시도 중심 근사(지오코딩 미완)
}
export interface RealEstateMapData {
  ready: boolean; // 실거래 데이터가 채워졌는지 (false여도 지도는 표시)
  warming: boolean;
  message: string | null; // 수집중/안내 메시지
  source?: string;
  latest_label?: string | null;
  region_ym?: string | null;
  count?: number;
  geocoded?: number;
  regions: RealEstateRegion[];
  note?: string;
}
export interface RealEstateDeal {
  apt: string;
  dong: string;
  area: number | null;
  amount_eok: number;
  floor: string | null;
  build_year: string | null;
  date: string;
}
export interface RealEstateDeals {
  lawd: string;
  count: number;
  deals: RealEstateDeal[];
}
export interface RealEstateApartment {
  apt: string;
  dong: string;
  count: number;
  recent_eok: number;
  recent_area: number | null;
  recent_date: string;
  recent_floor: string | null;
  build_year: string | null;
  min_eok: number;
  max_eok: number;
  areas: number[];
  lat: number;
  lng: number;
  approx: boolean; // true=동 좌표 미확보 → 시군구 중심 근사
  deals: RealEstateDeal[];
}
export interface RealEstateApartments {
  lawd: string;
  sido: string;
  region: string;
  ym?: string | null;
  count: number;
  deal_count: number;
  geocoded: number;
  geocoding: boolean; // 동 좌표 채우는 중 → 잠시 후 재조회하면 정밀해짐
  center: number[];
  apartments: RealEstateApartment[];
}
export interface ReDealPt {
  date: string;
  eok: number;
  floor: string | null;
  area: number | null;
}
export interface ReSeriesPt {
  ym: string; // YYYY-MM
  avg: number;
  min: number;
  max: number;
  count: number;
}
export interface ReAreaMeta {
  area: number;
  key: string; // series 키
  count: number;
  min_eok: number;
  max_eok: number;
  recent_eok: number;
  recent_date: string;
  deals: ReDealPt[];
}
export interface ReStatic {
  available: boolean;
  reason: string;
  households: number | null;
  dong_count: number | null;
  approval_date: string | null;
  floors: string | null;
  parking: string | null;
  far: number | null;
  bcr: number | null;
  builder: string | null;
  heating: string | null;
  office_tel: string | null;
  road_address: string | null;
}
export interface RealEstateApartmentDetail {
  lawd: string;
  sido: string;
  region: string;
  apt: string;
  dong: string;
  ready: boolean;
  warming: boolean;
  progress: { done: number; total: number };
  months?: number;
  hist_from?: string; // YYYYMM
  build_year: string | null;
  total_deals?: number;
  last_date?: string | null;
  areas: ReAreaMeta[];
  series: Record<string, ReSeriesPt[]>;
  static: ReStatic;
  source?: string;
  note?: string;
  message?: string;
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

// --- 제품 단위 원가분해 (unit economics) ------------------------------------
export interface UEProduct {
  id: string;
  ticker: string;
  company: string;
  product: string;
  unit: string;
  sector: string;
}
export interface UEWaterfallItem {
  item: string;
  won: number;
  pct_of_retail: number;
  kind: "channel" | "material" | "process" | "sga" | "profit";
  commodity?: string | null;
  commodity_key?: string | null;
  chg_1y?: number | null;
  direction?: "up" | "down" | "flat" | null;
}
export interface UESensitivity {
  item: string;
  commodity: string;
  op_delta_per_10pct: number;
  op_delta_pct_per_10pct: number | null;
  chg_1y: number | null;
  direction: "up" | "down" | "flat" | null;
}
export interface UnitEconomics {
  product: { ticker: string; company: string; product: string; unit: string; channel: string; note: string };
  as_of: string;
  basis: { source: string; year: number | null };
  summary: {
    retail_price: number;
    distribution_take: number;
    channel_label: string;
    factory_price: number;
    cogs_ratio: number;
    sga_ratio: number;
    op_margin: number;
    profit_per_unit: number;
  };
  waterfall: UEWaterfallItem[];
  materials: UEWaterfallItem[];
  sensitivity: UESensitivity[];
  momentum: {
    cost_delta_won: number;
    op_before: number;
    op_after: number;
    op_change_pct: number | null;
    verdict: string;
  };
  company?: {
    year: number | null;
    headcount: number | null;
    avg_salary_manwon: number | null;
    revenue_eok: number | null;
    labor_eok: number | null;
    labor_pct: number | null;
    sga_eok: number | null;
    op_eok: number | null;
    sga_per_day_eok: number | null;
  } | null;
}

// ===== 회사 단위 원가분석 (원가분석 탭 드릴다운) =====
export interface CCMCompany {
  ticker: string;
  company: string;
  sector: string;
  n_products: number;
  cogs_ratio: number;
  op_margin: number;
  basis: string;
  production_type?: string;   // 야간 배치(I1)가 채운 값 — 없으면 추정 목록
  verdict?: string;
  integrity_pct?: number | null;      // §15 원가 진실성(배치가 채움)
  integrity_coverage?: number | null;
  integrity_grade?: string | null;
  integrity_fail?: number | null;
}
export interface CCMProduct {
  id: string;
  product: string;
  unit: string;
  retail_price: number;
  cogs_ratio: number;
  op_margin: number;
  profit_per_unit: number;
  top_materials: string[];
  material_names: (string | null)[];
}
export interface CCMMaterial {
  item: string;
  pct_of_cogs: number;
  commodity: string | null;
  commodity_key: string | null;
  price: number | null;
  unit: string | null;
  chg_1y: number | null;
  direction: "up" | "down" | "flat" | null;
}
export interface CCMReconciliation {
  bottom_up_op_margin: number;
  reported_op_margin: number;
  gap_pp: number;
  status: "ok" | "warn" | "mismatch" | "loss";
  loss_making?: boolean;
  reason?: string;
  assumptions: string[];
}
export interface CCMFinYear {
  year: number;
  sales: number;
  revenue_eok: number;
  cogs_ratio: number;
  sga_ratio: number | null;
  op_margin: number | null;
}
export interface CCMVarContribution {
  item: string;
  commodity: string | null;
  material_eok: number;
  chg_1y: number;
  variance_eok: number;
  fu: "U" | "F" | "—";
}
export interface CCMVariance {
  basis: string;
  years: string;
  price_variance_eok: number;
  price_variance_pp: number;
  price_fu: "U" | "F" | "—";
  actual_change_pp: number;
  actual_fu: "U" | "F" | "—";
  efficiency_pp: number;
  efficiency_fu: "U" | "F" | "—";
  cogs_ratio_change_3y_pp: number | null;
  contributions: CCMVarContribution[];
  note: string;
  verdict: string;
}
// C2: 생산유형(종합원가 분류) 태그
export interface CCMProductionType {
  type: string;
  archetype: string;
  is_joint: boolean;
  basis: string;
  reason: string | null;
}
// C3: 결합원가 배분 (기본 상대판매가치법 · 보조 순실현가치법)
export interface CCMJointProduct {
  name: string;
  kind: "주산품" | "부산품";
  sales_pct: number;
  sales_eok: number;
  alloc_cogs_eok: number;
  gross_margin_pct: number | null;
}
export interface CCMJointAltProduct {
  name: string;
  kind: "주산품" | "부산품";
  alloc_cogs_eok: number;
  gross_margin_pct: number | null;
  delta_eok: number;
}
export interface CCMJointAllocation {
  method: string;
  method_basis: string;
  production_type: CCMProductionType;
  source: string;
  joint_cost_eok: number;
  revenue_eok: number;
  byproduct_threshold_pct: number;
  products: CCMJointProduct[];
  alt: {
    method: string;
    available: boolean;
    reason?: string;
    note?: string;
    byproduct_nrv_eok?: number;
    joint_cost_after_eok?: number;
    products: CCMJointAltProduct[];
  };
  caveats: string[];
}
// C5: ⚪ 원가회계 교육 레이어 (툴팁 + 해설 카드)
export interface CostingEducation {
  tooltips: Record<string, { badge: string; title: string; body: string }>;
  cards: {
    id: string;
    title: string;
    level: string;
    body: string[];
    table?: { head: string[]; rows: string[][] };
    footer?: string[];
  }[];
  note: string;
}
// W1: 노무비(인건비) 레이어 — DART 「직원 등의 현황」 실측
export interface CCMLaborSegment {
  name: string;
  kind: "생산" | "연구" | "관리·영업";
  headcount: number | null;
  annual_labor: number | null;
  avg_salary: number | null;
  tenure: number | null;
  regular: number | null;
  contract: number | null;
}
export interface CCMLaborYear {
  year: number;
  headcount: number | null;
  annual_labor: number | null;
  annual_labor_eok: number | null;
  avg_salary: number | null;
  avg_salary_disclosed: number | null;
  hourly_cost: number | null;
  mfg_ratio: number | null;
  mfg_labor_eok: number | null;
  mfg_basis: string;
  contract_ratio: number | null;
  by_segment: CCMLaborSegment[];
  source: string;
}
export interface CCMLabor {
  ticker: string;
  years: CCMLaborYear[];
  current: CCMLaborYear | null;
  productivity: {
    year: number;
    rev_per_head_eok: number;
    op_per_head_eok: number | null;
    labor_to_revenue: number | null;
    labor_to_cogs: number | null;
  }[];
  flags: { type: string; severity: "info" | "warn" | "alert"; detail: string; why: string }[];
  consolidated: {
    consolidated_labor_eok: number;
    disclosed_domestic_eok: number;
    subsidiary_share: number | null;
    source: string;
    note: string;
  } | null;
  outsourced: null;
  market_salary: null;
  unit_labor: null;
  assumptions: string[];
  coverage: string;
  note: string;
}

// 사업보고서 원문 실측 — 「비용의 성격별 분류」 + 감사보고서
export interface CCMCostNature {
  basis: string;
  member: string;
  breakdown: { cat: string; amount_eok: number; pct: number }[];
  material_ratio: number;
  labor_ratio: number;
  depreciation_ratio: number;
  total_cost_eok: number;
  labor_eok: number;
  material_eok: number;
  separate_total_eok?: number;
  items: { name: string; cat: string; amount_eok: number; prev_eok: number | null }[];
}
export interface CCMReportNotes {
  ticker: string;
  available: boolean;
  rcept: string | null;
  url?: string;
  reason?: string;
  cost_nature: CCMCostNature | null;
  audit: {
    opinion: string | null;
    kam: string[];
    n_kam: number;
    going_concern_doubt: boolean;
    emphasis: boolean;
    internal_control_issue: boolean;
  } | null;
  source: string;
  note: string;
}

// B3·B4: 사업보고서 「사업의 내용」 — 실단가 변동 + 생산물량·가동률
export interface CCMPriceItem {
  name: string;
  group?: string | null;
  unit?: string | null;
  values: Record<string, number>;
  latest_period?: string;
  latest?: number;
  chg_1y?: number | null;
  chg_span?: number | null;
  span?: string;
}
export interface CCMBusiness {
  ticker: string;
  available: boolean;
  rcept?: string;
  reason?: string;
  price_trend: { scope: string; unit: string | null; items: CCMPriceItem[] }[];
  utilization: {
    unit: string | null;
    items: {
      name: string;
      group?: string | null;
      capacity: number | null;
      output: number | null;
      utilization_pct: number;
      is_total?: boolean;
    }[];
  }[];
  output_series: { unit: string | null; items: CCMPriceItem[]; dropped_rows?: number }[];
  source: string;
  note: string;
}

// 재무제표 3종 감사 — 커버리지 + 정합성(조작 탐지)
export interface CCMStatementCheck {
  code: string;
  label: string;
  status: "ok" | "warn" | "fail";
  detail: string;
  year: number | null;
  why?: string;
}
export interface CCMStatementAudit {
  ticker: string;
  available: boolean;
  statements: {
    sj_div: string;
    label: string;
    years: number[];
    n_years: number;
    n_accounts: number;
    ok: boolean;
  }[];
  core_ok?: boolean;
  basis?: Record<string, string | null>;
  years?: number[];
  checks: CCMStatementCheck[];
  score: number | null;
  verdict: string;
  note: string;
}

// ===== §15 원가 진실성 — 사업보고서 전 항목 파싱 + 교차검증 X1~X35 =====
export interface IntegrityCheck {
  code: string;                       // X1~X35
  label: string;
  grade: "치명" | "중대" | "일반" | "참고";
  weight: number;
  status: "ok" | "warn" | "fail" | "na";
  detail: string;
  a: number | string | null;
  b: number | string | null;
  source_a: string | null;            // A가 어느 절에서 왔는지 — 판정만 보여주면 믿을 근거가 없다
  source_b: string | null;
  why: string | null;
  year: number | null;
}
export interface IntegrityScore {
  ticker: string;
  available: boolean;
  score_pct: number | null;
  coverage_pct: number;
  grade: string;
  phrase: string;
  n_ok: number;
  n_warn: number;
  n_fail: number;
  n_unavailable: number;
  n_total: number;
  checked: number;
  sector_percentile?: number | null;
  by_grade: { grade: string; n: number; ok: number; warn: number; fail: number; na: number }[];
  checks: IntegrityCheck[];
  rcept?: string | null;
  url?: string | null;
  note: string;
  weights: Record<string, number | string>;
}
export interface DFMaterialRow {
  segment: string | null;
  type: string | null;
  item: string;
  use: string | null;
  amount_won: number;
  pct: number | null;
}
export interface DFSegmentRow {
  name: string;
  revenue_won: number;
  op_won?: number | null;
  assets_won?: number | null;
  depreciation_won?: number | null;
  op_margin?: number | null;
  revenue_pct: number | null;
}
export interface DFUnitConsumption {
  segment: string | null;
  type: string | null;
  material: string;
  price_item: string;
  join: string;
  year: string;
  unit_price: number | null;
  price_unit: string | null;
  amount_won: number;
  qty: number;
  qty_unit: string;
  output: number;
  output_unit: string;
  u: number;
  u_unit: string;
  trend: { year: string; u: number; qty?: number; output?: number }[];
  stable: boolean | null;
  note: string;
}
export interface DartFull {
  ticker: string;
  available: boolean;
  rcept?: string;
  url?: string;
  sections_found: string[];
  notes_found?: string[];
  notes_basis?: string | null;
  parsed?: string[];
  reason?: string;
  materials_purchase: { rows: DFMaterialRow[]; total_won: number; unit_won: number; source: string } | null;
  material_prices: {
    rows: { segment: string | null; type: string | null; item: string; prices: Record<string, number>; unit: string | null }[];
    unit_map: Record<string, string>;
    source: string;
  } | null;
  sales_mix: { rows: unknown[]; total_by_year: Record<string, number>; latest_period?: string; source: string } | null;
  segments: { rows: DFSegmentRow[]; total_revenue_won: number; source: string } | null;
  inventory: {
    items: { name: string; book_won: number; loss_won: number }[];
    total_won: number; gross_won: number | null; valuation_loss_won: number;
    loss_pct: number | null; raw_won?: number; wip_won?: number; fg_won?: number;
    source: string;
  } | null;
  related_party: {
    parties: { name: string; sales_won: number; purchase_won: number }[];
    sales_won: number; purchase_won: number; n_parties: number; source: string;
  } | null;
  audit_meta: {
    opinions?: { period: string | null; kind: string | null; auditor: string | null; opinion: string; kam: string | null }[];
    latest_opinion?: string;
    auditors?: (string | null)[];
    auditor_changed?: boolean;
    audit_service?: { period: string; hours: number | null; fee_mn: number | null }[];
    hours_chg?: number;
    fee_chg?: number;
  } | null;
  unit_consumption: DFUnitConsumption[];
  other_financial: Record<string, unknown>;
  consolidation?: Record<string, unknown>;
}

export interface CompanyCostModel {
  ticker: string;
  company: string;
  sector: string;
  as_of: string;
  basis: { source: string; year: number | null; sales: number | null };
  summary: { cogs_ratio: number; sga_ratio: number; op_margin: number; revenue_eok: number | null };
  financials_3y: CCMFinYear[];
  variance: CCMVariance | null;
  production_type: CCMProductionType;
  joint_allocation: CCMJointAllocation | null;
  labor: CCMLabor | null;
  statement_audit: CCMStatementAudit | null;
  report_notes: CCMReportNotes | null;
  business: CCMBusiness | null;
  dart_full: DartFull | null;          // §15.2 전 항목 파싱
  integrity: IntegrityScore | null;    // §15.1 원가 진실성 스코어
  products: CCMProduct[];
  materials: CCMMaterial[];
  reconciliation: CCMReconciliation;
  financials_detail: {
    source: string;
    year: number | null;
    rows: { label: string; eok: number | null; pct: number }[];
    note: string;
  };
  company_block: UnitEconomics["company"];
  coverage: { products: string; sales_mix: string; financials: string };
}

// ===== 원가 경쟁력 랭킹 ("괜찮은 순") =====
export interface CostRankPart {
  score: number;
  max: number;
  detail: string;
  estimated?: boolean;
}
export interface CostRankRow {
  rank: number;
  ticker: string;
  company: string;
  sector: string;
  score: number;
  grade: string;
  parts: Record<string, CostRankPart>;
  estimated_parts: string[];
  headline: string;
  op_margin: number | null;
  cogs_ratio: number | null;
  revenue_eok: number | null;
  cogs_delta_3y_pp: number | null;
  cogs_sd_pp: number | null;
  efficiency_pp: number | null;
  price_variance_pp: number | null;
  verdict: string | null;
  audit_score: number | null;
  recon_status: string | null;
  production_type: string | null;
  basis: string | null;
  year: number | null;
}
export interface CostRanking {
  available: boolean;
  built_at?: string;
  as_of?: string;
  count?: number;
  excluded?: number;
  weights?: Record<string, number>;
  sectors?: string[];
  rows: CostRankRow[];
  note: string;
}

// ===== 미래가치 4문(門) =====
export interface FVFalsifier { cap: string; text: string; why: string }
export interface FVRow {
  rank: number;
  ticker: string;
  name: string;
  sector: string;
  score: number;
  grade: string;
  raw_grade: string;
  parts: Record<string, CostRankPart>;
  estimated_parts: string[];
  falsifiers: FVFalsifier[];
  verdict: string;
  loss_making: boolean;
  year: number | null;
  revenue_eok: number | null;
  op_margin: number | null;
  reinvest_rate: number | null;
  conversion: number | null;
  sales_cagr: number | null;
  net_cash_eok: number | null;
  interest_cover: number | null;
  runway_months: number | null;
  cash_positive: boolean;
  dilution_years: number;
  themes: string[];
}
export interface FutureValueBoard {
  generated_at: string;
  count: number;
  filtered?: number;
  weights: Record<string, number>;
  grades: Record<string, number>;
  verdicts: Record<string, number>;
  loss_verdicts: Record<string, number>;
  theme_ready: boolean;
  sectors: string[];
  rows: FVRow[];
  note: string;
}

// ===== P1: DART 사업보고서 품목별 매출구성 =====
export interface CompanyProducts {
  ticker: string;
  products: { name: string; pct: number }[];
  source: string;
  coverage: string;
}

// ===== 애널리스트 리포트 취합 (Tier 1: 사실+링크) =====
export interface AnalystReport {
  title: string;
  broker: string;
  date: string;
  url: string | null;
  target_price?: number | null;
}
export interface AnalystProvider {
  broker: string;
  date: string;
  target: number | null;
  opinion: string;
}
export interface AnalystConsensus {
  opinion_score: number;
  opinion_label: string;
  target_price: number;
  eps: number;
  per: number;
  n_institutions: number;
  as_of: string | null;
  opinion_dist: { buy: number; hold: number; sell: number };
  providers: AnalystProvider[];
  source: string;
}
export interface AnalystReports {
  ticker: string;
  company: string;
  n_reports: number;
  brokers: string[];
  broker_count: number;
  latest_date: string | null;
  reports: AnalystReport[];
  consensus: AnalystConsensus | null;
  target_sample?: { n: number; avg: number | null; high: number | null; low: number | null };
  source: string;
  error?: string;
}

export const api = {
  health: () => request<Health>("/api/health"),
  authLogin: (username: string, password: string) =>
    request<{ token: string; username: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  authSendCode: (email: string) =>
    request<{ sent: boolean; email_configured: boolean; dev_code?: string }>("/api/auth/send-code", { method: "POST", body: JSON.stringify({ email }) }),
  authRegister: (username: string, password: string, email: string, name: string, code: string) =>
    request<{ token: string; username: string }>("/api/auth/register", { method: "POST", body: JSON.stringify({ username, password, email, name, code }) }),
  authFindId: (email: string) =>
    request<{ usernames: string[] }>("/api/auth/find-id", { method: "POST", body: JSON.stringify({ email }) }),
  authResetPassword: (username: string, email: string, new_password: string, code: string) =>
    request<{ ok: boolean }>("/api/auth/reset-password", { method: "POST", body: JSON.stringify({ username, email, new_password, code }) }),
  me: () => request<Me>("/api/auth/me"),
  track: (view: string) => request<{ ok: boolean }>("/api/track", { method: "POST", body: JSON.stringify({ view }) }),
  // 관리자
  adminBlogGenerate: (p: { kind: string; ticker?: string; title?: string; body?: string }) =>
    request<BlogPost>("/api/admin/blog/generate", { method: "POST", body: JSON.stringify(p) }),
  adminUsers: () => request<{ users: AdminUser[]; admins: string[] }>("/api/admin/users"),
  adminBlogPublish: (date = "", force = true) =>
    request<BlogSavedPost>("/api/admin/blog/publish", {
      method: "POST", body: JSON.stringify({ date, force }),
    }),
  adminBlogPosts: (limit = 60) =>
    request<{ posts: BlogPostListItem[]; dir: string }>(`/api/admin/blog/posts?limit=${limit}`),
  adminBlogPost: (date = "", kind = "market-wrap") =>
    request<BlogSavedPost>(
      `/api/admin/blog/post?date=${encodeURIComponent(date)}&kind=${encodeURIComponent(kind)}`),
  adminBlogScheduler: () => request<BlogSchedulerStatus>("/api/admin/blog/scheduler"),
  adminStatus: () => request<AdminStatus>("/api/admin/status"),
  adminStats: () => request<VisitorStats>("/api/admin/stats"),
  adminCurationGet: () => request<Curation>("/api/admin/curation"),
  adminCurationSet: (headline: string, picks: string[], note: string) =>
    request<Curation>("/api/admin/curation", { method: "POST", body: JSON.stringify({ headline, picks, note }) }),
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
  livePulse: () => request<LivePulse>(`/api/data/live-pulse`),
  moneyFlow: () => request<GlobalMoneyFlow>(`/api/data/money-flow`),
  premarket: () => request<Premarket>(`/api/data/premarket`),
  premarketHistory: (limit = 60) => request<PremarketHistory>(`/api/data/premarket/history?limit=${limit}`),
  targetPrice: (ticker: string) => request<TargetPrice>(`/api/data/target-price?ticker=${ticker}`),
  signals: (ticker: string) => request<TradeSignals>(`/api/data/signals?ticker=${ticker}`),
  stockScore: () => request<StockScoreBoard>(`/api/data/stock-score`),
  delistingRisk: () => request<DelistingBoard>(`/api/data/delisting-risk`),
  earningsQuality: () => request<EqBoard>(`/api/data/earnings-quality`),
  watchlist: () => request<Watchlist>(`/api/data/watchlist`),
  watchlistAdd: (ticker: string) => request<Watchlist>(`/api/data/watchlist/add?ticker=${ticker}`, { method: "POST" }),
  watchlistRemove: (ticker: string) => request<Watchlist>(`/api/data/watchlist/remove?ticker=${ticker}`, { method: "POST" }),
  portfolioDiag: () => request<Portfolio>(`/api/data/portfolio`),
  portfolioSave: (holdings: { ticker: string; qty: number; avg: number }[]) =>
    request<Portfolio>(`/api/data/portfolio`, { method: "POST", body: JSON.stringify(holdings) }),
  dividends: () => request<DividendsBoard>(`/api/data/dividends`),
  dividendUniverse: () => request<DividendUniverse>(`/api/data/dividend-universe`),
  dividendDetail: (ticker: string) => request<DividendDetail>(`/api/data/dividend-detail?ticker=${ticker}`),
  dividendRoyalty: (invest = 0) => request<DividendRoyalty>(`/api/data/dividend-royalty${invest > 0 ? `?invest=${invest}` : ""}`),
  crisisSurvivors: () => request<CrisisSurvivors>(`/api/data/crisis-survivors`),
  dividendEtf: () => request<DividendEtfBoard>(`/api/data/dividend-etf`),
  spDca: (monthly: number, years: number, annualReturn: number) =>
    request<SpDca>(`/api/data/sp-dca?monthly=${monthly}&years=${years}&annual_return=${annualReturn}`),
  budgetSummary: (month?: string) => request<BudgetSummary>(`/api/data/budget/summary${month ? `?month=${month}` : ""}`),
  budgetSetIncome: (monthly_net: number, extra = 0, memo = "") =>
    request<BudgetIncome>(`/api/data/budget/income`, { method: "POST", body: JSON.stringify({ monthly_net, extra, memo }) }),
  budgetParsePayslip: async (file: File): Promise<PayslipParse> => {
    const fd = new FormData();
    fd.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/data/budget/income/parse`, { method: "POST", body: fd, headers: { ...authHeader() } });
    } catch {
      throw new ApiError(0, `백엔드에 연결할 수 없습니다 (${API_BASE}).`);
    }
    if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
    return res.json() as Promise<PayslipParse>;
  },
  budgetImportFile: async (file: File): Promise<{ parsed: number; sample: BudgetTx[] }> => {
    const fd = new FormData();
    fd.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/data/budget/import-file`, { method: "POST", body: fd, headers: { ...authHeader() } });
    } catch {
      throw new ApiError(0, `백엔드에 연결할 수 없습니다 (${API_BASE}).`);
    }
    if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
    return res.json();
  },
  budgetImport: (text: string) =>
    request<{ parsed: number; sample: BudgetTx[] }>(`/api/data/budget/import`, { method: "POST", body: JSON.stringify({ text }) }),
  budgetAdd: (items: { date: string; merchant: string; amount: number; category?: string }[]) =>
    request<{ added: number }>(`/api/data/budget/add`, { method: "POST", body: JSON.stringify(items) }),
  budgetDelete: (txId: number) => request<{ ok: boolean }>(`/api/data/budget/delete?tx_id=${txId}`, { method: "POST" }),
  budgetSetCategory: (txId: number, category: string, applyAll = true) =>
    request<{ ok: boolean }>(`/api/data/budget/category?tx_id=${txId}&category=${encodeURIComponent(category)}&apply_all=${applyAll}`, { method: "POST" }),
  budgetPlan: (emergencyMonths = 3, investRatio = 0.5) =>
    request<BudgetPlan>(`/api/data/budget/plan?emergency_months=${emergencyMonths}&invest_ratio=${investRatio}`),
  incomeOverview: () => request<IncomeOverview>(`/api/data/income/overview`),
  incomeSalaryGet: () => request<{ salary: SalaryComputed | null; history: SalaryHistory[] }>(`/api/data/income/salary`),
  incomeSalarySet: (earnings: SalaryItem[], deductions: SalaryItem[], memo = "") =>
    request<SalaryComputed>(`/api/data/income/salary`, { method: "POST", body: JSON.stringify({ earnings, deductions, memo }) }),
  incomeRaiseSim: (p: { raise_pct?: number; raise_amount?: number; years?: number; invest_ratio?: number; annual_return?: number }) => {
    const q = new URLSearchParams();
    if (p.raise_pct != null) q.set("raise_pct", String(p.raise_pct));
    if (p.raise_amount != null) q.set("raise_amount", String(p.raise_amount));
    if (p.years != null) q.set("years", String(p.years));
    if (p.invest_ratio != null) q.set("invest_ratio", String(p.invest_ratio));
    if (p.annual_return != null) q.set("annual_return", String(p.annual_return));
    return request<RaiseSim>(`/api/data/income/raise-sim?${q.toString()}`);
  },
  incomeSideList: (month?: string) => request<SideList>(`/api/data/income/side${month ? `?month=${month}` : ""}`),
  incomeSideAdd: (items: { date: string; source: string; amount: number; memo?: string }[]) =>
    request<{ added: number }>(`/api/data/income/side`, { method: "POST", body: JSON.stringify(items) }),
  incomeSideDelete: (sid: number) => request<{ ok: boolean }>(`/api/data/income/side/delete?sid=${sid}`, { method: "POST" }),
  wealthPlan: () => request<WealthPlan>(`/api/data/wealth/plan`),
  wealthSaveProfile: (profile: Record<string, unknown>) =>
    request<WealthPlan>(`/api/data/wealth/profile`, { method: "POST", body: JSON.stringify(profile) }),
  wealthLoanSim: (loanAmount: number, loanRate: number, loanYears: number, investReturn: number) =>
    request<LoanSim>(`/api/data/wealth/loan-sim?loan_amount=${loanAmount}&loan_rate=${loanRate}&loan_years=${loanYears}&invest_return=${investReturn}`),
  wealthRealtySim: (p: { price: number; own_capital: number; loan_rate: number; years: number; appreciation: number; mode: string; deposit: number; rent_monthly: number }) =>
    request<RealtySim>(`/api/data/wealth/realty-sim?price=${p.price}&own_capital=${p.own_capital}&loan_rate=${p.loan_rate}&years=${p.years}&appreciation=${p.appreciation}&mode=${p.mode}&deposit=${p.deposit}&rent_monthly=${p.rent_monthly}`),
  wealthRealtyLoans: (p: { price: number; annual_income: number; age: number; married: boolean; homeless: boolean; has_child: boolean; deposit: number; mode: string }) =>
    request<RealtyLoans>(`/api/data/wealth/realty-loans?price=${p.price}&annual_income=${p.annual_income}&age=${p.age}&married=${p.married}&homeless=${p.homeless}&has_child=${p.has_child}&deposit=${p.deposit}&mode=${p.mode}`),
  wealthHoldings: () => request<HoldingsData>(`/api/data/wealth/holdings`),
  wealthSaveHoldings: (holdings: { name: string; monthly: number; current: number }[], horizon: number) =>
    request<HoldingsData>(`/api/data/wealth/holdings`, { method: "POST", body: JSON.stringify({ holdings, horizon }) }),
  wealthDividendSim: (p: { invest: number; yield_pct: number; years: number; growth_pct: number; reinvest: boolean }) =>
    request<DividendSim>(`/api/data/wealth/dividend-sim?invest=${p.invest}&yield_pct=${p.yield_pct}&years=${p.years}&growth_pct=${p.growth_pct}&reinvest=${p.reinvest}`),
  wealthIpoSim: (p: { offer_price: number; alloc_shares: number; subscribe_amount: number }) =>
    request<IpoSim>(`/api/data/wealth/ipo-sim?offer_price=${p.offer_price}&alloc_shares=${p.alloc_shares}&subscribe_amount=${p.subscribe_amount}`),
  briefing: (market: "auto" | "kr" | "us" = "auto") => request<Briefing>(`/api/data/briefing?market=${market}`),
  movers: (refresh = false) => request<Movers>(`/api/data/movers${refresh ? "?refresh=true" : ""}`),
  moversHistory: (limit = 50) => request<{ items: MoversHistoryItem[] }>(`/api/data/movers/history?limit=${limit}`),
  wealthDividendPicks: (top = 12) => request<DividendPicks>(`/api/data/wealth/dividend-picks?top=${top}`),
  wealthIpoSchedule: () => request<IpoSchedule>(`/api/data/wealth/ipo-schedule`),
  koreaFlow: () => request<KoreaFlow>(`/api/data/korea-flow`),
  koreaDiagnosis: () => request<KoreaDiagnosis>(`/api/data/korea-diagnosis`),
  kospiEarnings: () => request<KospiEarnings>(`/api/data/kospi-earnings`),
  realestateTrades: () => request<RealEstateTrades>(`/api/data/realestate-trades`),
  realestateRent: () => request<RealEstateRent>(`/api/data/realestate-rent`),
  ecosMacro: () => request<EcosMacro>(`/api/data/ecos-macro`),
  moneySupply: () => request<MoneySupply>(`/api/data/money-supply`),
  moneyAnalysis: () => request<MoneyAnalysis>(`/api/data/money-analysis`),
  realEconomy: () => request<RealEconomy>(`/api/data/real-economy`),
  institutional: () => request<InstitutionalFlow>(`/api/data/institutional`),
  futureThemes: () => request<FutureThemesResponse>(`/api/data/future-themes`),
  futureThemesStatus: () => request<FutureThemesStatus>(`/api/data/future-themes/status`),
  futureTheme: (key: string) => request<FutureTheme>(`/api/data/future-theme?key=${encodeURIComponent(key)}`),
  crossAsset: () => request<CrossAssetLayer>(`/api/data/cross-asset`),
  assetDetail: (key: string, date?: string) =>
    request<AssetDetail>(
      `/api/data/asset-detail?key=${encodeURIComponent(key)}${date ? `&date=${encodeURIComponent(date)}` : ""}`,
    ),
  assetQuotes: (symbols: string[], date?: string) =>
    request<{ quotes: ConstituentQuote[] }>(
      `/api/data/asset-quotes?symbols=${encodeURIComponent(symbols.join(","))}${date ? `&date=${encodeURIComponent(date)}` : ""}`,
    ),
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
  unitEconomicsProducts: () =>
    request<{ as_of: string; products: UEProduct[] }>(`/api/data/unit-economics/products`),
  unitEconomics: (product: string) =>
    request<UnitEconomics>(`/api/data/unit-economics?product=${encodeURIComponent(product)}`),
  companyCostModelList: () =>
    request<{ as_of: string; sectors: string[]; companies: CCMCompany[] }>(`/api/data/company-costmodel/list`),
  companyCostModel: (ticker: string) =>
    request<CompanyCostModel>(`/api/data/company-costmodel?ticker=${encodeURIComponent(ticker)}`),
  analystReports: (ticker: string, company: string) =>
    request<AnalystReports>(`/api/data/analyst-reports?ticker=${encodeURIComponent(ticker)}&company=${encodeURIComponent(company)}`),
  companyProducts: (ticker: string) =>
    request<CompanyProducts>(`/api/data/company-products?ticker=${encodeURIComponent(ticker)}`),
  costingEducation: () => request<CostingEducation>(`/api/data/costing-education`),
  futureValue: (sector?: string, onlyLoss = false) => {
    const q = new URLSearchParams();
    if (sector && sector !== "전체") q.set("sector", sector);
    if (onlyLoss) q.set("only_loss", "true");
    const s = q.toString();
    return request<FutureValueBoard>(`/api/data/future-value${s ? `?${s}` : ""}`);
  },
  costRanking: (sector?: string) => {
    const q = sector && sector !== "전체" ? `?sector=${encodeURIComponent(sector)}` : "";
    return request<CostRanking>(`/api/data/company-costmodel/ranking${q}`);
  },
  companyLabor: (ticker: string) =>
    request<CCMLabor>(`/api/data/company-labor?ticker=${encodeURIComponent(ticker)}`),
  statementAudit: (ticker: string) =>
    request<CCMStatementAudit>(`/api/data/statement-audit?ticker=${encodeURIComponent(ticker)}`),
  reportNotes: (ticker: string) =>
    request<CCMReportNotes>(`/api/data/report-notes?ticker=${encodeURIComponent(ticker)}`),
  reportBusiness: (ticker: string) =>
    request<CCMBusiness>(`/api/data/report-business?ticker=${encodeURIComponent(ticker)}`),
  dartFull: (ticker: string, refresh = false) =>
    request<DartFull>(`/api/data/dart-full?ticker=${encodeURIComponent(ticker)}${refresh ? "&refresh=true" : ""}`),
  integrity: (ticker: string, refresh = false) =>
    request<IntegrityScore>(`/api/data/integrity?ticker=${encodeURIComponent(ticker)}${refresh ? "&refresh=true" : ""}`),
  crisisMeta: () => request<CrisisMeta>(`/api/crisis/meta`),
  crisisSim: (metric: string, crises?: string[]) => {
    const q = new URLSearchParams({ metric });
    if (crises && crises.length) q.set("crises", crises.join(","));
    return request<CrisisSim>(`/api/crisis/sim?${q.toString()}`);
  },
  crisisWarning: () => request<CrisisWarning>(`/api/crisis/warning`),
  crisisKoreaWarning: () => request<CrisisKoreaWarning>(`/api/crisis/korea-warning`),
  crisisCountries: () => request<CrisisCountries>(`/api/crisis/countries`),
  realestateMap: () => request<RealEstateMapData>(`/api/data/realestate-map`),
  realestateDeals: (lawd: string, ym?: string) =>
    request<RealEstateDeals>(`/api/data/realestate-deals?lawd=${encodeURIComponent(lawd)}${ym ? `&ym=${ym}` : ""}`),
  realestateApartments: (lawd: string, ym?: string) =>
    request<RealEstateApartments>(`/api/data/realestate-apartments?lawd=${encodeURIComponent(lawd)}${ym ? `&ym=${ym}` : ""}`),
  realestateApartment: (lawd: string, apt: string, dong?: string, months = 120) =>
    request<RealEstateApartmentDetail>(
      `/api/data/realestate-apartment?lawd=${encodeURIComponent(lawd)}&apt=${encodeURIComponent(apt)}${
        dong ? `&dong=${encodeURIComponent(dong)}` : ""
      }&months=${months}`,
    ),
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
