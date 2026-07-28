// 회사 단위 원가분석 — 원가모델·노무비·사업보고서·감사·랭킹·미래가치

import { request } from "./client";
import type { UnitEconomics } from "./unitEconomics";
import type { DartFull, IntegrityScore } from "./integrity";

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
  scoring?: {
    base: number;
    deductions: { reason: string; points: number; codes: string[] }[];
    final: number;
    formula: string;
  };
  ledger?: {
    year: number;
    basis: string | null;
    accounts: {
      label: string;
      statement: string;
      eok: number | null;
      won: number;
      account_nm: string;
      account_id: string;
    }[];
  }[];
  source?: string;
  verdict: string;
  note: string;
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

export const costmodelApi = {
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
};
