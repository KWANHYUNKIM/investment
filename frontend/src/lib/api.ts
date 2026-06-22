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

// 부동산 실거래 — 국토부 RTMS (서울 25개구 아파트 매매 월별 거래량·거래대금)
export interface RealEstateMonth {
  ym: string;
  label: string;
  count: number;
  amount_eok: number;
  provisional: boolean; // 신고 진행중(잠정) — 보통 당월
}
export interface RealEstateRegion {
  region: string;
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
  by_region: RealEstateRegion[];
  partial?: boolean;
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
  livePulse: () => request<LivePulse>(`/api/data/live-pulse`),
  moneyFlow: () => request<GlobalMoneyFlow>(`/api/data/money-flow`),
  koreaFlow: () => request<KoreaFlow>(`/api/data/korea-flow`),
  realestateTrades: () => request<RealEstateTrades>(`/api/data/realestate-trades`),
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
